"""Heizungssteuerung Hauptprogramm."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from typing import Any

from .lib.config import AppConfig, ChannelConfig, ConfigError
from .lib.failsafe import FailsafeMonitor, FailsafeState
from .lib.hand_auto import HandAutoManager
from .lib.iohw import BaseIO, HardwareSnapshot, create_io_backend
from .lib.mqtt_bridge import MqttBridge
from .lib.routing import RoutingState, compute_routing
from .lib.state import StateStore

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

    io_backend = create_io_backend(app_config.io_map, os.environ.get("HEIZUNG_IO_BACKEND", "auto"))
    hand_auto = HandAutoManager(app_config.io_map, StateStore(hand_state_path), default_hand_timeout)
    failsafe_monitor = FailsafeMonitor.from_settings(app_config.settings)
    mqtt = MqttBridge(app_config.mqtt)
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
    try:
        while not stop.is_set():
            started = time.monotonic()
            now_ts = time.time()

            snapshot = await io_backend.read_all()
            await _handle_mqtt_commands(
                mqtt,
                app_config,
                hand_auto,
                failsafe_monitor,
                io_backend,
                now_ts,
            )

            failsafe_state = failsafe_monitor.evaluate(
                now_ts=now_ts,
                mqtt_connected=mqtt.connected,
                last_mqtt_seen_ts=mqtt.last_seen_ts,
                last_ha_heartbeat_ts=mqtt.last_ha_heartbeat_ts,
                outside_temp_c=_sensor_value_by_component(app_config, snapshot, "aussen"),
            )

            routing_state, auto_do, auto_ao = _compute_auto_outputs(app_config, mqtt, failsafe_state)
            await _write_outputs(app_config, io_backend, hand_auto, auto_do, auto_ao, now_ts)

            _publish_state(mqtt, app_config, snapshot, failsafe_state, hand_auto, routing_state)
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
    failsafe_monitor: FailsafeMonitor,
    io_backend: BaseIO,
    now_ts: float,
) -> None:
    for command in mqtt.drain_commands():
        if command.typ == "failsafe_force":
            failsafe_monitor.force = str(command.payload).strip().lower() in {"1", "true", "on", "ja"}
            continue

        channel = app_config.io_map.by_component(command.name)
        if channel is None:
            log.warning("MQTT-Kommando fuer unbekannte Komponente ignoriert: %s", command.name)
            continue

        if command.typ == "hand_set":
            wert = _extract_hand_value(command.payload)
            hand_auto.set_hand(channel.id, _coerce_output_value(channel, wert), now_ts)
        elif command.typ == "hand_auto":
            hand_auto.set_auto(channel.id)
        elif command.typ == "pulse" and channel.kind == "do":
            duration_ms = channel.impuls_ms or 250
            await io_backend.pulse(channel, duration_ms)


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
    failsafe_state: FailsafeState,
) -> tuple[RoutingState, dict[str, bool], dict[str, float]]:
    routing_state, routed_do, routed_ao = compute_routing(app_config.settings, mqtt.demands, failsafe_state)
    auto = {channel_id: False for channel_id in app_config.io_map.do}
    for channel_id, value in routed_do.items():
        if channel_id in auto:
            auto[channel_id] = value
    auto_ao = {channel_id: 0.0 for channel_id in app_config.io_map.ao}
    for channel_id, value in routed_ao.items():
        if channel_id in auto_ao:
            auto_ao[channel_id] = value
    return routing_state, auto, auto_ao


async def _write_outputs(
    app_config: AppConfig,
    io_backend: BaseIO,
    hand_auto: HandAutoManager,
    auto_do: dict[str, bool],
    auto_ao: dict[str, float],
    now_ts: float,
) -> None:
    for channel_id, channel in app_config.io_map.do.items():
        value, _hand = hand_auto.apply(channel, auto_do.get(channel_id, False), now_ts)
        await io_backend.write_do(channel, bool(value))

    for channel_id, channel in app_config.io_map.ao.items():
        value, _hand = hand_auto.apply(channel, auto_ao.get(channel_id, 0.0), now_ts)
        await io_backend.write_ao(channel, float(value))


def _publish_state(
    mqtt: MqttBridge,
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
    failsafe_state: FailsafeState,
    hand_auto: HandAutoManager,
    routing_state: RoutingState,
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

    for name, demand in mqtt.demands.items():
        mqtt.publish_json(
            f"{base}/anforderung/{name}/aktuell",
            {"aktiv": demand.aktiv, "vl_soll": demand.vl_soll, "quelle": demand.quelle},
            retain=True,
        )

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


def _coerce_output_value(channel: ChannelConfig, value: Any) -> Any:
    if channel.kind == "do":
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "on", "ja"}
        return bool(value)
    if isinstance(value, str):
        value = value.replace(",", ".")
    return float(value)


def _sensor_value_by_component(app_config: AppConfig, snapshot: HardwareSnapshot, component: str) -> float | None:
    for channel_id, channel in app_config.io_map.rtd.items():
        if channel.komponente == component:
            return snapshot.rtd.get(channel_id)
    for channel_id, channel in app_config.io_map.ai.items():
        if channel.komponente == component:
            return snapshot.ai.get(channel_id)
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
