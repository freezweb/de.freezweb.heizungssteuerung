"""Heizungssteuerung Hauptprogramm."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from typing import Any

from .lib.brauchwasser import BrauchwasserState, compute_brauchwasser
from .lib.config import AppConfig, ChannelConfig, ConfigError
from .lib.failsafe import FailsafeMonitor, FailsafeState
from .lib.freigaben import Freigaben
from .lib.hand_auto import HandAutoManager
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
    cycle_s = float(app_config.setting("regelung.zyklus_ms", 1000)) / 1000
    default_hand_timeout = app_config.setting("hand.default_timeout_min")
    hand_state_path = app_config.state_path(app_config.setting("hand.state_persist_path", "state/hand_state.json"))
    freigaben_state_path = app_config.state_path(app_config.setting("freigaben.state_persist_path", "state/freigaben.json"))
    regler_state_path = app_config.state_path(app_config.setting("regler.state_persist_path", "state/regler.json"))

    io_backend = create_io_backend(app_config.io_map, os.environ.get("HEIZUNG_IO_BACKEND", "auto"))
    hand_auto = HandAutoManager(app_config.io_map, StateStore(hand_state_path), default_hand_timeout)
    freigaben = Freigaben.from_settings(app_config.settings, StateStore(freigaben_state_path))
    regler = ReglerParameter.from_settings(app_config.settings, StateStore(regler_state_path))
    failsafe_monitor = FailsafeMonitor.from_settings(app_config.settings)
    mqtt = MqttBridge(app_config.mqtt)
    mqtt.set_default_demands(app_config.setting("anforderungen", {}))
    mqtt.start()

    log.info("Heizungssteuerung gestartet, Zyklus %.3fs", cycle_s)
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
    brauchwasser_ladung_active = False
    try:
        while not stop.is_set():
            started = time.monotonic()
            now_ts = time.time()

            snapshot = await io_backend.read_all()
            await _handle_mqtt_commands(
                mqtt,
                app_config,
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
                outside_temp_c=_sensor_value_by_component(app_config, snapshot, "aussen"),
            )

            routing_state, brauchwasser_state, auto_do, auto_ao = _compute_auto_outputs(
                app_config,
                mqtt,
                snapshot,
                failsafe_state,
                freigaben,
                regler,
                brauchwasser_ladung_active,
            )
            brauchwasser_ladung_active = brauchwasser_state.active
            applied_do, applied_ao = await _write_outputs(app_config, io_backend, hand_auto, auto_do, auto_ao, now_ts)

            _publish_state(
                mqtt,
                app_config,
                snapshot,
                failsafe_state,
                hand_auto,
                freigaben,
                regler,
                routing_state,
                brauchwasser_state,
                applied_do,
                applied_ao,
            )
            uptime_s = int(now_ts - boot_ts)
            heartbeat_tick = uptime_s // 30
            if heartbeat_tick != last_heartbeat_tick:
                last_heartbeat_tick = heartbeat_tick
                mqtt.publish_heartbeat(uptime_s)

            await _sleep_remaining(stop, cycle_s, started)
    finally:
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
) -> tuple[RoutingState, BrauchwasserState, dict[str, bool], dict[str, float]]:
    routing_state, routed_do, routed_ao = compute_routing(
        regler.as_settings(app_config.settings),
        mqtt.demands,
        failsafe_state,
        freigaben,
    )
    auto = {channel_id: False for channel_id in app_config.io_map.do}
    for channel_id, value in routed_do.items():
        if channel_id in auto:
            auto[channel_id] = value
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
    auto_ao = {channel_id: 0.0 for channel_id in app_config.io_map.ao}
    for channel_id, value in routed_ao.items():
        if channel_id in auto_ao:
            auto_ao[channel_id] = value
    return routing_state, brauchwasser_state, auto, auto_ao


async def _write_outputs(
    app_config: AppConfig,
    io_backend: BaseIO,
    hand_auto: HandAutoManager,
    auto_do: dict[str, bool],
    auto_ao: dict[str, float],
    now_ts: float,
) -> tuple[dict[str, bool], dict[str, float]]:
    applied_do: dict[str, bool] = {}
    applied_ao: dict[str, float] = {}
    for channel_id, channel in app_config.io_map.do.items():
        value, _hand = hand_auto.apply(channel, auto_do.get(channel_id, False), now_ts)
        applied_do[channel_id] = bool(value)
        await io_backend.write_do(channel, applied_do[channel_id])

    for channel_id, channel in app_config.io_map.ao.items():
        value, _hand = hand_auto.apply(channel, auto_ao.get(channel_id, 0.0), now_ts)
        applied_ao[channel_id] = float(value)
        await io_backend.write_ao(channel, applied_ao[channel_id])
    return applied_do, applied_ao


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
    applied_do: dict[str, bool],
    applied_ao: dict[str, float],
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
        if value is not None:
            mqtt.publish(f"{base}/temp/{channel.komponente}/state", f"{value:.1f}")

    for channel_id, channel in app_config.io_map.rtd.items():
        value = snapshot.rtd.get(channel_id)
        if value is not None:
            mqtt.publish(f"{base}/temp/{channel.komponente}/state", f"{value:.1f}")

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
            return snapshot.rtd.get(channel_id)
    for channel_id, channel in app_config.io_map.ai.items():
        if channel.komponente == component:
            return snapshot.ai.get(channel_id)
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
