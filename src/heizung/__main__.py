"""Heizungssteuerung Hauptprogramm."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from .lib.brauchwasser import BrauchwasserState, compute_brauchwasser
from .lib.brunnen import BrunnenPressureState, brunnen_flow_timer_armed, compute_brunnen_pressure
from .lib.config import AppConfig, ChannelConfig, ConfigError, IoMap, load_yaml, resolve_config_file
from .lib.failsafe import FailsafeMonitor, FailsafeState
from .lib.flowmeter import (
    FlowmeterModbusClient,
    FlowmeterModbusConfig,
    WatermeterHttpClient,
    WatermeterHttpConfig,
    WatermeterHttpSnapshot,
)
from .lib.freigaben import Freigaben
from .lib.hand_auto import HandAutoManager
from .lib.intercpu import KellerModbusClient
from .lib.iohw import BaseIO, HardwareSnapshot, create_io_backend
from .lib.keller_relais import KellerRelayClient, KellerRelayConfig, RelayGroupConfig, relay_component_names
from .lib.mqtt_bridge import MqttBridge
from .lib.oelverbrauch import DieselPriceClient, OelverbrauchConfig, OelverbrauchSnapshot, OelverbrauchTracker
from .lib.pool import PoolController, PoolControlState, PoolProdinoConfig
from .lib.prodino_modbus import ProdinoPoolModbusClient, ProdinoPoolSnapshot
from .lib.pumpengruppe import (
    PumpGroupModbusClient,
    PumpGroupSnapshot,
    pump_group_configs_from_settings,
)
from .lib.regler import ReglerParameter
from .lib.routing import RoutingState, compute_routing
from .lib.state import StateStore
from .lib.tor import TorRuntime

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
    keller_relay_config = KellerRelayConfig.from_settings(app_config.settings)
    pool_prodino_config = PoolProdinoConfig.from_settings(app_config.settings, app_config.mqtt.get("topics", {}).get("base", "heizung"))
    oelverbrauch_config = OelverbrauchConfig.from_settings(app_config.settings)

    keller_client: KellerModbusClient | None = None
    keller_relay_client: KellerRelayClient | None = None
    pool_prodino_client: ProdinoPoolModbusClient | None = None
    controller_config = app_config
    keller_io_map = (
        _load_keller_io_map(app_config)
        if _controller_role(app_config) == "haupt"
        else None
    )
    if keller_io_map is not None and bool(app_config.setting("intercpu.keller.enabled", True)):
        host = str(app_config.setting("intercpu.keller.host", "10.1.25.11"))
        port = int(app_config.setting("intercpu.keller.port", 502))
        timeout_s = float(app_config.setting("intercpu.keller.timeout_s", 1.0))
        keller_client = KellerModbusClient(host, port, keller_io_map, timeout_s=timeout_s)
        controller_config = replace(app_config, io_map=_merge_io_maps(app_config.io_map, keller_io_map))
        log.info("Keller-Slave per Modbus aktiviert: %s:%s", host, port)
    if _controller_role(app_config) == "haupt" and keller_relay_config.enabled:
        keller_relay_io_map = _load_optional_io_map(app_config, "io_map.keller_relais.yaml")
        if keller_relay_io_map is not None:
            controller_config = replace(controller_config, io_map=_merge_io_maps(controller_config.io_map, keller_relay_io_map))
        keller_relay_client = KellerRelayClient(
            keller_relay_config,
            StateStore(app_config.state_path(keller_relay_config.state_persist_path)),
        )
        log.info(
            "Keller-R421B16 Relais aktiviert: %s:%s Unit %s",
            keller_relay_config.host,
            keller_relay_config.port,
            keller_relay_config.unit_id,
        )
    if _controller_role(app_config) == "haupt" and pool_prodino_config.enabled:
        pool_io_map = _load_optional_io_map(app_config, "io_map.pool_prodino.yaml")
        if pool_io_map is not None:
            controller_config = replace(controller_config, io_map=_merge_io_maps(controller_config.io_map, pool_io_map))
        if pool_prodino_config.protocol in {"modbus_tcp", "modbus"}:
            pool_prodino_client = ProdinoPoolModbusClient(pool_prodino_config)
            log.info(
                "Pool-Prodino Modbus TCP aktiviert: %s:%s Unit %s",
                pool_prodino_config.host,
                pool_prodino_config.port,
                pool_prodino_config.unit_id,
            )
        else:
            log.info("Pool-Prodino MQTT aktiviert: %s", pool_prodino_config.topic_base)

    io_backend = create_io_backend(app_config.io_map, os.environ.get("HEIZUNG_IO_BACKEND", "auto"))
    hand_auto = HandAutoManager(controller_config.io_map, StateStore(hand_state_path), default_hand_timeout)
    freigaben = Freigaben.from_settings(app_config.settings, StateStore(freigaben_state_path))
    regler = ReglerParameter.from_settings(app_config.settings, StateStore(regler_state_path))
    tor_runtime = TorRuntime(
        StateStore(app_config.state_path(app_config.setting("tor.state_persist_path", "state/tor.json"))),
        fahrzeit_s=float(app_config.setting("tor.fahrzeit_s", 30)),
        initial_position=str(app_config.setting("tor.initial_position", "geschlossen")),
        halb_aktiv=bool(app_config.setting("tor.halb_aktiv", False)),
    )
    pool_controller = (
        PoolController(
            pool_prodino_config,
            StateStore(app_config.state_path(pool_prodino_config.state_persist_path)),
        )
        if pool_prodino_config.enabled
        else None
    )
    oelverbrauch = OelverbrauchTracker(
        oelverbrauch_config,
        StateStore(app_config.state_path(oelverbrauch_config.state_persist_path)),
    )
    diesel_price_client = DieselPriceClient(oelverbrauch_config) if oelverbrauch_config.enabled else None
    failsafe_monitor = FailsafeMonitor.from_settings(app_config.settings)
    flowmeter_config = FlowmeterModbusConfig.from_settings(app_config.settings)
    flowmeter = FlowmeterModbusClient(flowmeter_config) if flowmeter_config.enabled else None
    watermeter_http_config = WatermeterHttpConfig.from_settings(app_config.settings)
    watermeter_http = WatermeterHttpClient(watermeter_http_config) if watermeter_http_config.enabled else None
    pump_group_configs = pump_group_configs_from_settings(app_config.settings)
    pump_group_clients = {
        name: PumpGroupModbusClient(config) for name, config in pump_group_configs.items()
    }
    disabled_physical_output_components = _disabled_local_pump_group_output_components(pump_group_configs)
    if keller_relay_client is not None:
        disabled_physical_output_components.update(_keller_relay_output_components(keller_relay_config))
    if pool_prodino_config.enabled:
        disabled_physical_output_components.update({pool_prodino_config.valve_component, pool_prodino_config.pump_component})
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
    brunnen_water_total_l: float | None = None
    brunnen_water_total_l_http: float | None = None
    brunnen_flow_last_seen_ts: float | None = None
    brunnen_no_flow_since_ts: float | None = None
    flowmeter_next_poll_ts = 0.0
    flowmeter_task: asyncio.Task | None = None
    flowmeter_last_error_log_ts = 0.0
    watermeter_http_next_poll_ts = 0.0
    watermeter_http_task: asyncio.Task | None = None
    watermeter_http_last_error_log_ts = 0.0
    applied_do: dict[str, bool] = {}
    applied_ao: dict[str, float] = {}
    pump_group_snapshots: dict[str, PumpGroupSnapshot] = {}
    keller_relay_last_ok_ts: float | None = None
    keller_relay_online: bool | None = None
    keller_relay_next_poll_ts = 0.0
    keller_relay_vl_next_control_ts: dict[str, float] = {}
    keller_relay_vl_samples: dict[str, tuple[float, float]] = {}
    keller_relay_error = ""
    pool_prodino_snapshot: ProdinoPoolSnapshot | None = None
    pool_prodino_online: bool | None = None
    pool_prodino_last_ok_ts: float | None = None
    pool_prodino_next_poll_ts = 0.0
    pool_prodino_error = ""
    oelverbrauch_snapshot = oelverbrauch.snapshot(None)
    diesel_price_next_poll_ts = 0.0
    diesel_price_task: asyncio.Task | None = None
    diesel_price_last_error_log_ts = 0.0
    oelbrenner_common_active = False
    klima_og_cooling_active = False
    pool_state = PoolControlState(False, None, None, False, False, False, False, "deaktiviert", 0.0, 0.0, 0.0, None, 0.0, 0.0, "")
    try:
        while not stop.is_set():
            started = time.monotonic()
            now_ts = time.time()
            heating_tick = cycle_count % heating_divider == 0
            if mqtt.connected and not ha_discovery_published:
                _publish_ha_discovery(mqtt, controller_config)
                ha_discovery_published = True
            if flowmeter is not None:
                if flowmeter_task is not None and flowmeter_task.done():
                    try:
                        flowmeter_snapshot = flowmeter_task.result()
                        brunnen_flow_l_min = flowmeter_snapshot.flow_l_min
                        brunnen_water_total_l = flowmeter_snapshot.total_l
                        brunnen_flow_last_seen_ts = now_ts
                    except Exception as exc:
                        if now_ts - flowmeter_last_error_log_ts >= 60:
                            flowmeter_last_error_log_ts = now_ts
                            log.warning("Brunnen-Flowmeter Modbus nicht erreichbar: %s", exc)
                    flowmeter_task = None
                    flowmeter_next_poll_ts = now_ts + max(0.2, flowmeter_config.poll_interval_s)
                if flowmeter_task is None and now_ts >= flowmeter_next_poll_ts:
                    flowmeter_task = asyncio.create_task(flowmeter.read_snapshot())
            if watermeter_http is not None:
                if watermeter_http_task is not None and watermeter_http_task.done():
                    try:
                        watermeter_snapshot = watermeter_http_task.result()
                        brunnen_water_total_l_http = watermeter_snapshot.total_l
                        if watermeter_http_config.mqtt_mirror_enabled:
                            _publish_watermeter_http_mirror(mqtt, watermeter_http_config, watermeter_snapshot)
                    except Exception as exc:
                        if watermeter_http_config.mqtt_mirror_enabled:
                            _publish_watermeter_http_error(mqtt, watermeter_http_config, str(exc))
                        if now_ts - watermeter_http_last_error_log_ts >= 60:
                            watermeter_http_last_error_log_ts = now_ts
                            log.warning("AI-on-the-edge Wasserzaehler HTTP nicht erreichbar/ungueltig: %s", exc)
                    watermeter_http_task = None
                    watermeter_http_next_poll_ts = now_ts + max(1.0, watermeter_http_config.poll_interval_s)
                if watermeter_http_task is None and now_ts >= watermeter_http_next_poll_ts:
                    watermeter_http_task = asyncio.create_task(watermeter_http.read_snapshot())
            if diesel_price_client is not None:
                if diesel_price_task is not None and diesel_price_task.done():
                    try:
                        diesel_price_snapshot = diesel_price_task.result()
                        oelverbrauch.update_dieselpreis(diesel_price_snapshot, now_ts)
                    except Exception as exc:
                        oelverbrauch.mark_price_error(str(exc))
                        if now_ts - diesel_price_last_error_log_ts >= 300:
                            diesel_price_last_error_log_ts = now_ts
                            log.warning("Dieselpreis konnte nicht aktualisiert werden: %s", exc)
                    diesel_price_task = None
                    diesel_price_next_poll_ts = now_ts + oelverbrauch_config.dieselpreis_poll_interval_s
                if diesel_price_task is None and now_ts >= diesel_price_next_poll_ts:
                    diesel_price_task = asyncio.create_task(asyncio.to_thread(diesel_price_client.fetch))

            snapshot = await io_backend.read_all()
            if pool_controller is not None:
                if pool_prodino_client is not None and now_ts >= pool_prodino_next_poll_ts:
                    pool_prodino_next_poll_ts = now_ts + pool_prodino_config.poll_interval_s
                    try:
                        pool_prodino_snapshot = await pool_prodino_client.read_snapshot()
                        pool_prodino_online = True
                        pool_prodino_last_ok_ts = now_ts
                        pool_prodino_error = ""
                    except Exception as exc:
                        if pool_prodino_online is not False:
                            log.warning("Pool-Prodino Modbus nicht erreichbar: %s", exc)
                        pool_prodino_online = False
                        pool_prodino_error = str(exc)
                        pool_prodino_client.reset_cache()
                if pool_prodino_client is not None:
                    snapshot = _merge_prodino_pool_modbus_snapshot(
                        controller_config,
                        snapshot,
                        pool_prodino_snapshot if pool_prodino_online else None,
                        pool_prodino_config,
                    )
                else:
                    snapshot = _merge_prodino_pool_snapshot(controller_config, snapshot, mqtt, pool_prodino_config)
            if keller_client is not None:
                try:
                    keller_snapshot = await keller_client.read_snapshot()
                    snapshot = _merge_snapshots(snapshot, keller_snapshot)
                    mqtt.peer_last_seen_ts = now_ts
                    mqtt.peer_online = True
                except Exception as exc:
                    mqtt.peer_online = False
                    log.warning("Keller-Slave Modbus nicht erreichbar: %s", exc)

            if heating_tick and pump_group_clients:
                pump_group_snapshots = await _read_pump_groups(
                    controller_config,
                    pump_group_clients,
                    pump_group_snapshots,
                )
                snapshot = _merge_pump_group_snapshot(controller_config, snapshot, pump_group_snapshots)

            if keller_relay_client is not None and now_ts >= keller_relay_next_poll_ts:
                keller_relay_next_poll_ts = now_ts + keller_relay_config.health_poll_interval_s
                try:
                    await keller_relay_client.poll_status()
                    keller_relay_last_ok_ts = now_ts
                    if keller_relay_online is False:
                        log.info("Keller-R421B16 Relais wieder erreichbar")
                    keller_relay_online = True
                    keller_relay_error = ""
                except Exception as exc:
                    if keller_relay_online is not False:
                        log.warning("Keller-R421B16 Relais Statuspoll fehlgeschlagen: %s", exc)
                    keller_relay_online = False
                    keller_relay_error = str(exc)

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
                keller_relay_client,
                failsafe_monitor,
                io_backend,
                snapshot,
                now_ts,
                tor_runtime,
            )

            failsafe_state = failsafe_monitor.evaluate(
                now_ts=now_ts,
                mqtt_connected=mqtt.connected,
                last_mqtt_seen_ts=mqtt.last_seen_ts,
                last_ha_heartbeat_ts=mqtt.last_ha_heartbeat_ts,
                outside_temp_c=_sensor_value_by_component(controller_config, snapshot, "aussen"),
            )

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
                oelverbrauch_snapshot = oelverbrauch.update(
                    now_ts,
                    _di_value_by_component(controller_config, snapshot, oelverbrauch_config.burner_component),
                )
                _apply_pump_group_vl_controls(
                    controller_config,
                    mqtt,
                    snapshot,
                    auto_do,
                    auto_ao,
                    applied_ao,
                    pump_group_snapshots,
                    keller_relay_config if keller_relay_client is not None else None,
                    keller_relay_client.snapshot() if keller_relay_client is not None else None,
                    keller_relay_vl_next_control_ts,
                    keller_relay_vl_samples,
                    now_ts,
                )
                if pool_controller is not None:
                    pool_state = pool_controller.compute(
                        now_ts=now_ts,
                        float_empty=_di_value_by_component(controller_config, snapshot, pool_prodino_config.float_component),
                        test_mode=bool(regler.pool_nachspeisung_testmodus),
                        fill_delay_s=regler.pool_nachspeisung_delay_s,
                        start_hour=regler.pool_nachspeisung_start_hour,
                        end_hour=regler.pool_nachspeisung_end_hour,
                        close_delay_s=regler.pool_nachspeisung_close_delay_s,
                        meter_settle_s=regler.pool_nachspeisung_meter_settle_s,
                        max_fill_s=regler.pool_nachspeisung_max_fill_s,
                        daily_dose_ml=regler.pool_flockung_tagesdosis_ml,
                        daily_dose_hour=regler.pool_flockung_start_hour,
                        fresh_ml_per_l=regler.pool_flockung_ml_pro_l_frischwasser,
                        pump_ml_min=regler.pool_flockung_pumpe_ml_min,
                        water_meter_total_l=(
                            brunnen_water_total_l_http
                            if brunnen_water_total_l_http is not None
                            else brunnen_water_total_l
                        ),
                    )
                    _set_do_by_component(controller_config, auto_do, pool_prodino_config.valve_component, pool_state.valve_open)
                    _set_do_by_component(controller_config, auto_do, pool_prodino_config.pump_component, pool_state.dosing_pump_on)
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
                disabled_physical_output_components=disabled_physical_output_components,
            )
            applied_do.update(written_do)
            applied_ao.update(written_ao)
            if heating_tick and pool_controller is not None:
                if pool_prodino_client is not None:
                    try:
                        await _write_prodino_pool_modbus_outputs(
                            pool_prodino_client,
                            controller_config,
                            applied_do,
                            pool_prodino_config,
                        )
                    except Exception as exc:
                        pool_prodino_online = False
                        pool_prodino_error = str(exc)
                        pool_prodino_client.reset_cache()
                        log.warning("Pool-Prodino Modbus Schreiben fehlgeschlagen: %s", exc)
                else:
                    _write_prodino_pool_outputs(mqtt, controller_config, applied_do, pool_prodino_config)
            if heating_tick and pump_group_clients:
                await _write_pump_groups(controller_config, pump_group_clients, applied_do, applied_ao)
            if heating_tick and keller_relay_client is not None:
                try:
                    await keller_relay_client.write_outputs(
                        controller_config,
                        applied_do,
                        {**applied_ao, **auto_ao},
                        _hand_overrides_for_components(
                            controller_config,
                            hand_auto,
                            _keller_relay_manual_components(keller_relay_config),
                        ),
                    )
                except Exception as exc:
                    keller_relay_online = False
                    keller_relay_error = str(exc)
                    log.warning("Keller-R421B16 Relais Schreiben fehlgeschlagen: %s", exc)
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
                    keller_relay_client.snapshot() if keller_relay_client is not None else None,
                    keller_relay_client.relay_component_states() if keller_relay_client is not None else None,
                    keller_relay_online,
                    keller_relay_last_ok_ts,
                    keller_relay_error,
                    pool_state if pool_controller is not None else None,
                    (
                        _prodino_modbus_online(pool_prodino_last_ok_ts, pool_prodino_online, pool_prodino_config, now_ts)
                        if pool_prodino_client is not None
                        else _prodino_pool_online(mqtt, pool_prodino_config, now_ts)
                    )
                    if pool_controller is not None
                    else None,
                    (
                    pool_prodino_last_ok_ts
                        if pool_prodino_client is not None
                        else mqtt.prodino_pool_last_seen_ts
                    )
                    if pool_controller is not None
                    else None,
                    pool_prodino_snapshot if pool_prodino_client is not None else None,
                    brunnen_water_total_l_http if brunnen_water_total_l_http is not None else brunnen_water_total_l,
                    oelverbrauch_snapshot,
                    tor_runtime,
                    now_ts,
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
                keller_relay_last_ok_ts=keller_relay_last_ok_ts,
                keller_relay_online=keller_relay_online,
                pool_prodino_last_ok_ts=pool_prodino_last_ok_ts,
                pool_prodino_online=pool_prodino_online,
            )

            await _sleep_remaining(stop, cycle_s, started)
    finally:
        await io_backend.set_cpu_leds({"A1": "off", "A2": "off", "A3": "off", "A4": "off", "A5": "off"})
        if keller_relay_client is not None:
            try:
                await keller_relay_client.all_off()
            except Exception as exc:
                log.warning("Keller-R421B16 Relais Abschalten fehlgeschlagen: %s", exc)
        if pool_prodino_client is not None:
            try:
                await pool_prodino_client.all_off()
            except Exception as exc:
                log.warning("Pool-Prodino Abschalten fehlgeschlagen: %s", exc)
        if flowmeter_task is not None:
            flowmeter_task.cancel()
        if watermeter_http_task is not None:
            watermeter_http_task.cancel()
        if diesel_price_task is not None:
            diesel_price_task.cancel()
        oelverbrauch.save()
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
    return _load_optional_io_map(app_config, "io_map.keller.yaml")


def _load_optional_io_map(app_config: AppConfig, name: str) -> IoMap | None:
    try:
        raw = load_yaml(resolve_config_file(app_config.config_dir, name))
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


def _merge_prodino_pool_snapshot(
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
    mqtt: MqttBridge,
    config: PoolProdinoConfig,
) -> HardwareSnapshot:
    channel = app_config.io_map.by_component(config.float_component)
    if channel is None or channel.kind != "di":
        return snapshot
    raw_value = mqtt.prodino_pool_inputs.get(config.input_index)
    if raw_value is None:
        return snapshot
    empty_value = bool(raw_value) if config.float_empty_high else not bool(raw_value)
    return HardwareSnapshot(
        di={**snapshot.di, channel.id: empty_value},
        ai=snapshot.ai,
        rtd=snapshot.rtd,
        do=snapshot.do,
        ao=snapshot.ao,
    )


def _merge_prodino_pool_modbus_snapshot(
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
    prodino: ProdinoPoolSnapshot | None,
    config: PoolProdinoConfig,
) -> HardwareSnapshot:
    if prodino is None:
        return snapshot
    channel = app_config.io_map.by_component(config.float_component)
    if channel is None or channel.kind != "di":
        return snapshot
    raw_value = prodino.inputs.get(config.input_index)
    if raw_value is None:
        return snapshot
    empty_value = bool(raw_value) if config.float_empty_high else not bool(raw_value)
    return HardwareSnapshot(
        di={**snapshot.di, channel.id: empty_value},
        ai=snapshot.ai,
        rtd=snapshot.rtd,
        do=snapshot.do,
        ao=snapshot.ao,
    )


def _prodino_pool_online(mqtt: MqttBridge, config: PoolProdinoConfig, now_ts: float) -> bool:
    if mqtt.prodino_pool_online is False:
        return False
    if mqtt.prodino_pool_last_seen_ts is None:
        return False
    if now_ts - mqtt.prodino_pool_last_seen_ts > config.health_timeout_s:
        return False
    return bool(mqtt.prodino_pool_online)


def _prodino_modbus_online(
    last_ok_ts: float | None,
    online: bool | None,
    config: PoolProdinoConfig,
    now_ts: float,
) -> bool:
    if online is False or last_ok_ts is None:
        return False
    return now_ts - last_ok_ts <= config.health_timeout_s


async def _read_pump_groups(
    app_config: AppConfig,
    clients: dict[str, PumpGroupModbusClient],
    previous: dict[str, PumpGroupSnapshot],
) -> dict[str, PumpGroupSnapshot]:
    snapshots: dict[str, PumpGroupSnapshot] = {}
    for name, client in clients.items():
        try:
            snapshots[name] = await client.read_snapshot()
        except Exception as exc:
            old = previous.get(name)
            snapshots[name] = PumpGroupSnapshot(online=False)
            if old is None or old.online:
                log.warning("Pumpengruppe %s Modbus TCP nicht erreichbar: %s", name, exc)
    return snapshots


def _merge_pump_group_snapshot(
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
    pump_groups: dict[str, PumpGroupSnapshot],
) -> HardwareSnapshot:
    rtd = dict(snapshot.rtd)
    for name, pump_snapshot in pump_groups.items():
        if not pump_snapshot.online:
            continue
        config = pump_group_configs_from_settings(app_config.settings).get(name)
        if config is None:
            continue
        _set_virtual_rtd(app_config, rtd, config.vl_component, pump_snapshot.vl_temp_c)
        _set_virtual_rtd(app_config, rtd, config.rl_component, pump_snapshot.rl_temp_c)
    return HardwareSnapshot(
        di=dict(snapshot.di),
        ai=dict(snapshot.ai),
        rtd=rtd,
        do=dict(snapshot.do),
        ao=dict(snapshot.ao),
    )


def _set_virtual_rtd(app_config: AppConfig, rtd: dict[str, float | None], component: str, value: float | None) -> None:
    if not component or value is None:
        return
    for channel_id, channel in app_config.io_map.rtd.items():
        if channel.komponente == component:
            rtd[channel_id] = value
            return


async def _write_pump_groups(
    app_config: AppConfig,
    clients: dict[str, PumpGroupModbusClient],
    applied_do: dict[str, bool],
    applied_ao: dict[str, float],
) -> None:
    configs = pump_group_configs_from_settings(app_config.settings)
    for name, client in clients.items():
        config = configs.get(name)
        if config is None:
            continue
        pump_on = _applied_do_by_component(app_config, applied_do, config.pump_component)
        target_pct = _applied_ao_by_component(app_config, applied_ao, config.mixer_component)
        try:
            await client.write_command(pump_on=pump_on, target_pct=target_pct)
        except Exception as exc:
            log.warning("Pumpengruppe %s Modbus TCP Schreiben fehlgeschlagen: %s", name, exc)


def _disabled_local_pump_group_output_components(
    configs: dict[str, Any],
) -> set[str]:
    components: set[str] = set()
    for config in configs.values():
        if not getattr(config, "disable_local_outputs", False):
            continue
        if config.pump_component:
            components.add(config.pump_component)
        if config.mixer_component:
            components.add(config.mixer_component)
        # Die alten AUF/ZU-Relais gehoeren zum selben lokalen Kreis und duerfen
        # beim ESP-Test nicht parallel anziehen.
        if config.name == "nebengeb":
            components.update({"sv_nebengeb_auf", "sv_nebengeb_zu"})
    return components


def _keller_relay_output_components(config: KellerRelayConfig) -> set[str]:
    components: set[str] = set()
    for group in config.groups.values():
        components.add(group.pump_component)
        components.add(group.mixer_component)
        components.update(relay_component_names(group.name).values())
    return components


def _keller_relay_manual_components(config: KellerRelayConfig) -> set[str]:
    components: set[str] = set()
    for group in config.groups.values():
        components.update(relay_component_names(group.name).values())
    return components


def _hand_overrides_for_components(
    app_config: AppConfig,
    hand_auto: HandAutoManager,
    components: set[str],
) -> dict[str, bool]:
    hand_snapshot = hand_auto.snapshot()
    overrides: dict[str, bool] = {}
    for component in components:
        channel = app_config.io_map.by_component(component)
        if channel is None:
            continue
        hand = hand_snapshot.get(channel.id)
        if hand and hand.get("hand"):
            overrides[component] = bool(hand.get("wert"))
    return overrides


async def _update_cpu_leds(
    io_backend: BaseIO,
    app_config: AppConfig,
    mqtt: MqttBridge,
    failsafe_state: FailsafeState,
    now_ts: float,
    boot_ts: float,
    cycle_count: int,
    *,
    keller_relay_last_ok_ts: float | None = None,
    keller_relay_online: bool | None = None,
    pool_prodino_last_ok_ts: float | None = None,
    pool_prodino_online: bool | None = None,
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
        keller_relay_enabled = bool(app_config.setting("keller_relais.enabled", False))
        pool_prodino_enabled = bool(app_config.setting("pool_prodino.enabled", False))
        colors.update(
            {
                "A3": _peer_led_color_from_status(
                    keller_relay_last_ok_ts,
                    keller_relay_online,
                    now_ts,
                    boot_ts,
                    peer_timeout_s,
                )
                if keller_relay_enabled
                else ("green" if mqtt.connected else "red"),
                "A4": _freshness_led_color(mqtt.last_ha_heartbeat_ts, now_ts, ha_timeout_s, required=ha_required),
                "A5": _peer_led_color_from_status(
                    pool_prodino_last_ok_ts,
                    pool_prodino_online,
                    now_ts,
                    boot_ts,
                    peer_timeout_s,
                )
                if pool_prodino_enabled
                else ("red" if failsafe_state.active else "green"),
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
    return _peer_led_color_from_status(mqtt.peer_last_seen_ts, mqtt.peer_online, now_ts, boot_ts, timeout_s)


def _peer_led_color_from_status(
    last_seen_ts: float | None,
    online: bool | None,
    now_ts: float,
    boot_ts: float,
    timeout_s: float,
) -> str:
    if online is False:
        return "red"
    if last_seen_ts is not None and now_ts - last_seen_ts <= timeout_s and online is not False:
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
    keller_relay_client: KellerRelayClient | None,
    failsafe_monitor: FailsafeMonitor,
    io_backend: BaseIO,
    snapshot: HardwareSnapshot,
    now_ts: float,
    tor_runtime: TorRuntime,
) -> None:
    for command in mqtt.drain_commands():
        if command.typ == "failsafe_force":
            failsafe_monitor.force = str(command.payload).strip().lower() in {"1", "true", "on", "ja"}
            continue

        if command.typ == "freigabe_set":
            group, _, name = command.name.partition("/")
            if not freigaben.set(group, name, _extract_bool(command.payload)):
                log.warning("MQTT-Freigabe fuer unbekannte Gruppe/Komponente ignoriert: %s", command.name)
            else:
                _publish_freigaben_state(mqtt, freigaben)
            continue

        if command.typ == "regler_set":
            if not regler.set(command.name, command.payload):
                log.warning("MQTT-Reglerparameter unbekannt, ignoriert: %s", command.name)
            continue

        if command.typ == "mischer_runtime_set":
            if keller_relay_client is None or not keller_relay_client.set_runtime(command.name, command.payload):
                log.warning("MQTT-Mischerlaufzeit unbekannt/ungueltig, ignoriert: %s", command.name)
            continue

        if command.typ == "tor_request":
            mqtt.publish_json(
                f"{mqtt.base}/tor/fahrwunsch",
                {"command": command.name, "requested_at": now_ts},
                retain=False,
            )
            log.info("Torfahrwunsch %s zur Kamerapruefung an Home Assistant gesendet", command.name)
            continue

        if command.typ == "tor_command":
            await _handle_tor_command(app_config, io_backend, command.name, tor_runtime, now_ts)
            continue

        if command.typ == "tor_verify":
            if not tor_runtime.bestaetige_position(command.name, now_ts):
                log.warning("Torposition %r nicht akzeptiert (Fahrt aktiv oder Wert ungueltig)", command.name)
            else:
                log.info("Torposition durch Kamerapruefung bestaetigt: %s", command.name)
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
    command_name: str,
    tor_runtime: TorRuntime,
    now_ts: float,
) -> None:
    decision = tor_runtime.entscheide(command_name, now_ts)
    log.info(
        "Torbefehl %s: position=%s ausgang=%s ausfuehren=%s grund=%s",
        command_name,
        tor_runtime.position,
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
    outside_temp_c = _sensor_value_by_component(app_config, snapshot, "aussen")
    routing_state, routed_do, routed_ao = compute_routing(
        regler.as_settings(app_config.settings),
        demands,
        failsafe_state,
        freigaben,
        outside_temp_c=outside_temp_c,
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
        auto["DO01"] = auto["DO01"] or (
            brauchwasser_state.active
            and _compute_oelbrenner_brauchwasser_heat(app_config, snapshot, brauchwasser_state)
        )
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


def _apply_pump_group_vl_controls(
    app_config: AppConfig,
    mqtt: MqttBridge,
    snapshot: HardwareSnapshot,
    auto_do: dict[str, bool],
    auto_ao: dict[str, float],
    applied_ao: dict[str, float],
    pump_group_snapshots: dict[str, PumpGroupSnapshot],
    keller_relay_config: KellerRelayConfig | None = None,
    keller_relay_snapshot: dict[str, dict[str, float | bool | str]] | None = None,
    relay_next_control_ts: dict[str, float] | None = None,
    relay_vl_samples: dict[str, tuple[float, float]] | None = None,
    now_ts: float | None = None,
) -> None:
    _apply_single_pump_group_vl_control(
        app_config,
        mqtt,
        snapshot,
        auto_do,
        auto_ao,
        applied_ao,
        pump_group_snapshots,
        name="nebengeb",
    )
    if keller_relay_config is not None:
        for group in keller_relay_config.groups.values():
            _apply_single_relay_group_vl_control(
                app_config,
                mqtt,
                snapshot,
                auto_do,
                auto_ao,
                applied_ao,
                group,
                keller_relay_snapshot or {},
                relay_next_control_ts if relay_next_control_ts is not None else {},
                relay_vl_samples if relay_vl_samples is not None else {},
                time.time() if now_ts is None else now_ts,
            )


def _apply_single_pump_group_vl_control(
    app_config: AppConfig,
    mqtt: MqttBridge,
    snapshot: HardwareSnapshot,
    auto_do: dict[str, bool],
    auto_ao: dict[str, float],
    applied_ao: dict[str, float],
    pump_group_snapshots: dict[str, PumpGroupSnapshot],
    *,
    name: str,
) -> None:
    configs = pump_group_configs_from_settings(app_config.settings)
    config = configs.get(name)
    if config is None:
        return
    demand = mqtt.demands.get(name)
    if demand is None or not demand.aktiv or demand.vl_soll is None:
        return
    if not _auto_do_by_component(app_config, auto_do, config.pump_component):
        return

    actual_vl = _sensor_value_by_component(app_config, snapshot, config.vl_component)
    if actual_vl is None:
        log.warning("Pumpengruppe %s: keine gueltige Vorlauftemperatur, Mischerziel bleibt unveraendert", name)
        return

    current_position = _pump_group_current_position(
        app_config,
        applied_ao,
        auto_ao,
        pump_group_snapshots.get(name),
        config.mixer_component,
    )
    target_position = _compute_incremental_mixer_position(
        target_vl=float(demand.vl_soll),
        actual_vl=float(actual_vl),
        current_position=current_position,
        hysterese_k=float(app_config.setting(f"mischer.{name}.hysterese_k", 0.3)),
        kp_pct_per_k=float(app_config.setting(f"mischer.{name}.kp_pct_pro_k", 8.0)),
        max_step_pct=float(app_config.setting(f"mischer.{name}.max_step_pct", 20.0)),
        min_pct=float(app_config.setting(f"mischer.{name}.min_pct", 0.0)),
        max_pct=float(app_config.setting(f"mischer.{name}.max_pct", 100.0)),
    )
    _set_ao_by_component(app_config, auto_ao, config.mixer_component, target_position)
    if abs(target_position - current_position) >= 0.5:
        log.info(
            "Pumpengruppe %s VL-Regelung: soll=%.1fC ist=%.1fC pos=%.1f%% ziel=%.1f%%",
            name,
            float(demand.vl_soll),
            float(actual_vl),
            current_position,
            target_position,
        )


def _apply_single_relay_group_vl_control(
    app_config: AppConfig,
    mqtt: MqttBridge,
    snapshot: HardwareSnapshot,
    auto_do: dict[str, bool],
    auto_ao: dict[str, float],
    applied_ao: dict[str, float],
    group: RelayGroupConfig,
    relay_snapshot: dict[str, dict[str, float | bool | str]],
    next_control_ts: dict[str, float],
    vl_samples: dict[str, tuple[float, float]],
    now_ts: float,
) -> None:
    snapshot_values = relay_snapshot.get(group.name, {})
    last_target = _relay_group_snapshot_pct(snapshot_values, "target_pct")
    demand = mqtt.demands.get(group.name)
    if demand is None or not demand.aktiv or demand.vl_soll is None:
        _set_ao_by_component(app_config, auto_ao, group.mixer_component, 0.0)
        next_control_ts[group.name] = now_ts
        return
    if not _auto_do_by_component(app_config, auto_do, group.pump_component):
        _set_ao_by_component(app_config, auto_ao, group.mixer_component, 0.0)
        next_control_ts[group.name] = now_ts
        return

    actual_vl = _sensor_value_by_component(app_config, snapshot, group.vl_component)
    if actual_vl is None:
        _set_ao_by_component(app_config, auto_ao, group.mixer_component, 0.0)
        next_control_ts[group.name] = now_ts
        log.warning(
            "R421B16-Gruppe %s: keine gueltige Vorlauftemperatur %s, Mischerziel wird geschlossen",
            group.name,
            group.vl_component,
        )
        return

    if now_ts < next_control_ts.get(group.name, 0.0):
        if last_target is not None:
            _set_ao_by_component(app_config, auto_ao, group.mixer_component, last_target)
        return

    effective_vl, rise_rate_k_min = _predicted_vl_for_rising_temperature(
        group.name,
        float(actual_vl),
        now_ts,
        vl_samples,
        anticipation_s=float(app_config.setting(f"mischer.{group.name}.anticipation_s", 90.0)),
    )
    current_position = _relay_group_current_position(app_config, applied_ao, auto_ao, group, relay_snapshot)
    target_position = _compute_incremental_mixer_position(
        target_vl=float(demand.vl_soll),
        actual_vl=effective_vl,
        current_position=current_position,
        hysterese_k=float(app_config.setting(f"mischer.{group.name}.hysterese_k", 0.3)),
        kp_pct_per_k=float(app_config.setting(f"mischer.{group.name}.kp_pct_pro_k", 8.0)),
        max_step_pct=float(app_config.setting(f"mischer.{group.name}.max_step_pct", 20.0)),
        max_open_step_pct=float(app_config.setting(f"mischer.{group.name}.max_open_step_pct", app_config.setting(f"mischer.{group.name}.max_step_pct", 20.0))),
        max_close_step_pct=float(app_config.setting(f"mischer.{group.name}.max_close_step_pct", app_config.setting(f"mischer.{group.name}.max_step_pct", 20.0))),
        min_pct=float(app_config.setting(f"mischer.{group.name}.min_pct", 0.0)),
        max_pct=float(app_config.setting(f"mischer.{group.name}.max_pct", 100.0)),
    )
    _set_ao_by_component(app_config, auto_ao, group.mixer_component, target_position)
    control_interval_s = max(1.0, float(app_config.setting(f"mischer.{group.name}.control_interval_s", 20.0)))
    next_control_ts[group.name] = now_ts + control_interval_s
    if abs(target_position - current_position) >= 0.5:
        log.info(
            "R421B16-Gruppe %s VL-Regelung: soll=%.1fC ist=%.1fC prog=%.1fC steigung=%.2fK/min pos=%.1f%% ziel=%.1f%% pause=%.0fs",
            group.name,
            float(demand.vl_soll),
            float(actual_vl),
            effective_vl,
            rise_rate_k_min,
            current_position,
            target_position,
            control_interval_s,
        )


def _pump_group_current_position(
    app_config: AppConfig,
    applied_ao: dict[str, float],
    auto_ao: dict[str, float],
    pump_snapshot: PumpGroupSnapshot | None,
    mixer_component: str,
) -> float:
    if pump_snapshot is not None and pump_snapshot.online and pump_snapshot.position_pct is not None:
        return _clamp_pct(pump_snapshot.position_pct)
    channel = app_config.io_map.by_component(mixer_component)
    if channel is not None and channel.kind == "ao":
        if channel.id in applied_ao:
            return _clamp_pct(applied_ao[channel.id])
        if channel.id in auto_ao:
            return _clamp_pct(auto_ao[channel.id])
    return 0.0


def _relay_group_current_position(
    app_config: AppConfig,
    applied_ao: dict[str, float],
    auto_ao: dict[str, float],
    group: RelayGroupConfig,
    relay_snapshot: dict[str, dict[str, float | bool | str]],
) -> float:
    raw = relay_snapshot.get(group.name, {}).get("position_pct")
    if raw is not None:
        try:
            return _clamp_pct(float(raw))
        except (TypeError, ValueError):
            pass
    return _pump_group_current_position(app_config, applied_ao, auto_ao, None, group.mixer_component)


def _relay_group_snapshot_pct(snapshot_values: dict[str, float | bool | str], key: str) -> float | None:
    raw = snapshot_values.get(key)
    if raw is None:
        return None
    try:
        return _clamp_pct(float(raw))
    except (TypeError, ValueError):
        return None


def _predicted_vl_for_rising_temperature(
    name: str,
    actual_vl: float,
    now_ts: float,
    samples: dict[str, tuple[float, float]],
    *,
    anticipation_s: float,
) -> tuple[float, float]:
    previous = samples.get(name)
    samples[name] = (actual_vl, now_ts)
    if previous is None:
        return actual_vl, 0.0

    previous_vl, previous_ts = previous
    dt_s = now_ts - previous_ts
    if dt_s < 5.0 or dt_s > 300.0:
        return actual_vl, 0.0

    rate_k_s = (actual_vl - previous_vl) / dt_s
    rise_rate_k_min = rate_k_s * 60.0
    if rate_k_s <= 0.0:
        return actual_vl, rise_rate_k_min

    return actual_vl + rate_k_s * max(0.0, anticipation_s), rise_rate_k_min


def _compute_incremental_mixer_position(
    *,
    target_vl: float,
    actual_vl: float,
    current_position: float,
    hysterese_k: float,
    kp_pct_per_k: float,
    max_step_pct: float,
    min_pct: float,
    max_pct: float,
    max_open_step_pct: float | None = None,
    max_close_step_pct: float | None = None,
) -> float:
    hysterese_k = max(0.0, hysterese_k)
    min_pct = _clamp_pct(min_pct)
    max_pct = _clamp_pct(max_pct)
    if min_pct > max_pct:
        min_pct, max_pct = max_pct, min_pct
    error_k = target_vl - actual_vl
    if abs(error_k) <= hysterese_k:
        return max(min_pct, min(max_pct, _clamp_pct(current_position)))
    raw_step = error_k * max(0.0, kp_pct_per_k)
    open_limit = abs(max_open_step_pct if max_open_step_pct is not None else max_step_pct)
    close_limit = abs(max_close_step_pct if max_close_step_pct is not None else max_step_pct)
    if raw_step > 0:
        step = min(open_limit, raw_step)
    else:
        step = max(-close_limit, raw_step)
    return max(min_pct, min(max_pct, _clamp_pct(current_position + step)))


def _clamp_pct(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


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


def _compute_oelbrenner_brauchwasser_heat(
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
    brauchwasser_state: BrauchwasserState,
) -> bool:
    if not brauchwasser_state.active:
        return False
    vl_ist = _sensor_value_by_component(app_config, snapshot, "vl_sammel")
    if vl_ist is None:
        return True
    return vl_ist < float(brauchwasser_state.soll_c) + max(0.0, float(brauchwasser_state.kessel_reserve_k))


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


def _applied_do_by_component(app_config: AppConfig, applied_do: dict[str, bool], component: str) -> bool:
    channel = app_config.io_map.by_component(component)
    if channel is None or channel.kind != "do":
        return False
    return bool(applied_do.get(channel.id, False))


def _auto_do_by_component(app_config: AppConfig, auto_do: dict[str, bool], component: str) -> bool:
    channel = app_config.io_map.by_component(component)
    if channel is None or channel.kind != "do":
        return False
    return bool(auto_do.get(channel.id, False))


def _applied_ao_by_component(app_config: AppConfig, applied_ao: dict[str, float], component: str) -> float:
    channel = app_config.io_map.by_component(component)
    if channel is None or channel.kind != "ao":
        return 0.0
    return float(applied_ao.get(channel.id, 0.0))


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
    disabled_physical_output_components: set[str] | None = None,
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
        if channel.komponente in (disabled_physical_output_components or set()):
            continue
        if channel_id in local_io_map.do:
            await io_backend.write_do(channel, applied_do[channel_id])
        else:
            if channel_id not in local_io_map.do:
                keller_do[channel_id] = applied_do[channel_id]

    for channel_id, channel in app_config.io_map.ao.items():
        if only_channel_ids is not None and channel_id not in only_channel_ids:
            continue
        value, _hand = hand_auto.apply(channel, auto_ao.get(channel_id, 0.0), now_ts)
        applied_ao[channel_id] = float(value)
        if channel.komponente in (disabled_physical_output_components or set()):
            continue
        if channel_id in local_io_map.ao:
            await io_backend.write_ao(channel, applied_ao[channel_id])
        else:
            if channel_id not in local_io_map.ao:
                keller_ao[channel_id] = applied_ao[channel_id]

    if keller_client is not None and (keller_do or keller_ao):
        for channel_id, channel in keller_client.io_map.do.items():
            if channel.komponente not in (disabled_physical_output_components or set()):
                keller_do.setdefault(channel_id, (keller_fallback_do or {}).get(channel_id, auto_do.get(channel_id, False)))
        for channel_id, channel in keller_client.io_map.ao.items():
            if channel.komponente not in (disabled_physical_output_components or set()):
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
    keller_relay_snapshot: dict[str, dict[str, float | bool | str]] | None = None,
    keller_relay_states: dict[str, bool] | None = None,
    keller_relay_online: bool | None = None,
    keller_relay_last_ok_ts: float | None = None,
    keller_relay_error: str = "",
    pool_state: PoolControlState | None = None,
    pool_prodino_online: bool | None = None,
    pool_prodino_last_seen_ts: float | None = None,
    pool_prodino_snapshot: ProdinoPoolSnapshot | None = None,
    brunnen_water_total_l: float | None = None,
    oelverbrauch_snapshot: OelverbrauchSnapshot | None = None,
    tor_runtime: TorRuntime | None = None,
    now_ts: float | None = None,
) -> None:
    base = mqtt.base
    if tor_runtime is not None and now_ts is not None:
        tor_state = tor_runtime.snapshot(now_ts)
        mqtt.publish(f"{base}/tor/status", tor_state["status"], retain=True)
        mqtt.publish(f"{base}/tor/gesperrt", "1" if tor_state["gesperrt"] else "0", retain=True)
        mqtt.publish_json(f"{base}/tor/state", tor_state, retain=True)
    mqtt.publish(f"{base}/failsafe/active", "1" if failsafe_state.active else "0", retain=True)
    mqtt.publish(f"{base}/failsafe/grund", ",".join(failsafe_state.reasons), retain=True)
    if failsafe_state.vl_soll is not None:
        mqtt.publish(f"{base}/vl_soll/state", f"{failsafe_state.vl_soll:.1f}", retain=True)
    effective_vl_soll = _effective_heat_source_vl_soll(app_config, routing_state, brauchwasser_state)
    mqtt.publish(
        f"{base}/gesamt/vl_soll/state",
        "" if effective_vl_soll is None else f"{effective_vl_soll:.1f}",
        retain=True,
    )
    mqtt.publish(
        f"{base}/gesamt/waermebedarf_kw/state",
        "" if routing_state.heat_demand_kw is None else f"{routing_state.heat_demand_kw:.2f}",
        retain=True,
    )
    mqtt.publish(
        f"{base}/gesamt/wp_einzelleistung_kw/state",
        "" if routing_state.single_wp_available_kw is None else f"{routing_state.single_wp_available_kw:.2f}",
        retain=True,
    )
    mqtt.publish(
        f"{base}/gesamt/wp_parallel_schwelle_kw/state",
        "" if routing_state.wp_parallel_threshold_kw is None else f"{routing_state.wp_parallel_threshold_kw:.2f}",
        retain=True,
    )
    mqtt.publish(f"{base}/gesamt/active", "1" if routing_state.common_active else "0", retain=True)
    mqtt.publish_json(f"{base}/routing/state", routing_state.as_payload(), retain=True)
    mqtt.publish(f"{base}/brauchwasser/ladung_aktiv", "1" if brauchwasser_state.active else "0", retain=True)
    mqtt.publish(f"{base}/brauchwasser/grund", brauchwasser_state.reason, retain=True)
    mqtt.publish_json(f"{base}/brauchwasser/state", brauchwasser_state.as_payload(), retain=True)
    mqtt.publish(f"{base}/klima_og/kuehlung_aktiv", "1" if klima_og_cooling_active else "0", retain=True)
    if keller_relay_snapshot:
        _publish_mischer_state(mqtt, keller_relay_snapshot)
    if keller_relay_online is not None:
        _publish_keller_relay_health(mqtt, keller_relay_online, keller_relay_last_ok_ts, keller_relay_error)
    if pool_state is not None:
        _publish_pool_state(mqtt, pool_state, pool_prodino_online, pool_prodino_last_seen_ts, pool_prodino_snapshot)
    oelbrenner_safety_reasons = _oelbrenner_safety_reasons(app_config, snapshot)
    mqtt.publish(f"{base}/oelbrenner/sicherheit/ok", "0" if oelbrenner_safety_reasons else "1", retain=True)
    mqtt.publish(f"{base}/oelbrenner/sicherheit/grund", ",".join(oelbrenner_safety_reasons), retain=True)
    if oelverbrauch_snapshot is not None:
        _publish_oelverbrauch_state(mqtt, oelverbrauch_snapshot)
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
        f"{base}/brunnen/wasserzaehler_l/state",
        "" if brunnen_water_total_l is None else f"{brunnen_water_total_l:.3f}",
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
    _publish_freigaben_state(mqtt, freigaben)
    mqtt.publish_json(f"{base}/regler/state", regler.snapshot(), retain=True)
    for name, value in regler.snapshot().items():
        mqtt.publish(f"{base}/regler/{name}/state", str(value), retain=True)

    for name, demand in mqtt.demands.items():
        mqtt.publish_json(
            f"{base}/anforderung/{name}/aktuell",
            {
                "aktiv": demand.aktiv,
                "vl_soll": demand.vl_soll,
                "quelle": demand.quelle,
                "leistung_kw": demand.leistung_kw,
            },
            retain=True,
        )
        mqtt.publish(f"{base}/anforderung/{name}/aktiv/state", "1" if demand.aktiv else "0", retain=True)
        if demand.vl_soll is not None:
            mqtt.publish(f"{base}/anforderung/{name}/vl_soll/state", f"{demand.vl_soll:.1f}", retain=True)
        mqtt.publish(
            f"{base}/anforderung/{name}/leistung_kw/state",
            "" if demand.leistung_kw is None else f"{demand.leistung_kw:.2f}",
            retain=True,
        )

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
            mqtt.publish(f"{base}/di/{channel.komponente}/state", "1" if value else "0", retain=True)

    mqtt.publish_json(f"{base}/hand/state", hand_auto.snapshot(), retain=True)
    hand_snapshot = hand_auto.snapshot()
    for channel_id, channel in app_config.io_map.do.items():
        value = applied_do.get(channel_id, False)
        hand = hand_snapshot.get(channel_id)
        hand_active = bool((hand or {}).get("hand"))
        mqtt.publish(f"{base}/do/{channel.komponente}/state", "1" if value else "0", retain=True)
        mqtt.publish(f"{base}/{channel.komponente}/hand/mode/state", "1" if hand_active else "0", retain=True)
        mqtt.publish(
            f"{base}/{channel.komponente}/hand/value/state",
            "1" if hand_active and (hand or {}).get("wert") else "0",
            retain=True,
        )
    if keller_relay_states:
        _publish_keller_relay_states(mqtt, keller_relay_states)
    for channel_id, channel in app_config.io_map.ao.items():
        value = applied_ao.get(channel_id, 0.0)
        hand = hand_snapshot.get(channel_id)
        hand_active = bool((hand or {}).get("hand"))
        mqtt.publish(f"{base}/ao/{channel.komponente}/state", f"{value:.1f}", retain=True)
        mqtt.publish(f"{base}/{channel.komponente}/hand/mode/state", "1" if hand_active else "0", retain=True)
        mqtt.publish(f"{base}/{channel.komponente}/hand/value/state", _ao_hand_value_state(channel, hand if hand_active else None), retain=True)


def _publish_watermeter_http_mirror(
    mqtt: MqttBridge,
    config: WatermeterHttpConfig,
    snapshot: WatermeterHttpSnapshot,
) -> None:
    topic_base = config.mqtt_topic_base
    if not topic_base:
        return
    mqtt.publish(f"{topic_base}/value", f"{snapshot.value:.4f}", retain=True)
    mqtt.publish(f"{topic_base}/raw", snapshot.raw, retain=True)
    mqtt.publish(f"{topic_base}/error", "no error", retain=True)
    mqtt.publish(f"{topic_base}/connection", "connected", retain=True)
    mqtt.publish(f"{topic_base}/timestamp", datetime.now(UTC).isoformat(), retain=True, force=True)


def _publish_oelverbrauch_state(mqtt: MqttBridge, snapshot: OelverbrauchSnapshot) -> None:
    base = mqtt.base
    mqtt.publish_json(f"{base}/oelverbrauch/state", snapshot.as_payload(), retain=True)
    mqtt.publish(
        f"{base}/oelverbrauch/brenner_laeuft",
        "" if snapshot.burner_running is None else ("1" if snapshot.burner_running else "0"),
        retain=True,
    )
    mqtt.publish(f"{base}/oelverbrauch/liter/state", f"{snapshot.total_liter:.4f}", retain=True)
    mqtt.publish(f"{base}/oelverbrauch/kwh/state", f"{snapshot.total_kwh:.3f}", retain=True)
    mqtt.publish(f"{base}/oelverbrauch/aktuell_l_h/state", f"{snapshot.current_liter_per_hour:.3f}", retain=True)
    mqtt.publish(f"{base}/oelverbrauch/aktuell_kw/state", f"{snapshot.current_kw:.3f}", retain=True)
    mqtt.publish(f"{base}/oelverbrauch/aktuell_eur_h/state", f"{snapshot.current_cost_eur_per_hour:.3f}", retain=True)
    mqtt.publish(f"{base}/oelverbrauch/laufzeit_h/state", f"{snapshot.runtime_h:.4f}", retain=True)
    mqtt.publish(f"{base}/oelverbrauch/kosten/state", f"{snapshot.cost_eur:.2f}", retain=True)
    mqtt.publish(f"{base}/oelverbrauch/dieselpreis_eur_l/state", f"{snapshot.dieselpreis_eur_l:.4f}", retain=True)
    mqtt.publish(f"{base}/oelverbrauch/dieselpreis_eur_m3/state", f"{snapshot.dieselpreis_eur_l:.4f}", retain=True)
    mqtt.publish(f"{base}/oelverbrauch/dieselpreis_quelle", snapshot.dieselpreis_source, retain=True)
    mqtt.publish(
        f"{base}/oelverbrauch/dieselpreis_aktualisiert",
        snapshot.dieselpreis_remote_updated or "unknown",
        retain=True,
    )
    mqtt.publish(
        f"{base}/oelverbrauch/dieselpreis_last_ok_ts",
        "" if snapshot.dieselpreis_last_ok_ts is None else str(int(snapshot.dieselpreis_last_ok_ts)),
        retain=True,
    )
    mqtt.publish(f"{base}/oelverbrauch/dieselpreis_fehler", snapshot.dieselpreis_error or "ok", retain=True)


def _effective_heat_source_vl_soll(
    app_config: AppConfig,
    routing_state: RoutingState,
    brauchwasser_state: BrauchwasserState,
) -> float | None:
    values: list[float] = []
    if routing_state.vl_soll is not None:
        values.append(float(routing_state.vl_soll))
    if brauchwasser_state.active:
        reserve_k = max(0.0, float(brauchwasser_state.kessel_reserve_k))
        values.append(float(brauchwasser_state.soll_c) + reserve_k)
    return max(values) if values else None


def _publish_watermeter_http_error(mqtt: MqttBridge, config: WatermeterHttpConfig, error: str) -> None:
    topic_base = config.mqtt_topic_base
    if not topic_base:
        return
    mqtt.publish(f"{topic_base}/connection", "disconnected", retain=True)
    mqtt.publish(f"{topic_base}/error", error or "HTTP read failed", retain=True)
    mqtt.publish(f"{topic_base}/timestamp", datetime.now(UTC).isoformat(), retain=True, force=True)


def _publish_keller_relay_states(mqtt: MqttBridge, states: dict[str, bool]) -> None:
    base = mqtt.base
    for component, value in sorted(states.items()):
        mqtt.publish(f"{base}/do/{component}/state", "1" if value else "0", retain=True)


def _publish_pool_state(
    mqtt: MqttBridge,
    state: PoolControlState,
    prodino_online: bool | None,
    prodino_last_seen_ts: float | None,
    prodino_snapshot: ProdinoPoolSnapshot | None = None,
) -> None:
    base = mqtt.base
    mqtt.publish_json(f"{base}/pool/nachspeisung/state", state.as_payload(), retain=True)
    mqtt.publish(f"{base}/pool/nachspeisung/grund", state.reason, retain=True)
    mqtt.publish(f"{base}/pool/nachspeisung/ventil", "1" if state.valve_open else "0", retain=True)
    mqtt.publish(
        f"{base}/pool/nachspeisung/schwimmer_zu_leer",
        "" if state.float_empty is None else ("1" if state.float_empty else "0"),
        retain=True,
    )
    mqtt.publish(f"{base}/pool/nachspeisung/fuellzeit_s/state", f"{state.fill_elapsed_s:.1f}", retain=True)
    mqtt.publish(f"{base}/pool/nachspeisung/letzte_liter/state", f"{state.last_fill_liters:.2f}", retain=True)
    mqtt.publish(f"{base}/pool/flockung/pumpe", "1" if state.dosing_pump_on else "0", retain=True)
    mqtt.publish(f"{base}/pool/flockung/restzeit_s/state", f"{state.dosing_remaining_s:.1f}", retain=True)
    mqtt.publish(
        f"{base}/pool/flockung/letzte_zugabe/state",
        "unknown" if state.last_dose_ts is None else _iso_timestamp(state.last_dose_ts),
        retain=True,
    )
    mqtt.publish(f"{base}/pool/flockung/letzte_zugabe_ml/state", f"{state.last_dose_ml:.2f}", retain=True)
    mqtt.publish(f"{base}/pool/flockung/letzte_zugabe_s/state", f"{state.last_dose_seconds:.1f}", retain=True)
    mqtt.publish(f"{base}/pool/flockung/letzte_zugabe_grund", state.last_dose_reason or "unbekannt", retain=True)
    if prodino_online is not None:
        mqtt.publish(f"{base}/prodino_pool/online", "1" if prodino_online else "0", retain=True)
    if prodino_snapshot is not None:
        for relay, value in sorted(prodino_snapshot.relays.items()):
            mqtt.publish(f"{base}/prodino_pool/relay/{relay}/state", "1" if value else "0", retain=True)
        valve_actual = prodino_snapshot.relays.get(1)
        dosing_actual = prodino_snapshot.relays.get(2)
        mqtt.publish(
            f"{base}/pool/nachspeisung/ventil_ist",
            "" if valve_actual is None else ("1" if valve_actual else "0"),
            retain=True,
        )
        mqtt.publish(
            f"{base}/pool/flockung/pumpe_ist",
            "" if dosing_actual is None else ("1" if dosing_actual else "0"),
            retain=True,
        )
        mismatch = (valve_actual is not None and valve_actual != state.valve_open) or (
            dosing_actual is not None and dosing_actual != state.dosing_pump_on
        )
        mqtt.publish(f"{base}/prodino_pool/relay_mismatch", "1" if mismatch else "0", retain=True)
    mqtt.publish(
        f"{base}/prodino_pool/last_seen_ts",
        "" if prodino_last_seen_ts is None else str(int(prodino_last_seen_ts)),
        retain=True,
    )


def _iso_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts).astimezone().isoformat()


def _write_prodino_pool_outputs(
    mqtt: MqttBridge,
    app_config: AppConfig,
    applied_do: dict[str, bool],
    config: PoolProdinoConfig,
) -> None:
    relay_map = {
        1: config.valve_component,
        2: config.pump_component,
    }
    for relay, component in relay_map.items():
        channel = app_config.io_map.by_component(component)
        if channel is None or channel.kind != "do":
            continue
        value = bool(applied_do.get(channel.id, False))
        reported = mqtt.prodino_pool_relays.get(relay)
        mqtt.publish(
            f"{config.topic_base}/relay/{relay}/set",
            "1" if value else "0",
            retain=False,
            force=reported is None or reported != value,
        )


async def _write_prodino_pool_modbus_outputs(
    client: ProdinoPoolModbusClient,
    app_config: AppConfig,
    applied_do: dict[str, bool],
    config: PoolProdinoConfig,
) -> None:
    valve_channel = app_config.io_map.by_component(config.valve_component)
    pump_channel = app_config.io_map.by_component(config.pump_component)
    valve_open = bool(applied_do.get(valve_channel.id, False)) if valve_channel is not None else False
    dosing_pump_on = bool(applied_do.get(pump_channel.id, False)) if pump_channel is not None else False
    await client.write_outputs(valve_open=valve_open, dosing_pump_on=dosing_pump_on)


def _publish_keller_relay_health(
    mqtt: MqttBridge,
    online: bool,
    last_ok_ts: float | None,
    error: str = "",
) -> None:
    base = mqtt.base
    mqtt.publish(f"{base}/keller_relais/online", "1" if online else "0", retain=True)
    mqtt.publish(f"{base}/keller_relais/stoerung", "0" if online else "1", retain=True)
    mqtt.publish(f"{base}/keller_relais/last_ok_ts", "" if last_ok_ts is None else str(int(last_ok_ts)), retain=True)
    mqtt.publish(f"{base}/keller_relais/error", "" if online else error, retain=True)


def _publish_mischer_state(mqtt: MqttBridge, snapshot: dict[str, dict[str, float | bool | str]]) -> None:
    base = mqtt.base
    mqtt.publish_json(f"{base}/mischer/state", snapshot, retain=True)
    for name in _mischer_names():
        values = snapshot.get(name)
        if not values:
            continue
        mqtt.publish(f"{base}/mischer/{name}/position_pct/state", f"{float(values.get('position_pct', 0.0)):.1f}", retain=True)
        mqtt.publish(f"{base}/mischer/{name}/target_pct/state", f"{float(values.get('target_pct', 0.0)):.1f}", retain=True)
        mqtt.publish(f"{base}/mischer/{name}/runtime_s/state", f"{float(values.get('runtime_s', 120.0)):.1f}", retain=True)
        mqtt.publish(f"{base}/mischer/{name}/moving/state", "1" if values.get("moving") else "0", retain=True)
        mqtt.publish(f"{base}/mischer/{name}/direction/state", str(values.get("direction", "stopp")), retain=True)


def _publish_freigaben_state(mqtt: MqttBridge, freigaben: Freigaben) -> None:
    base = mqtt.base
    mqtt.publish_json(f"{base}/freigabe/state", freigaben.snapshot(), retain=True)
    for name, enabled in freigaben.sources.items():
        mqtt.publish(f"{base}/freigabe/quellen/{name}/state", "1" if enabled else "0", retain=True)
    for name, enabled in freigaben.sinks.items():
        mqtt.publish(f"{base}/freigabe/senken/{name}/state", "1" if enabled else "0", retain=True)


def _ao_hand_value_state(channel: ChannelConfig, hand: dict[str, Any] | None) -> str:
    low, high = channel.bereich or (0.0, 100.0)
    if hand and hand.get("wert") is not None:
        value = float(hand["wert"])
    else:
        value = float(low)
    value = max(float(low), min(float(high), value))
    return f"{value:.1f}"


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

    _publish_discovery_entity(
        mqtt,
        prefix,
        "sensor",
        "tor_status",
        {
            "name": "Tor Status",
            "state_topic": f"{mqtt.base}/tor/status",
            "icon": "mdi:gate",
            "device": device_payload,
        },
    )
    for object_name, name, topic in (
        ("gesamt_waermebedarf_kw", "Heizung Waermebedarf", f"{mqtt.base}/gesamt/waermebedarf_kw/state"),
        ("wp_einzelleistung_kw", "WP Einzelleistung aktuell", f"{mqtt.base}/gesamt/wp_einzelleistung_kw/state"),
        (
            "wp_parallel_schwelle_kw",
            "WP Parallel Schwelle aktuell",
            f"{mqtt.base}/gesamt/wp_parallel_schwelle_kw/state",
        ),
    ):
        _publish_discovery_entity(
            mqtt,
            prefix,
            "sensor",
            object_name,
            {
                "name": name,
                "state_topic": topic,
                "unit_of_measurement": "kW",
                "device_class": "power",
                "state_class": "measurement",
                "device": device_payload,
            },
        )

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

    _publish_discovery_entity(
        mqtt,
        prefix,
        "binary_sensor",
        "keller_relais_modbus_stoerung",
        {
            "name": "R421B16 Modbus Stoerung",
            "state_topic": f"{mqtt.base}/keller_relais/stoerung",
            "payload_on": "1",
            "payload_off": "0",
            "device_class": "problem",
            "device": device_payload,
        },
    )
    _publish_discovery_entity(
        mqtt,
        prefix,
        "sensor",
        "keller_relais_modbus_fehler",
        {
            "name": "R421B16 Modbus Fehler",
            "state_topic": f"{mqtt.base}/keller_relais/error",
            "device": device_payload,
        },
    )

    _publish_mischer_discovery(mqtt, prefix, device_payload)
    _publish_pool_discovery(mqtt, prefix, device_payload)
    _publish_oelverbrauch_discovery(mqtt, prefix, device_payload)

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
        _publish_discovery_entity(
            mqtt,
            prefix,
            "sensor",
            demand["leistung_object_name"],
            {
                "name": demand["leistung_name"],
                "state_topic": demand["leistung_state_topic"],
                "unit_of_measurement": "kW",
                "device_class": "power",
                "state_class": "measurement",
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


def _publish_mischer_discovery(mqtt: MqttBridge, prefix: str, device_payload: dict[str, Any]) -> None:
    for key, label in _mischer_names().items():
        _publish_discovery_entity(
            mqtt,
            prefix,
            "sensor",
            f"mischer_{key}_ist",
            {
                "name": f"Mischer {label} Ist",
                "state_topic": f"{mqtt.base}/mischer/{key}/position_pct/state",
                "unit_of_measurement": "%",
                "state_class": "measurement",
                "device": device_payload,
            },
        )
        _publish_discovery_entity(
            mqtt,
            prefix,
            "sensor",
            f"mischer_{key}_soll",
            {
                "name": f"Mischer {label} Soll",
                "state_topic": f"{mqtt.base}/mischer/{key}/target_pct/state",
                "unit_of_measurement": "%",
                "state_class": "measurement",
                "device": device_payload,
            },
        )
        _publish_discovery_entity(
            mqtt,
            prefix,
            "binary_sensor",
            f"mischer_{key}_faehrt",
            {
                "name": f"Mischer {label} faehrt",
                "state_topic": f"{mqtt.base}/mischer/{key}/moving/state",
                "payload_on": "1",
                "payload_off": "0",
                "device": device_payload,
            },
        )
        _publish_discovery_entity(
            mqtt,
            prefix,
            "sensor",
            f"mischer_{key}_richtung",
            {
                "name": f"Mischer {label} Richtung",
                "state_topic": f"{mqtt.base}/mischer/{key}/direction/state",
                "device": device_payload,
            },
        )
        _publish_discovery_entity(
            mqtt,
            prefix,
            "number",
            f"mischer_{key}_laufzeit_s",
            {
                "name": f"Mischer {label} Laufzeit",
                "state_topic": f"{mqtt.base}/mischer/{key}/runtime_s/state",
                "command_topic": f"{mqtt.base}/mischer/{key}/runtime_s/set",
                "min": 10,
                "max": 900,
                "step": 1,
                "mode": "box",
                "unit_of_measurement": "s",
                "device": device_payload,
            },
        )


def _publish_pool_discovery(mqtt: MqttBridge, prefix: str, device_payload: dict[str, Any]) -> None:
    for sensor in (
        {
            "component": "sensor",
            "object_name": "pool_nachspeisung_grund",
            "name": "Pool Nachspeisung Grund",
            "state_topic": f"{mqtt.base}/pool/nachspeisung/grund",
        },
        {
            "component": "sensor",
            "object_name": "pool_nachspeisung_fuellzeit",
            "name": "Pool Nachspeisung Fuellzeit",
            "state_topic": f"{mqtt.base}/pool/nachspeisung/fuellzeit_s/state",
            "unit_of_measurement": "s",
            "state_class": "measurement",
        },
        {
            "component": "sensor",
            "object_name": "pool_nachspeisung_letzte_liter",
            "name": "Pool Nachspeisung letzte Liter",
            "state_topic": f"{mqtt.base}/pool/nachspeisung/letzte_liter/state",
            "unit_of_measurement": "L",
            "state_class": "measurement",
        },
        {
            "component": "sensor",
            "object_name": "pool_flockung_restzeit",
            "name": "Pool Flockung Restzeit",
            "state_topic": f"{mqtt.base}/pool/flockung/restzeit_s/state",
            "unit_of_measurement": "s",
            "state_class": "measurement",
        },
        {
            "component": "sensor",
            "object_name": "pool_flockung_letzte_zugabe",
            "name": "Pool Flockung letzte Zugabe",
            "state_topic": f"{mqtt.base}/pool/flockung/letzte_zugabe/state",
            "device_class": "timestamp",
        },
        {
            "component": "sensor",
            "object_name": "pool_flockung_letzte_zugabe_ml",
            "name": "Pool Flockung letzte Zugabe ml",
            "state_topic": f"{mqtt.base}/pool/flockung/letzte_zugabe_ml/state",
            "unit_of_measurement": "ml",
            "state_class": "measurement",
        },
        {
            "component": "sensor",
            "object_name": "pool_flockung_letzte_zugabe_s",
            "name": "Pool Flockung letzte Zugabe Laufzeit",
            "state_topic": f"{mqtt.base}/pool/flockung/letzte_zugabe_s/state",
            "unit_of_measurement": "s",
            "state_class": "measurement",
        },
        {
            "component": "sensor",
            "object_name": "pool_flockung_letzte_zugabe_grund",
            "name": "Pool Flockung letzte Zugabe Grund",
            "state_topic": f"{mqtt.base}/pool/flockung/letzte_zugabe_grund",
        },
    ):
        component = str(sensor.pop("component"))
        object_name = str(sensor.pop("object_name"))
        _publish_discovery_entity(mqtt, prefix, component, object_name, {**sensor, "device": device_payload})

    for binary in (
        {
            "object_name": "pool_nachspeisung_ventil",
            "name": "Pool Nachspeisung Ventil",
            "state_topic": f"{mqtt.base}/pool/nachspeisung/ventil",
        },
        {
            "object_name": "pool_nachspeisung_ventil_ist",
            "name": "Pool Nachspeisung Ventil Ist",
            "state_topic": f"{mqtt.base}/pool/nachspeisung/ventil_ist",
        },
        {
            "object_name": "pool_nachspeisung_schwimmer_zu_leer",
            "name": "Pool Schwimmer zu leer",
            "state_topic": f"{mqtt.base}/pool/nachspeisung/schwimmer_zu_leer",
        },
        {
            "object_name": "pool_flockung_pumpe",
            "name": "Pool Flockung Pumpe",
            "state_topic": f"{mqtt.base}/pool/flockung/pumpe",
        },
        {
            "object_name": "pool_flockung_pumpe_ist",
            "name": "Pool Flockung Pumpe Ist",
            "state_topic": f"{mqtt.base}/pool/flockung/pumpe_ist",
        },
        {
            "object_name": "prodino_pool_online",
            "name": "Prodino Pool online",
            "state_topic": f"{mqtt.base}/prodino_pool/online",
        },
        {
            "object_name": "prodino_pool_relay_mismatch",
            "name": "Prodino Pool Relais Abweichung",
            "state_topic": f"{mqtt.base}/prodino_pool/relay_mismatch",
        },
    ):
        _publish_discovery_entity(
            mqtt,
            prefix,
            "binary_sensor",
            binary["object_name"],
            {
                "name": binary["name"],
                "state_topic": binary["state_topic"],
                "payload_on": "1",
                "payload_off": "0",
                "device": device_payload,
            },
        )


def _publish_oelverbrauch_discovery(mqtt: MqttBridge, prefix: str, device_payload: dict[str, Any]) -> None:
    for sensor in (
        {
            "object_name": "oelverbrauch_liter",
            "name": "Oelverbrauch Liter",
            "state_topic": f"{mqtt.base}/oelverbrauch/liter/state",
            "unit_of_measurement": "L",
            "device_class": "gas",
            "state_class": "total_increasing",
            "icon": "mdi:oil",
        },
        {
            "object_name": "oelverbrauch_kwh",
            "name": "Oelverbrauch Energie",
            "state_topic": f"{mqtt.base}/oelverbrauch/kwh/state",
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing",
            "icon": "mdi:fire",
        },
        {
            "object_name": "oelverbrauch_aktuell_l_h",
            "name": "Oelverbrauch aktuell Energie-Dashboard",
            "state_topic": f"{mqtt.base}/oelverbrauch/aktuell_l_h/state",
            "unit_of_measurement": "L/h",
            "device_class": "volume_flow_rate",
            "state_class": "measurement",
            "icon": "mdi:oil",
        },
        {
            "object_name": "oelbrenner_leistung",
            "name": "Oelbrenner Leistung",
            "state_topic": f"{mqtt.base}/oelverbrauch/aktuell_kw/state",
            "unit_of_measurement": "kW",
            "device_class": "power",
            "state_class": "measurement",
            "icon": "mdi:fire",
        },
        {
            "object_name": "oelverbrauch_kosten_aktuell",
            "name": "Oelverbrauch Kosten aktuell",
            "state_topic": f"{mqtt.base}/oelverbrauch/aktuell_eur_h/state",
            "unit_of_measurement": "EUR/h",
            "state_class": "measurement",
            "icon": "mdi:currency-eur",
        },
        {
            "object_name": "oelverbrauch_laufzeit",
            "name": "Oelbrenner Laufzeit",
            "state_topic": f"{mqtt.base}/oelverbrauch/laufzeit_h/state",
            "unit_of_measurement": "h",
            "state_class": "total_increasing",
            "icon": "mdi:timer-outline",
        },
        {
            "object_name": "oelverbrauch_kosten",
            "name": "Oelverbrauch Kosten",
            "state_topic": f"{mqtt.base}/oelverbrauch/kosten/state",
            "unit_of_measurement": "EUR",
            "state_class": "measurement",
            "icon": "mdi:currency-eur",
        },
        {
            "object_name": "oelpreis_diesel_wez",
            "name": "Oelpreis Diesel WEZ",
            "state_topic": f"{mqtt.base}/oelverbrauch/dieselpreis_eur_l/state",
            "unit_of_measurement": "EUR/L",
            "state_class": "measurement",
            "icon": "mdi:gas-station",
        },
        {
            "object_name": "oelpreis_diesel_aktualisiert",
            "name": "Oelpreis Diesel Aktualisiert",
            "state_topic": f"{mqtt.base}/oelverbrauch/dieselpreis_aktualisiert",
            "icon": "mdi:update",
        },
        {
            "object_name": "oelpreis_diesel_fehler",
            "name": "Oelpreis Diesel Fehler",
            "state_topic": f"{mqtt.base}/oelverbrauch/dieselpreis_fehler",
            "icon": "mdi:alert-circle-outline",
        },
    ):
        object_name = str(sensor.pop("object_name"))
        _publish_discovery_entity(mqtt, prefix, "sensor", object_name, {**sensor, "device": device_payload})

    _publish_discovery_entity(
        mqtt,
        prefix,
        "binary_sensor",
        "oelverbrauch_brenner_laeuft",
        {
            "name": "Oelbrenner laeuft",
            "state_topic": f"{mqtt.base}/oelverbrauch/brenner_laeuft",
            "payload_on": "1",
            "payload_off": "0",
            "device_class": "running",
            "device": device_payload,
        },
    )


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


def _mischer_names() -> dict[str, str]:
    return {
        "fbh_eg": "FBH EG",
        "hk_backup": "HK Backup",
        "klima_og": "Klima OG",
    }


def _brunnen_sensor_definitions(base: str) -> list[dict[str, str]]:
    return [
        {
            "object_name": "brunnen_fluss",
            "name": "Brunnen Fluss",
            "state_topic": f"{base}/brunnen/fluss_l_min/state",
            "unit": "L/min",
        },
        {
            "object_name": "brunnen_wasserzaehler",
            "name": "Brunnen Wasserzaehler",
            "state_topic": f"{base}/brunnen/wasserzaehler_l/state",
            "unit": "L",
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
                "leistung_object_name": f"anforderung_{object_name}_leistung_kw",
                "leistung_name": f"Anforderung {display_name} Leistung",
                "leistung_state_topic": f"{base}/anforderung/{name}/leistung_kw/state",
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
            "key": "brauchwasser_kessel_reserve_k",
            "object_name": "brauchwasser_kessel_reserve_k",
            "name": "Brauchwasser Kesselreserve",
            "min": 0,
            "max": 30,
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
        {
            "key": "pool_nachspeisung_testmodus",
            "object_name": "pool_nachspeisung_testmodus",
            "name": "Pool Nachspeisung Testmodus",
            "min": 0,
            "max": 1,
            "step": 1,
            "unit": "",
        },
        {
            "key": "pool_nachspeisung_start_hour",
            "object_name": "pool_nachspeisung_startzeit",
            "name": "Pool Nachspeisung Startzeit",
            "min": 0,
            "max": 23,
            "step": 1,
            "unit": "h",
        },
        {
            "key": "pool_nachspeisung_end_hour",
            "object_name": "pool_nachspeisung_endzeit",
            "name": "Pool Nachspeisung Endzeit",
            "min": 0,
            "max": 23,
            "step": 1,
            "unit": "h",
        },
        {
            "key": "pool_nachspeisung_delay_s",
            "object_name": "pool_nachspeisung_verzoegerung",
            "name": "Pool Nachspeisung Verzoegerung",
            "min": 0,
            "max": 86400,
            "step": 10,
            "unit": "s",
        },
        {
            "key": "pool_nachspeisung_close_delay_s",
            "object_name": "pool_schwimmer_voll_verzoegerung",
            "name": "Pool Schwimmer Voll Verzoegerung",
            "min": 0,
            "max": 600,
            "step": 1,
            "unit": "s",
        },
        {
            "key": "pool_nachspeisung_meter_settle_s",
            "object_name": "pool_wasserzaehler_nachlauf",
            "name": "Pool Wasserzaehler Nachlauf",
            "min": 0,
            "max": 1800,
            "step": 10,
            "unit": "s",
        },
        {
            "key": "pool_nachspeisung_max_fill_s",
            "object_name": "pool_nachspeisung_max_fuellzeit",
            "name": "Pool Nachspeisung Max Fuellzeit",
            "min": 30,
            "max": 21600,
            "step": 30,
            "unit": "s",
        },
        {
            "key": "pool_flockung_tagesdosis_ml",
            "object_name": "pool_flockung_tagesdosis",
            "name": "Pool Flockung Tagesdosis",
            "min": 0,
            "max": 5000,
            "step": 1,
            "unit": "ml",
        },
        {
            "key": "pool_flockung_start_hour",
            "object_name": "pool_flockung_startzeit",
            "name": "Pool Flockung Startzeit",
            "min": 0,
            "max": 23,
            "step": 1,
            "unit": "h",
        },
        {
            "key": "pool_flockung_ml_pro_l_frischwasser",
            "object_name": "pool_flockung_je_l_frischwasser",
            "name": "Pool Flockung je L Frischwasser",
            "min": 0,
            "max": 100,
            "step": 0.01,
            "unit": "ml/L",
        },
        {
            "key": "pool_flockung_pumpe_ml_min",
            "object_name": "pool_flockung_pumpe_leistung",
            "name": "Pool Flockung Pumpe Leistung",
            "min": 0.1,
            "max": 1000,
            "step": 0.1,
            "unit": "ml/min",
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
