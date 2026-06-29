"""Heizungssteuerung Hauptprogramm."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from dataclasses import replace
from typing import Any

from .lib.brauchwasser import BrauchwasserState, compute_brauchwasser
from .lib.brunnen import BrunnenPressureState, brunnen_flow_timer_armed, compute_brunnen_pressure
from .lib.config import AppConfig, ChannelConfig, ConfigError, IoMap, load_yaml, resolve_config_file
from .lib.failsafe import FailsafeMonitor, FailsafeState
from .lib.flowmeter import FlowmeterModbusClient, FlowmeterModbusConfig
from .lib.freigaben import Freigaben
from .lib.hand_auto import HandAutoManager
from .lib.intercpu import KellerModbusClient
from .lib.iohw import BaseIO, HardwareSnapshot, create_io_backend
from .lib.mqtt_bridge import MqttBridge
from .lib.regler import ReglerParameter
from .lib.routing import RoutingState, compute_routing
from .lib.state import StateStore
from .lib.tor import entscheide_tor_command

log = logging.getLogger("heizung")


async def run() -> int:
    """Hauptregelkreis."""
    try:
        app_config = AppConfig.load()
    except ConfigError as exc:
        log.error("Konfiguration ungueltig: %s", exc)
        return 2

    _apply_log_level(app_config.setting("logging.level", "INFO"))
    cycle_s = float(app_config.setting("regelung.fast_zyklus_ms", 100)) / 1000
    heating_divider = max(1, int(app_config.setting("regelung.heizung_divider", 10)))
    default_hand_timeout = app_config.setting("hand.default_timeout_min")
    hand_state_path = app_config.state_path(app_config.setting("hand.state_persist_path", "state/hand_state.json"))
    freigaben_state_path = app_config.state_path(app_config.setting("freigaben.state_persist_path", "state/freigaben.json"))
    regler_state_path = app_config.state_path(app_config.setting("regler.state_persist_path", "state/regler.json"))

    keller_client: KellerModbusClient | None = None
    controller_config = app_config
    keller_io_map = _load_keller_io_map(app_config) if _controller_role(app_config) == "haupt" else None
    if keller_io_map is not None and bool(app_config.setting("intercpu.keller.enabled", True)):
        host = str(app_config.setting("intercpu.keller.host", "10.1.25.11"))
        port = int(app_config.setting("intercpu.keller.port", 502))
        timeout_s = float(app_config.setting("intercpu.keller.timeout_s", 1.0))
        keller_client = KellerModbusClient(host, port, keller_io_map, timeout_s=timeout_s)
        controller_config = replace(app_config, io_map=_merge_io_maps(app_config.io_map, keller_io_map))
        log.info("Keller-Slave per Modbus aktiviert: %s:%s", host, port)

    io_backend = create_io_backend(app_config.io_map, os.environ.get("HEIZUNG_IO_BACKEND", "auto"))
    hand_auto = HandAutoManager(controller_config.io_map, StateStore(hand_state_path), default_hand_timeout)
    freigaben = Freigaben.from_settings(app_config.settings, StateStore(freigaben_state_path))
    regler = ReglerParameter.from_settings(app_config.settings, StateStore(regler_state_path))
    failsafe_monitor = FailsafeMonitor.from_settings(app_config.settings)
    flowmeter_config = FlowmeterModbusConfig.from_settings(app_config.settings)
    flowmeter = FlowmeterModbusClient(flowmeter_config) if flowmeter_config.enabled else None
    mqtt = MqttBridge(app_config.mqtt)
    mqtt.set_default_demands(app_config.setting("anforderungen", {}))
    mqtt.start()

    log.info("Heizungssteuerung gestartet, schneller Zyklus %.3fs, Heizungsdivider %s", cycle_s, heating_divider)
    stop = asyncio.Event()
    boot_ts = time.time()

    def _handle_sig() -> None:
        log.info("Signal empfangen, beende ...")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_sig)
        except NotImplementedError:
            # Windows
            pass

    last_heartbeat_tick = -1
    ha_discovery_published = False
    cycle_count = 0
    brauchwasser_ladung_active = False
    brunnen_active = False
    brunnen_speed_pct = 0.0
    brunnen_flow_l_min: float | None = None
    brunnen_flow_last_seen_ts: float | None = None
    brunnen_no_flow_since_ts: float | None = None
    flowmeter_next_poll_ts = 0.0
    flowmeter_task: asyncio.Task[float] | None = None
    flowmeter_last_error_log_ts = 0.0
    applied_do: dict[str, bool] = {}
    applied_ao: dict[str, float] = {}
    oelbrenner_common_active = False
    klima_og_cooling_active = False
    try:
        while not stop.is_set():
            started = time.monotonic()
            now_ts = time.time()
            if mqtt.connected and not ha_discovery_published:
                _publish_ha_discovery(mqtt, controller_config)
                ha_discovery_published = True
            if flowmeter is not None:
                if flowmeter_task is not None and flowmeter_task.done():
                    try:
                        brunnen_flow_l_min = flowmeter_task.result()
                        brunnen_flow_last_seen_ts = now_ts
                    except Exception as exc:
                        if now_ts - flowmeter_last_error_log_ts >= 60:
                            flowmeter_last_error_log_ts = now_ts
                            log.warning("Brunnen-Flowmeter Modbus nicht erreichbar: %s", exc)
                    flowmeter_task = None
                    flowmeter_next_poll_ts = now_ts + max(0.2, flowmeter_config.poll_interval_s)
                if flowmeter_task is None and now_ts >= flowmeter_next_poll_ts:
                    flowmeter_task = asyncio.create_task(flowmeter.read_flow_l_min())

            snapshot = await io_backend.read_all()
            if keller_client is not None:
                try:
                    keller_snapshot = await keller_client.read_snapshot()
                    snapshot = _merge_snapshots(snapshot, keller_snapshot)
                    mqtt.peer_last_seen_ts = now_ts
                    mqtt.peer_online = True
                except Exception as exc:
                    mqtt.peer_online = False
                    log.warning("Keller-Slave Modbus nicht erreichbar: %s", exc)

            brunnen_flow_l_min, brunnen_no_flow_s, brunnen_no_flow_since_ts = _brunnen_flow_runtime(
                controller_config,
                regler,
                brunnen_flow_l_min,
                brunnen_flow_last_seen_ts,
                brunnen_no_flow_since_ts,
                brunnen_active,
                brunnen_flow_timer_armed(controller_config, snapshot, regler),
                now_ts,
            )
            await _handle_mqtt_commands(
                mqtt,
                controller_config,
                hand_auto,
                freigaben,
                regler,
                failsafe_monitor,
                io_backend,
                snapshot,
                now_ts,
            )

            failsafe_state = failsafe_monitor.evaluate(
                now_ts=now_ts,
                mqtt_connected=mqtt.connected,
                last_mqtt_seen_ts=mqtt.last_seen_ts,
                last_ha_heartbeat_ts=mqtt.last_ha_heartbeat_ts,
                outside_temp_c=_sensor_value_by_component(controller_config, snapshot, "aussen"),
            )

            heating_tick = cycle_count % heating_divider == 0
            if heating_tick:
                (
                    routing_state,
                    brauchwasser_state,
                    brunnen_state,
                    auto_do,
                    auto_ao,
                    oelbrenner_common_active,
                    klima_og_cooling_active,
                ) = _compute_auto_outputs(
                    controller_config,
                    mqtt,
                    snapshot,
                    failsafe_state,
                    freigaben,
                    regler,
                    brauchwasser_ladung_active,
                    brunnen_active,
                    brunnen_speed_pct,
                    oelbrenner_common_active,
                    klima_og_cooling_active,
                    cycle_s,
                    brunnen_flow_l_min,
                    brunnen_no_flow_s,
                )
                brauchwasser_ladung_active = brauchwasser_state.active
            else:
                brunnen_state = _compute_fast_brunnen_outputs(
                    controller_config,
                    snapshot,
                    regler,
                    brunnen_active,
                    brunnen_speed_pct,
                    cycle_s,
                    brunnen_flow_l_min,
                    brunnen_no_flow_s,
                    auto_do,
                    auto_ao,
                    klima_og_cooling_active,
                )
            brunnen_active = brunnen_state.active
            brunnen_speed_pct = brunnen_state.speed_pct
            write_only = None if heating_tick else _brunnen_output_ids(controller_config)
            written_do, written_ao = await _write_outputs(
                controller_config,
                app_config.io_map,
                io_backend,
                hand_auto,
                auto_do,
                auto_ao,
                snapshot,
                now_ts,
                keller_client,
                only_channel_ids=write_only,
                keller_fallback_do=applied_do,
                keller_fallback_ao=applied_ao,
            )
            applied_do.update(written_do)
            applied_ao.update(written_ao)
            if keller_client is not None and mqtt.peer_online is not False:
                mqtt.peer_last_seen_ts = now_ts
                mqtt.peer_online = True

            if heating_tick:
                _publish_state(
                    mqtt,
                    controller_config,
                    snapshot,
                    failsafe_state,
                    hand_auto,
                    freigaben,
                    regler,
                    routing_state,
                    brauchwasser_state,
                    brunnen_state,
                    applied_do,
                    applied_ao,
                    klima_og_cooling_active,
                )
            uptime_s = int(now_ts - boot_ts)
            heartbeat_tick = uptime_s // 30
            if heartbeat_tick != last_heartbeat_tick:
                last_heartbeat_tick = heartbeat_tick
                mqtt.publish_heartbeat(uptime_s)

            cycle_count += 1
            await _update_cpu_leds(
                io_backend,
                app_config,
                mqtt,
                failsafe_state,
                now_ts,
                boot_ts,
                cycle_count // max(1, heating_divider // 2),
            )

            await _sleep_remaining(stop, cycle_s, started)
    finally:
        await io_backend.set_cpu_leds({"A1": "off", "A2": "off", "A3": "off", "A4": "off", "A5": "off"})
        if flowmeter_task is not None:
            flowmeter_task.cancel()
        mqtt.stop()
        await io_backend.close()

    log.info("Heizungssteuerung beendet")
    return 0


async def _sleep_remaining(stop: asyncio.Event, cycle_s: float, started: float) -> None:
    remaining = max(0.0, cycle_s - (time.monotonic() - started))
    try:
        await asyncio.wait_for(stop.wait(), timeout=remaining)
    except TimeoutError:
        return


def _load_keller_io_map(app_config: AppConfig) -> IoMap | None:
    try:
        raw = load_yaml(resolve_config_file(app_config.config_dir, "io_map.keller.yaml"))
    except ConfigError:
        return None
    return IoMap.from_dict(raw)


def _merge_io_maps(main: IoMap, keller: IoMap) -> IoMap:
    return IoMap(
        revpi=dict(main.revpi),
        do={**main.do, **keller.do},
        di={**main.di, **keller.di},
        ai={**main.ai, **keller.ai},
        ao={**main.ao, **keller.ao},
        rtd={**main.rtd, **keller.rtd},
    )


def _brunnen_flow_runtime(
    app_config: AppConfig,
    regler: ReglerParameter,
    flow_l_min: float | None,
    flow_last_seen_ts: float | None,
    no_flow_since_ts: float | None,
    pump_active: bool,
    timer_armed: bool,
    now_ts: float,
) -> tuple[float | None, float | None, float | None]:
    stale_timeout_s = float(app_config.setting("brunnen.flow_stale_timeout_s", 15.0))
    if flow_l_min is None or flow_last_seen_ts is None or now_ts - flow_last_seen_ts > stale_timeout_s:
        return None, None, None

    if not pump_active or not timer_armed:
        return flow_l_min, None, None

    if flow_l_min > float(regler.brunnen_flow_min_l_min):
        return flow_l_min, 0.0, None

    if no_flow_since_ts is None:
        no_flow_since_ts = now_ts
    return flow_l_min, max(0.0, now_ts - no_flow_since_ts), no_flow_since_ts


def _merge_snapshots(main: HardwareSnapshot, keller: HardwareSnapshot) -> HardwareSnapshot:
    return HardwareSnapshot(
        di={**main.di, **keller.di},
        ai={**main.ai, **keller.ai},
        rtd={**main.rtd, **keller.rtd},
        do={**main.do, **keller.do},
        ao={**main.ao, **keller.ao},
    )


async def _update_cpu_leds(
    io_backend: BaseIO,
    app_config: AppConfig,
    mqtt: MqttBridge,
    failsafe_state: FailsafeState,
    now_ts: float,
    boot_ts: float,
    cycle_count: int,
) -> None:
    settings = app_config.setting("leds", {})
    if isinstance(settings, dict) and settings.get("enabled") is False:
        return

    role = _controller_role(app_config)
    peer_timeout_s = float((settings or {}).get("peer_timeout_s", 90) if isinstance(settings, dict) else 90)
    heartbeat_interval_s = float(
        (settings or {}).get("heartbeat_interval_s", 1.0) if isinstance(settings, dict) else 1.0
    )
    ha_timeout_s = float(app_config.setting("failsafe.ha_heartbeat_timeout_s", 300))
    ha_required = bool(app_config.setting("failsafe.ha_heartbeat_required", False))

    colors = {
        "A1": _heartbeat_led_color(now_ts, boot_ts, heartbeat_interval_s),
        "A2": _peer_led_color(mqtt, now_ts, boot_ts, peer_timeout_s),
    }
    if role == "haupt":
        colors.update(
            {
                "A3": "green" if mqtt.connected else "red",
                "A4": _freshness_led_color(mqtt.last_ha_heartbeat_ts, now_ts, ha_timeout_s, required=ha_required),
                "A5": "red" if failsafe_state.active else "green",
            }
        )
    else:
        colors.update({"A3": "off", "A4": "off", "A5": "off"})

    await io_backend.set_cpu_leds(colors)


def _heartbeat_led_color(now_ts: float, boot_ts: float, interval_s: float) -> str:
    interval_s = max(0.2, float(interval_s))
    return "blue" if int((now_ts - boot_ts) / interval_s) % 2 else "yellow"


def _controller_role(app_config: AppConfig) -> str:
    leds = app_config.mqtt.get("leds", {})
    if isinstance(leds, dict) and leds.get("role"):
        role = str(leds["role"]).strip().lower()
        if role in {"haupt", "main"}:
            return "haupt"
        if role in {"keller", "slave"}:
            return "keller"

    client_id = str(app_config.mqtt.get("broker", {}).get("client_id", "")).lower()
    hostname = str(app_config.io_map.revpi.get("hostname", "")).lower()
    if "keller" in client_id or hostname.endswith("107293"):
        return "keller"
    return "haupt"


def _peer_led_color(mqtt: MqttBridge, now_ts: float, boot_ts: float, timeout_s: float) -> str:
    if mqtt.peer_last_seen_ts is not None and now_ts - mqtt.peer_last_seen_ts <= timeout_s and mqtt.peer_online is not False:
        return "green"
    if now_ts - boot_ts < timeout_s:
        return "yellow"
    return "red"


def _freshness_led_color(last_seen_ts: float | None, now_ts: float, timeout_s: float, *, required: bool) -> str:
    if last_seen_ts is not None and now_ts - last_seen_ts <= timeout_s:
        return "green"
    return "red" if required else "yellow"


async def _handle_mqtt_commands(
    mqtt: MqttBridge,
    app_config: AppConfig,
    hand_auto: HandAutoManager,
    freigaben: Freigaben,
    regler: ReglerParameter,
    failsafe_monitor: FailsafeMonitor,
    io_backend: BaseIO,
    snapshot: HardwareSnapshot,
    now_ts: float,
) -> None:
    for command in mqtt.drain_commands():
        if command.typ == "failsafe_force":
            failsafe_monitor.force = str(command.payload).strip().lower() in {"1", "true", "on", "ja"}
            continue

        if command.typ == "freigabe_set":
            group, _, name = command.name.partition("/")
            if not freigaben.set(group, name, _extract_bool(command.payload)):
                log.warning("MQTT-Freigabe fuer unbekannte Gruppe/Komponente ignoriert: %s", command.name)
            continue

        if command.typ == "regler_set":
            if not regler.set(command.name, command.payload):
                log.warning("MQTT-Reglerparameter unbekannt, ignoriert: %s", command.name)
            continue

        if command.typ == "tor_command":
            await _handle_tor_command(app_config, io_backend, snapshot, command.name)
            continue

        channel = app_config.io_map.by_component(command.name)
        if channel is None:
            log.warning("MQTT-Kommando fuer unbekannte Komponente ignoriert: %s", command.name)
            continue
        log.info("MQTT-Kommando verarbeitet: typ=%s komponente=%s kanal=%s kind=%s", command.typ, command.name, channel.id, channel.kind)

        if command.typ == "hand_set":
            wert = _extract_hand_value(command.payload)
            hand_auto.set_hand(channel.id, _coerce_output_value(channel, wert), now_ts)
        elif command.typ == "hand_auto":
            hand_auto.set_auto(channel.id)
        elif command.typ == "pulse" and channel.kind == "do":
            duration_ms = channel.impuls_ms or 250
            log.info("Pulse Ausgang %s (%s) fuer %sms", channel.id, channel.komponente, duration_ms)
            await io_backend.pulse(channel, duration_ms)


async def _handle_tor_command(
    app_config: AppConfig,
    io_backend: BaseIO,
    snapshot: HardwareSnapshot,
    command_name: str,
) -> None:
    links_zu = _di_value_by_component(app_config, snapshot, "tor_fluegel_links_zu", "tor_es_ganz_zu")
    rechts_zu = _di_value_by_component(app_config, snapshot, "tor_fluegel_rechts_zu", "tor_es_halb_zu")
    decision = entscheide_tor_command(command_name, links_zu, rechts_zu)
    log.info(
        "Torbefehl %s: links_zu=%s rechts_zu=%s ausgang=%s ausfuehren=%s grund=%s",
        command_name,
        links_zu,
        rechts_zu,
        decision.ausgang,
        decision.ausfuehren,
        decision.grund,
    )
    if not decision.ausfuehren or decision.ausgang is None:
        return
    channel = app_config.io_map.by_component(decision.ausgang)
    if channel is None or channel.kind != "do":
        log.warning("Torbefehl %s kann Ausgang %s nicht finden", command_name, decision.ausgang)
        return
    await io_backend.pulse(channel, channel.impuls_ms or 1000)


def _extract_hand_value(payload: Any) -> Any:
    if isinstance(payload, dict):
        if payload.get("hand") is False:
            return False
        return payload.get("wert", payload.get("value", True))
    if isinstance(payload, str):
        lowered = payload.strip().lower()
        if lowered in {"1", "true", "on", "ja"}:
            return True
        if lowered in {"0", "false", "off", "nein"}:
            return False
    return payload


def _compute_auto_outputs(
    app_config: AppConfig,
    mqtt: MqttBridge,
    snapshot: HardwareSnapshot,
    failsafe_state: FailsafeState,
    freigaben: Freigaben,
    regler: ReglerParameter,
    brauchwasser_previous_active: bool,
    brunnen_previous_active: bool,
    brunnen_previous_speed_pct: float,
    oelbrenner_previous_active: bool,
    klima_og_cooling_previous_active: bool,
    cycle_s: float = 1.0,
    brunnen_flow_l_min: float | None = None,
    brunnen_no_flow_s: float | None = None,
) -> tuple[RoutingState, BrauchwasserState, BrunnenPressureState, dict[str, bool], dict[str, float], bool, bool]:
    demands = dict(mqtt.demands)
    klima_og_cooling_active = _compute_klima_og_cooling(
        app_config,
        demands,
        snapshot,
        freigaben,
        klima_og_cooling_previous_active,
    )
    if klima_og_cooling_active:
        demands.pop("klima_og", None)
    routing_state, routed_do, routed_ao = compute_routing(
        regler.as_settings(app_config.settings),
        demands,
        failsafe_state,
        freigaben,
    )
    auto = {channel_id: False for channel_id in app_config.io_map.do}
    for channel_id, value in routed_do.items():
        if channel_id in auto:
            auto[channel_id] = value
    oelbrenner_common_active = bool(auto.get("DO01", False))
    if "DO01" in auto:
        auto["DO01"] = _compute_oelbrenner_common_heat(
            app_config,
            snapshot,
            routing_state,
            oelbrenner_common_active,
            oelbrenner_previous_active,
        )
    brauchwasser_state = compute_brauchwasser(
        app_config,
        snapshot,
        freigaben,
        regler,
        brauchwasser_previous_active,
    )
    if "DO01" in auto:
        auto["DO01"] = auto["DO01"] or brauchwasser_state.active
    if "DO02" in auto:
        auto["DO02"] = brauchwasser_state.active

    brunnen_state = compute_brunnen_pressure(
        app_config,
        snapshot,
        regler,
        brunnen_previous_active,
        brunnen_previous_speed_pct,
        cycle_s,
        brunnen_flow_l_min,
        brunnen_no_flow_s,
    )
    brunnen_do = app_config.io_map.by_component("brunnen_pumpe_freigabe")
    if brunnen_do is not None and brunnen_do.kind == "do" and brunnen_do.id in auto:
        auto[brunnen_do.id] = brunnen_state.active

    auto_ao = {channel_id: 0.0 for channel_id in app_config.io_map.ao}
    for channel_id, value in routed_ao.items():
        if channel_id in auto_ao:
            auto_ao[channel_id] = value
    brunnen_ao = app_config.io_map.by_component("brunnen_fu_soll")
    if brunnen_ao is not None and brunnen_ao.kind == "ao" and brunnen_ao.id in auto_ao:
        auto_ao[brunnen_ao.id] = brunnen_state.speed_pct
    _apply_klima_og_cooling_outputs(app_config, regler, auto, auto_ao, klima_og_cooling_active)
    return (
        routing_state,
        brauchwasser_state,
        brunnen_state,
        auto,
        auto_ao,
        bool(auto.get("DO01", False) and not brauchwasser_state.active),
        klima_og_cooling_active,
    )


def _compute_klima_og_cooling(
    app_config: AppConfig,
    demands: dict[str, Demand],
    snapshot: HardwareSnapshot,
    freigaben: Freigaben,
    previous_active: bool,
) -> bool:
    if not bool(app_config.setting("klima_og.kuehlung_enabled", False)):
        return False
    demand = demands.get("klima_og")
    if demand is None or not demand.aktiv or demand.vl_soll is None:
        return False
    if not freigaben.sink_enabled("klima_og"):
        return False
    target_vl = float(demand.vl_soll)
    if target_vl > float(app_config.setting("klima_og.kuehlung_max_vl_soll_c", 25.0)):
        return False
    actual_vl = _sensor_value_by_component(app_config, snapshot, "klima_og_vl")
    if actual_vl is None:
        actual_vl = _sensor_value_by_component(app_config, snapshot, "kuehl_vl")
    if actual_vl is None:
        return False
    hysterese_k = max(0.1, float(app_config.setting("klima_og.kuehlung_hysterese_k", 1.0)))
    if previous_active:
        return actual_vl > target_vl
    return actual_vl >= target_vl + hysterese_k


def _apply_klima_og_cooling_outputs(
    app_config: AppConfig,
    regler: ReglerParameter,
    auto_do: dict[str, bool],
    auto_ao: dict[str, float],
    active: bool,
) -> None:
    if not active:
        return
    _set_do_by_component(app_config, auto_do, "pumpe_klima_og", True)
    _set_do_by_component(app_config, auto_do, "brunnen_mv", True)
    _set_do_by_component(app_config, auto_do, "brunnen_pumpe_freigabe", True)
    _set_ao_by_component(app_config, auto_ao, "mischer_klima_og_pct", 0.0)
    brunnen_ao = app_config.io_map.by_component("brunnen_fu_soll")
    if brunnen_ao is not None and brunnen_ao.kind == "ao" and brunnen_ao.id in auto_ao and auto_ao[brunnen_ao.id] <= 0:
        auto_ao[brunnen_ao.id] = float(regler.brunnen_fu_start_pct)


def _compute_oelbrenner_common_heat(
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
    routing_state: RoutingState,
    requested: bool,
    previous_active: bool,
) -> bool:
    if not requested or routing_state.vl_soll is None:
        return False
    vl_ist = _sensor_value_by_component(app_config, snapshot, "vl_sammel")
    if vl_ist is None:
        return True
    hysterese_k = max(0.1, float(app_config.setting("regelung.oelbrenner_hysterese_k", 1.0)))
    if vl_ist >= float(routing_state.vl_soll):
        return False
    if vl_ist <= float(routing_state.vl_soll) - hysterese_k:
        return True
    return previous_active


def _compute_fast_brunnen_outputs(
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
    regler: ReglerParameter,
    brunnen_previous_active: bool,
    brunnen_previous_speed_pct: float,
    cycle_s: float,
    brunnen_flow_l_min: float | None,
    brunnen_no_flow_s: float | None,
    auto_do: dict[str, bool],
    auto_ao: dict[str, float],
    klima_og_cooling_active: bool = False,
) -> BrunnenPressureState:
    brunnen_state = compute_brunnen_pressure(
        app_config,
        snapshot,
        regler,
        brunnen_previous_active,
        brunnen_previous_speed_pct,
        cycle_s,
        brunnen_flow_l_min,
        brunnen_no_flow_s,
    )
    brunnen_do = app_config.io_map.by_component("brunnen_pumpe_freigabe")
    if brunnen_do is not None and brunnen_do.kind == "do" and brunnen_do.id in auto_do:
        auto_do[brunnen_do.id] = brunnen_state.active
    brunnen_ao = app_config.io_map.by_component("brunnen_fu_soll")
    if brunnen_ao is not None and brunnen_ao.kind == "ao" and brunnen_ao.id in auto_ao:
        auto_ao[brunnen_ao.id] = brunnen_state.speed_pct
    _apply_klima_og_cooling_outputs(app_config, regler, auto_do, auto_ao, klima_og_cooling_active)
    return brunnen_state


def _set_do_by_component(app_config: AppConfig, auto_do: dict[str, bool], component: str, value: bool) -> None:
    channel = app_config.io_map.by_component(component)
    if channel is not None and channel.kind == "do" and channel.id in auto_do:
        auto_do[channel.id] = value


def _set_ao_by_component(app_config: AppConfig, auto_ao: dict[str, float], component: str, value: float) -> None:
    channel = app_config.io_map.by_component(component)
    if channel is not None and channel.kind == "ao" and channel.id in auto_ao:
        auto_ao[channel.id] = value


def _brunnen_output_ids(app_config: AppConfig) -> set[str]:
    ids: set[str] = set()
    for component in ("brunnen_pumpe_freigabe", "brunnen_fu_soll"):
        channel = app_config.io_map.by_component(component)
        if channel is not None and channel.kind in {"do", "ao"}:
            ids.add(channel.id)
    burner = _burner_output_channel(app_config)
    if burner is not None:
        ids.add(burner.id)
    ids.update(_heating_pump_output_ids(app_config))
    return ids


async def _write_outputs(
    app_config: AppConfig,
    local_io_map: IoMap,
    io_backend: BaseIO,
    hand_auto: HandAutoManager,
    auto_do: dict[str, bool],
    auto_ao: dict[str, float],
    snapshot: HardwareSnapshot,
    now_ts: float,
    keller_client: KellerModbusClient | None = None,
    only_channel_ids: set[str] | None = None,
    keller_fallback_do: dict[str, bool] | None = None,
    keller_fallback_ao: dict[str, float] | None = None,
) -> tuple[dict[str, bool], dict[str, float]]:
    applied_do: dict[str, bool] = {}
    applied_ao: dict[str, float] = {}
    keller_do: dict[str, bool] = {}
    keller_ao: dict[str, float] = {}
    for channel_id, channel in app_config.io_map.do.items():
        if only_channel_ids is not None and channel_id not in only_channel_ids:
            continue
        value, _hand = hand_auto.apply(channel, auto_do.get(channel_id, False), now_ts)
        applied_do[channel_id] = bool(value)
        if _is_hard_locked_burner_output(channel, app_config, snapshot):
            applied_do[channel_id] = False
        if _is_hard_locked_heating_pump_output(channel, app_config, snapshot):
            applied_do[channel_id] = False
        if channel_id in local_io_map.do:
            await io_backend.write_do(channel, applied_do[channel_id])
        else:
            keller_do[channel_id] = applied_do[channel_id]

    for channel_id, channel in app_config.io_map.ao.items():
        if only_channel_ids is not None and channel_id not in only_channel_ids:
            continue
        value, _hand = hand_auto.apply(channel, auto_ao.get(channel_id, 0.0), now_ts)
        applied_ao[channel_id] = float(value)
        if channel_id in local_io_map.ao:
            await io_backend.write_ao(channel, applied_ao[channel_id])
        else:
            keller_ao[channel_id] = applied_ao[channel_id]

    if keller_client is not None and (keller_do or keller_ao):
        for channel_id in keller_client.io_map.do:
            keller_do.setdefault(channel_id, (keller_fallback_do or {}).get(channel_id, auto_do.get(channel_id, False)))
        for channel_id in keller_client.io_map.ao:
            keller_ao.setdefault(channel_id, (keller_fallback_ao or {}).get(channel_id, auto_ao.get(channel_id, 0.0)))
        try:
            await keller_client.write_outputs(keller_do, keller_ao, enabled=True)
        except Exception as exc:
            log.warning("Keller-Slave Modbus Schreiben fehlgeschlagen: %s", exc)
    return applied_do, applied_ao


def _is_hard_locked_burner_output(
    channel: ChannelConfig,
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
) -> bool:
    burner = _burner_output_channel(app_config)
    if burner is None or channel.id != burner.id:
        return False
    return bool(_oelbrenner_hard_safety_reasons(app_config, snapshot))


def _is_hard_locked_heating_pump_output(
    channel: ChannelConfig,
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
) -> bool:
    if channel.kind != "do" or channel.id not in _heating_pump_output_ids(app_config):
        return False
    return _oelbrenner_water_shortage_active(app_config, snapshot)


def _burner_output_channel(app_config: AppConfig) -> ChannelConfig | None:
    for component in ("brenner", "olbrenner_freigabe", "oelbrenner_freigabe"):
        channel = app_config.io_map.by_component(component)
        if channel is not None and channel.kind == "do":
            return channel
    return None


def _oelbrenner_safety_reasons(app_config: AppConfig, snapshot: HardwareSnapshot) -> tuple[str, ...]:
    reasons = list(_oelbrenner_hard_safety_reasons(app_config, snapshot))
    if _oelbrenner_fault_active(app_config, snapshot):
        reasons.append("stoermeldung")
    return tuple(reasons)


def _oelbrenner_hard_safety_reasons(app_config: AppConfig, snapshot: HardwareSnapshot) -> tuple[str, ...]:
    checks = (
        ("oelbrenner_wasserdruck_stoerung", True, "wasserdruck"),
        ("oelbrenner_stb_stoerung", True, "stb"),
    )
    reasons: list[str] = []
    for component, nc_safe_high, reason in checks:
        value = _di_value_by_component(app_config, snapshot, component)
        if value is None:
            continue
        if nc_safe_high:
            if not value:
                reasons.append(reason)
        elif value:
            reasons.append(reason)
    return tuple(reasons)


def _oelbrenner_fault_active(app_config: AppConfig, snapshot: HardwareSnapshot) -> bool:
    return _di_value_by_component(app_config, snapshot, "brenner_stoerung") is True


def _oelbrenner_water_shortage_active(app_config: AppConfig, snapshot: HardwareSnapshot) -> bool:
    value = _di_value_by_component(app_config, snapshot, "oelbrenner_wasserdruck_stoerung")
    return value is False


def _heating_pump_output_ids(app_config: AppConfig) -> set[str]:
    components = {
        "pumpe_bw_lade",
        "pumpe_nebengeb",
        "pumpe_pool",
        "pumpe_fbh_eg",
        "pumpe_klima_og",
        "pumpe_hk_backup",
    }
    ids: set[str] = set()
    for channel in app_config.io_map.do.values():
        if channel.komponente in components:
            ids.add(channel.id)
    return ids


def _publish_state(
    mqtt: MqttBridge,
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
    failsafe_state: FailsafeState,
    hand_auto: HandAutoManager,
    freigaben: Freigaben,
    regler: ReglerParameter,
    routing_state: RoutingState,
    brauchwasser_state: BrauchwasserState,
    brunnen_state: BrunnenPressureState,
    applied_do: dict[str, bool],
    applied_ao: dict[str, float],
    klima_og_cooling_active: bool = False,
) -> None:
    base = mqtt.base
    mqtt.publish(f"{base}/failsafe/active", "1" if failsafe_state.active else "0", retain=True)
    mqtt.publish(f"{base}/failsafe/grund", ",".join(failsafe_state.reasons), retain=True)
    if failsafe_state.vl_soll is not None:
        mqtt.publish(f"{base}/vl_soll/state", f"{failsafe_state.vl_soll:.1f}", retain=True)
    if routing_state.vl_soll is not None:
        mqtt.publish(f"{base}/gesamt/vl_soll/state", f"{routing_state.vl_soll:.1f}", retain=True)
    mqtt.publish(f"{base}/gesamt/active", "1" if routing_state.common_active else "0", retain=True)
    mqtt.publish_json(f"{base}/routing/state", routing_state.as_payload(), retain=True)
    mqtt.publish(f"{base}/brauchwasser/ladung_aktiv", "1" if brauchwasser_state.active else "0", retain=True)
    mqtt.publish(f"{base}/brauchwasser/grund", brauchwasser_state.reason, retain=True)
    mqtt.publish_json(f"{base}/brauchwasser/state", brauchwasser_state.as_payload(), retain=True)
    mqtt.publish(f"{base}/klima_og/kuehlung_aktiv", "1" if klima_og_cooling_active else "0", retain=True)
    oelbrenner_safety_reasons = _oelbrenner_safety_reasons(app_config, snapshot)
    mqtt.publish(f"{base}/oelbrenner/sicherheit/ok", "0" if oelbrenner_safety_reasons else "1", retain=True)
    mqtt.publish(f"{base}/oelbrenner/sicherheit/grund", ",".join(oelbrenner_safety_reasons), retain=True)
    mqtt.publish(f"{base}/brunnen/active", "1" if brunnen_state.active else "0", retain=True)
    mqtt.publish(f"{base}/brunnen/grund", brunnen_state.reason, retain=True)
    mqtt.publish(f"{base}/brunnen/druck_bar/state", "" if brunnen_state.pressure_bar is None else f"{brunnen_state.pressure_bar:.2f}", retain=True)
    mqtt.publish(f"{base}/brunnen/fu_soll_pct/state", f"{brunnen_state.speed_pct:.1f}", retain=True)
    mqtt.publish(
        f"{base}/brunnen/fluss_l_min/state",
        "" if brunnen_state.flow_l_min is None else f"{brunnen_state.flow_l_min:.2f}",
        retain=True,
    )
    mqtt.publish(
        f"{base}/brunnen/kein_durchfluss_s/state",
        "0" if brunnen_state.no_flow_s is None else f"{brunnen_state.no_flow_s:.0f}",
        retain=True,
    )
    mqtt.publish(
        f"{base}/brunnen/abschaltung_in_s/state",
        "0" if brunnen_state.flow_shutdown_remaining_s is None else f"{brunnen_state.flow_shutdown_remaining_s:.0f}",
        retain=True,
    )
    mqtt.publish_json(f"{base}/brunnen/state", brunnen_state.as_payload(), retain=True)
    for name, active in sorted(mqtt.pv.items()):
        mqtt.publish(f"{base}/pv/{name}/state", "1" if active else "0", retain=True)
    mqtt.publish_json(f"{base}/freigabe/state", freigaben.snapshot(), retain=True)
    mqtt.publish_json(f"{base}/regler/state", regler.snapshot(), retain=True)
    for name, value in regler.snapshot().items():
        mqtt.publish(f"{base}/regler/{name}/state", str(value), retain=True)

    for name, enabled in freigaben.sources.items():
        mqtt.publish(f"{base}/freigabe/quellen/{name}/state", "1" if enabled else "0", retain=True)
    for name, enabled in freigaben.sinks.items():
        mqtt.publish(f"{base}/freigabe/senken/{name}/state", "1" if enabled else "0", retain=True)

    for name, demand in mqtt.demands.items():
        mqtt.publish_json(
            f"{base}/anforderung/{name}/aktuell",
            {"aktiv": demand.aktiv, "vl_soll": demand.vl_soll, "quelle": demand.quelle},
            retain=True,
        )
        mqtt.publish(f"{base}/anforderung/{name}/aktiv/state", "1" if demand.aktiv else "0", retain=True)
        if demand.vl_soll is not None:
            mqtt.publish(f"{base}/anforderung/{name}/vl_soll/state", f"{demand.vl_soll:.1f}", retain=True)

    for channel_id, channel in app_config.io_map.ai.items():
        value = snapshot.ai.get(channel_id)
        if value is not None and _is_temperature_channel(channel):
            _publish_temperature(mqtt, f"{base}/temp/{channel.komponente}/state", value)

    for channel_id, channel in app_config.io_map.rtd.items():
        value = snapshot.rtd.get(channel_id)
        if value is not None:
            _publish_temperature(mqtt, f"{base}/temp/{channel.komponente}/state", value)

    for channel_id, channel in app_config.io_map.di.items():
        value = snapshot.di.get(channel_id)
        if value is not None:
            mqtt.publish(f"{base}/di/{channel.komponente}/state", "1" if value else "0")

    mqtt.publish_json(f"{base}/hand/state", hand_auto.snapshot(), retain=True)
    hand_snapshot = hand_auto.snapshot()
    for channel_id, channel in app_config.io_map.do.items():
        value = applied_do.get(channel_id, False)
        hand = hand_snapshot.get(channel_id)
        mqtt.publish(f"{base}/do/{channel.komponente}/state", "1" if value else "0", retain=True)
        mqtt.publish(f"{base}/{channel.komponente}/hand/mode/state", "1" if hand else "0", retain=True)
        mqtt.publish(f"{base}/{channel.komponente}/hand/value/state", "1" if (hand or {}).get("wert") else "0", retain=True)
    for channel_id, channel in app_config.io_map.ao.items():
        value = applied_ao.get(channel_id, 0.0)
        hand = hand_snapshot.get(channel_id)
        mqtt.publish(f"{base}/ao/{channel.komponente}/state", f"{value:.1f}", retain=True)
        mqtt.publish(f"{base}/{channel.komponente}/hand/mode/state", "1" if hand else "0", retain=True)
        mqtt.publish(f"{base}/{channel.komponente}/hand/value/state", str((hand or {}).get("wert", 0.0)), retain=True)


def _publish_ha_discovery(mqtt: MqttBridge, app_config: AppConfig) -> None:
    discovery = app_config.mqtt.get("ha_discovery", {})
    if discovery.get("enabled", True) is False:
        return
    prefix = str(discovery.get("prefix", "homeassistant")).strip("/")
    device = discovery.get("device", {})
    if not isinstance(device, dict):
        device = {}
    device_payload = {
        "identifiers": device.get("identifiers", ["heizung-haupt"]),
        "name": device.get("name", "Heizung Hauptsteuerung"),
        "model": device.get("model", "RevPi Connect 4"),
        "manufacturer": device.get("manufacturer", "Freezweb"),
        "sw_version": device.get("sw_version", "0.0.1"),
    }

    for regler_number in _regler_number_definitions():
        _publish_discovery_entity(
            mqtt,
            prefix,
            "number",
            regler_number["object_name"],
            {
                "name": regler_number["name"],
                "state_topic": f"{mqtt.base}/regler/{regler_number['key']}/state",
                "command_topic": f"{mqtt.base}/regler/{regler_number['key']}/set",
                "min": regler_number["min"],
                "max": regler_number["max"],
                "step": regler_number["step"],
                "mode": "box",
                "unit_of_measurement": regler_number["unit"],
                "device": device_payload,
            },
        )

    for sensor in _brunnen_sensor_definitions(mqtt.base):
        _publish_discovery_entity(
            mqtt,
            prefix,
            "sensor",
            sensor["object_name"],
            {
                "name": sensor["name"],
                "state_topic": sensor["state_topic"],
                "unit_of_measurement": sensor["unit"],
                "state_class": "measurement",
                "device": device_payload,
            },
        )

    for channel in list(app_config.io_map.rtd.values()) + [
        channel for channel in app_config.io_map.ai.values() if _is_temperature_channel(channel)
    ]:
        _publish_discovery_entity(
            mqtt,
            prefix,
            "sensor",
            f"temp_{channel.komponente}",
            {
                "name": _display_name(channel),
                "state_topic": f"{mqtt.base}/temp/{channel.komponente}/state",
                "availability_topic": f"{mqtt.base}/temp/{channel.komponente}/availability",
                "payload_available": "online",
                "payload_not_available": "offline",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
                "state_class": "measurement",
                "device": device_payload,
            },
        )

    _publish_discovery_entity(
        mqtt,
        prefix,
        "binary_sensor",
        "klima_og_kuehlung_aktiv",
        {
            "name": "Klima OG Kuehlung aktiv",
            "state_topic": f"{mqtt.base}/klima_og/kuehlung_aktiv",
            "payload_on": "1",
            "payload_off": "0",
            "device": device_payload,
        },
    )

    for demand in _demand_discovery_definitions(mqtt.base, app_config.setting("anforderungen", {})):
        _publish_discovery_entity(
            mqtt,
            prefix,
            "switch",
            demand["switch_object_name"],
            {
                "name": demand["switch_name"],
                "state_topic": demand["active_state_topic"],
                "command_topic": demand["active_command_topic"],
                "payload_on": "1",
                "payload_off": "0",
                "state_on": "1",
                "state_off": "0",
                "device": device_payload,
            },
        )
        _publish_discovery_entity(
            mqtt,
            prefix,
            "number",
            demand["number_object_name"],
            {
                "name": demand["number_name"],
                "state_topic": demand["vl_state_topic"],
                "command_topic": demand["vl_command_topic"],
                "min": demand["min"],
                "max": demand["max"],
                "step": 0.5,
                "mode": "box",
                "unit_of_measurement": "C",
                "device_class": "temperature",
                "device": device_payload,
            },
        )

    for channel in app_config.io_map.do.values():
        _publish_discovery_entity(
            mqtt,
            prefix,
            "binary_sensor",
            f"ausgang_{channel.komponente}",
            {
                "name": f"Ausgang {_display_name(channel)}",
                "state_topic": f"{mqtt.base}/do/{channel.komponente}/state",
                "payload_on": "1",
                "payload_off": "0",
                "device": device_payload,
            },
        )
        _publish_discovery_entity(
            mqtt,
            prefix,
            "binary_sensor",
            f"hand_aktiv_{channel.komponente}",
            {
                "name": f"Hand aktiv {_display_name(channel)}",
                "state_topic": f"{mqtt.base}/{channel.komponente}/hand/mode/state",
                "payload_on": "1",
                "payload_off": "0",
                "device": device_payload,
            },
        )
        _publish_discovery_entity(
            mqtt,
            prefix,
            "switch",
            f"handwert_{channel.komponente}",
            {
                "name": f"Handwert {_display_name(channel)}",
                "state_topic": f"{mqtt.base}/{channel.komponente}/hand/value/state",
                "command_topic": f"{mqtt.base}/{channel.komponente}/hand/set",
                "payload_on": "1",
                "payload_off": "0",
                "state_on": "1",
                "state_off": "0",
                "device": device_payload,
            },
        )
        _publish_discovery_entity(
            mqtt,
            prefix,
            "button",
            f"auto_{channel.komponente}",
            {
                "name": f"Auto {_display_name(channel)}",
                "command_topic": f"{mqtt.base}/{channel.komponente}/hand/auto",
                "payload_press": "1",
                "device": device_payload,
            },
        )

    for channel in app_config.io_map.ao.values():
        unit = channel.einheit or "%"
        low, high = channel.bereich or (0.0, 100.0)
        _publish_discovery_entity(
            mqtt,
            prefix,
            "sensor",
            f"ausgang_{channel.komponente}",
            {
                "name": f"Ausgang {_display_name(channel)}",
                "state_topic": f"{mqtt.base}/ao/{channel.komponente}/state",
                "unit_of_measurement": unit,
                "state_class": "measurement",
                "device": device_payload,
            },
        )
        _publish_discovery_entity(
            mqtt,
            prefix,
            "binary_sensor",
            f"hand_aktiv_{channel.komponente}",
            {
                "name": f"Hand aktiv {_display_name(channel)}",
                "state_topic": f"{mqtt.base}/{channel.komponente}/hand/mode/state",
                "payload_on": "1",
                "payload_off": "0",
                "device": device_payload,
            },
        )
        _publish_discovery_entity(
            mqtt,
            prefix,
            "number",
            f"handwert_{channel.komponente}",
            {
                "name": f"Handwert {_display_name(channel)}",
                "state_topic": f"{mqtt.base}/{channel.komponente}/hand/value/state",
                "command_topic": f"{mqtt.base}/{channel.komponente}/hand/set",
                "min": low,
                "max": high,
                "step": 0.1,
                "mode": "box",
                "unit_of_measurement": unit,
                "device": device_payload,
            },
        )
        _publish_discovery_entity(
            mqtt,
            prefix,
            "button",
            f"auto_{channel.komponente}",
            {
                "name": f"Auto {_display_name(channel)}",
                "command_topic": f"{mqtt.base}/{channel.komponente}/hand/auto",
                "payload_press": "1",
                "device": device_payload,
            },
        )

    for channel in app_config.io_map.di.values():
        payload_on = "0" if channel.polaritaet == "NC_SAFE_HIGH" else "1"
        payload_off = "1" if channel.polaritaet == "NC_SAFE_HIGH" else "0"
        payload: dict[str, Any] = {
            "name": _display_name(channel),
            "state_topic": f"{mqtt.base}/di/{channel.komponente}/state",
            "payload_on": payload_on,
            "payload_off": payload_off,
            "device": device_payload,
        }
        if "stoerung" in channel.komponente:
            payload["device_class"] = "problem"
        elif channel.polaritaet == "NC_SAFE_HIGH":
            payload["device_class"] = "safety"
        _publish_discovery_entity(
            mqtt,
            prefix,
            "binary_sensor",
            channel.komponente,
            payload,
        )
    log.info("Home-Assistant MQTT-Discovery publiziert")


def _publish_discovery_entity(
    mqtt: MqttBridge,
    prefix: str,
    component: str,
    object_name: str,
    payload: dict[str, Any],
) -> None:
    unique_id = f"heizung_hauptsteuerung_{object_name}"
    entity_payload = {
        **payload,
        "unique_id": unique_id,
        "object_id": unique_id,
    }
    if "availability" not in entity_payload and "availability_topic" not in entity_payload:
        entity_payload.update(
            {
                "availability_topic": f"{mqtt.base}/status",
                "payload_available": "online",
                "payload_not_available": "offline",
            }
        )
    mqtt.publish_json(f"{prefix}/{component}/{unique_id}/config", entity_payload, retain=True)


def _brunnen_sensor_definitions(base: str) -> list[dict[str, str]]:
    return [
        {
            "object_name": "brunnen_fluss",
            "name": "Brunnen Fluss",
            "state_topic": f"{base}/brunnen/fluss_l_min/state",
            "unit": "L/min",
        },
        {
            "object_name": "brunnen_kein_durchfluss",
            "name": "Brunnen kein Durchfluss",
            "state_topic": f"{base}/brunnen/kein_durchfluss_s/state",
            "unit": "s",
        },
        {
            "object_name": "brunnen_abschaltung_in",
            "name": "Brunnen Abschaltung in",
            "state_topic": f"{base}/brunnen/abschaltung_in_s/state",
            "unit": "s",
        },
    ]


def _demand_discovery_definitions(base: str, demand_settings: dict[str, Any]) -> list[dict[str, Any]]:
    object_names = {
        "fbh_eg": "fbh_eg",
        "klima_og": "klima_og",
        "nebengeb": "nebengebaeude",
        "hk_backup": "hk_backup",
        "pool": "pool",
        "bwwp": "bwwp",
    }
    display_names = {
        "fbh_eg": "FBH EG",
        "klima_og": "Klima OG",
        "nebengeb": "Nebengebaeude",
        "hk_backup": "HK Backup",
        "pool": "Pool",
        "bwwp": "BWWP",
    }
    ranges = {
        "klima_og": (7, 55),
        "pool": (20, 45),
        "bwwp": (40, 65),
    }
    definitions: list[dict[str, Any]] = []
    for name in demand_settings:
        object_name = object_names.get(name, name)
        display_name = display_names.get(name, name.replace("_", " ").title())
        low, high = ranges.get(name, (20, 55))
        definitions.append(
            {
                "switch_object_name": f"anforderung_{object_name}",
                "number_object_name": f"vl_soll_{object_name}",
                "switch_name": f"Anforderung {display_name}",
                "number_name": f"VL Soll {display_name}",
                "active_state_topic": f"{base}/anforderung/{name}/aktiv/state",
                "active_command_topic": f"{base}/anforderung/{name}/aktiv/set",
                "vl_state_topic": f"{base}/anforderung/{name}/vl_soll/state",
                "vl_command_topic": f"{base}/anforderung/{name}/vl_soll/set",
                "min": low,
                "max": high,
            }
        )
    return definitions


def _regler_number_definitions() -> list[dict[str, Any]]:
    return [
        {
            "key": "mischer_reserve_k",
            "object_name": "mischer_reserve_k",
            "name": "Mischer Reserve K",
            "min": 0,
            "max": 15,
            "step": 0.5,
            "unit": "K",
        },
        {
            "key": "wp_parallel_ab_aktive_kreise",
            "object_name": "wp_parallel_ab_aktive_kreise",
            "name": "WP parallel ab aktive Kreise",
            "min": 1,
            "max": 10,
            "step": 1,
            "unit": "",
        },
        {
            "key": "brauchwasser_soll_c",
            "object_name": "brauchwasser_soll_c",
            "name": "Brauchwasser Soll C",
            "min": 30,
            "max": 70,
            "step": 0.5,
            "unit": "C",
        },
        {
            "key": "brauchwasser_hysterese_k",
            "object_name": "brauchwasser_hysterese_k",
            "name": "Brauchwasser Hysterese K",
            "min": 1,
            "max": 20,
            "step": 0.5,
            "unit": "K",
        },
        {
            "key": "brunnen_min_druck_bar",
            "object_name": "brunnen_min_druck",
            "name": "Brunnen Min Druck",
            "min": 0,
            "max": 9.5,
            "step": 0.1,
            "unit": "bar",
        },
        {
            "key": "brunnen_max_druck_bar",
            "object_name": "brunnen_max_druck",
            "name": "Brunnen Max Druck",
            "min": 0.2,
            "max": 10,
            "step": 0.1,
            "unit": "bar",
        },
        {
            "key": "brunnen_regeldruck_bar",
            "object_name": "brunnen_regeldruck",
            "name": "Brunnen Regeldruck",
            "min": 0,
            "max": 10,
            "step": 0.1,
            "unit": "bar",
        },
        {
            "key": "brunnen_fu_start_pct",
            "object_name": "brunnen_fu_start",
            "name": "Brunnen FU Start",
            "min": 0,
            "max": 100,
            "step": 1,
            "unit": "%",
        },
        {
            "key": "brunnen_fu_max_pct",
            "object_name": "brunnen_fu_max",
            "name": "Brunnen FU Max",
            "min": 0,
            "max": 100,
            "step": 1,
            "unit": "%",
        },
        {
            "key": "brunnen_kp_pct_pro_bar",
            "object_name": "brunnen_kp",
            "name": "Brunnen Kp",
            "min": 0,
            "max": 200,
            "step": 1,
            "unit": "%/bar",
        },
        {
            "key": "brunnen_fu_ramp_up_pct_s",
            "object_name": "brunnen_fu_rampe_hoch",
            "name": "Brunnen FU Rampe hoch",
            "min": 1,
            "max": 500,
            "step": 5,
            "unit": "%/s",
        },
        {
            "key": "brunnen_fu_ramp_down_pct_s",
            "object_name": "brunnen_fu_rampe_runter",
            "name": "Brunnen FU Rampe runter",
            "min": 1,
            "max": 1000,
            "step": 5,
            "unit": "%/s",
        },
        {
            "key": "brunnen_flow_min_l_min",
            "object_name": "brunnen_flow_min",
            "name": "Brunnen Flow Min",
            "min": 0,
            "max": 20,
            "step": 0.1,
            "unit": "L/min",
        },
        {
            "key": "brunnen_flow_timeout_s",
            "object_name": "brunnen_flow_timeout",
            "name": "Brunnen Flow Timeout",
            "min": 10,
            "max": 1800,
            "step": 10,
            "unit": "s",
        },
        {
            "key": "brunnen_flow_stop_tolerance_bar",
            "object_name": "brunnen_flow_stop_toleranz",
            "name": "Brunnen Flow Stop Toleranz",
            "min": 0,
            "max": 2,
            "step": 0.1,
            "unit": "bar",
        },
    ]


def _display_name(channel: ChannelConfig) -> str:
    if channel.beschreibung:
        return channel.beschreibung
    return channel.komponente.replace("_", " ").title()


def _publish_temperature(mqtt: MqttBridge, topic: str, value: float | None) -> None:
    if value is None or _is_missing_temperature(value):
        mqtt.publish(_temperature_availability_topic(topic), "offline", retain=True)
        mqtt.publish(topic, "", retain=True)
        return
    mqtt.publish(_temperature_availability_topic(topic), "online", retain=True)
    mqtt.publish(topic, f"{value:.1f}", retain=True)


def _temperature_availability_topic(topic: str) -> str:
    if topic.endswith("/state"):
        return f"{topic[:-len('/state')]}/availability"
    return f"{topic}/availability"


def _is_temperature_channel(channel: ChannelConfig) -> bool:
    unit = str(channel.einheit or "").strip().lower()
    sensor = str(channel.sensor or "").strip().lower()
    return channel.kind == "rtd" or unit in {"c", "°c", "grad c"} or "temperatur" in sensor or "pt100" in sensor


def _is_missing_temperature(value: float) -> bool:
    return abs(float(value)) >= 800.0


def _coerce_output_value(channel: ChannelConfig, value: Any) -> Any:
    if channel.kind == "do":
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "on", "ja"}
        return bool(value)
    if isinstance(value, str):
        value = value.replace(",", ".")
    return float(value)


def _extract_bool(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key in ("enabled", "freigabe", "aktiv", "value", "state"):
            if key in payload:
                return _extract_bool(payload[key])
        return bool(payload)
    if isinstance(payload, str):
        return payload.strip().lower() in {"1", "true", "on", "yes", "ja", "ein"}
    return bool(payload)


def _sensor_value_by_component(app_config: AppConfig, snapshot: HardwareSnapshot, component: str) -> float | None:
    for channel_id, channel in app_config.io_map.rtd.items():
        if channel.komponente == component:
            value = snapshot.rtd.get(channel_id)
            return None if value is None or _is_missing_temperature(value) else value
    for channel_id, channel in app_config.io_map.ai.items():
        if channel.komponente == component:
            value = snapshot.ai.get(channel_id)
            return None if value is None or (_is_temperature_channel(channel) and _is_missing_temperature(value)) else value
    return None


def _di_value_by_component(app_config: AppConfig, snapshot: HardwareSnapshot, *components: str) -> bool | None:
    for channel_id, channel in app_config.io_map.di.items():
        if channel.komponente in components:
            return snapshot.di.get(channel_id)
    return None


def _apply_log_level(level_name: str) -> None:
    level = getattr(logging, str(level_name).upper(), logging.INFO)
    logging.getLogger().setLevel(level)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
