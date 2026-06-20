"""Keller-RevPi als reiner Modbus-TCP I/O-Slave."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time

from .lib.config import AppConfig, ConfigError
from .lib.intercpu import (
    STATUS_IO_OK,
    STATUS_MASTER_FRESH,
    STATUS_READY,
    ModbusTcpRegisterServer,
    RegisterBank,
    decode_output_registers,
    encode_input_registers,
)
from .lib.iohw import BaseIO, create_io_backend

log = logging.getLogger("heizung.keller_slave")


async def run() -> int:
    try:
        app_config = AppConfig.load()
    except ConfigError as exc:
        log.error("Konfiguration ungueltig: %s", exc)
        return 2

    cycle_s = float(app_config.setting("intercpu.keller_slave.zyklus_ms", 500)) / 1000
    watchdog_s = float(app_config.setting("intercpu.keller_slave.watchdog_s", 5.0))
    host = str(app_config.setting("intercpu.keller_slave.host", "0.0.0.0"))
    port = int(app_config.setting("intercpu.keller_slave.port", 502))
    led_settings = app_config.setting("leds", {})
    heartbeat_interval_s = float(
        (led_settings or {}).get("heartbeat_interval_s", 1.0) if isinstance(led_settings, dict) else 1.0
    )
    led_update_s = min(0.5, max(0.2, heartbeat_interval_s))

    io_backend = create_io_backend(app_config.io_map, os.environ.get("HEIZUNG_IO_BACKEND", "auto"))
    bank = RegisterBank()
    server = ModbusTcpRegisterServer(bank, host=host, port=port)
    server_task = asyncio.create_task(server.serve_forever())

    stop = asyncio.Event()

    def _handle_sig() -> None:
        log.info("Signal empfangen, beende Keller-Slave ...")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_sig)
        except NotImplementedError:
            pass

    log.info("Keller-Slave gestartet, Zyklus %.3fs, Watchdog %.1fs", cycle_s, watchdog_s)
    cycle_count = 0
    boot_ts = time.time()
    last_led_ts = 0.0
    last_master_fresh: bool | None = None
    applied_do = {channel_id: False for channel_id in app_config.io_map.do}
    applied_ao = {channel_id: 0.0 for channel_id in app_config.io_map.ao}
    try:
        while not stop.is_set():
            started = time.monotonic()
            now_ts = time.time()
            holding = await bank.snapshot_holding()
            command_counter, enabled, desired_do, desired_ao = decode_output_registers(app_config.io_map, holding)
            master_fresh = bank.last_write_ts is not None and now_ts - bank.last_write_ts <= watchdog_s
            if not enabled or not master_fresh:
                desired_do = {channel_id: False for channel_id in app_config.io_map.do}
                desired_ao = {channel_id: 0.0 for channel_id in app_config.io_map.ao}

            outputs_changed = last_master_fresh is None or desired_do != applied_do or _ao_changed(desired_ao, applied_ao)
            watchdog_changed = last_master_fresh is not None and last_master_fresh != master_fresh
            if outputs_changed or watchdog_changed:
                applied_do, applied_ao = await _write_outputs(io_backend, app_config, desired_do, desired_ao)
            last_master_fresh = master_fresh
            snapshot = await io_backend.read_all()
            status = STATUS_READY | STATUS_IO_OK | (STATUS_MASTER_FRESH if master_fresh else 0)
            await bank.update_input(
                encode_input_registers(
                    app_config.io_map,
                    snapshot,
                    applied_do,
                    applied_ao,
                    status=status,
                    command_counter=command_counter,
                )
            )

            cycle_count += 1
            if now_ts - last_led_ts >= led_update_s:
                last_led_ts = now_ts
                await io_backend.set_cpu_leds(
                    {
                        "A1": _heartbeat_led_color(now_ts, boot_ts, heartbeat_interval_s),
                        "A2": "green" if master_fresh else "red",
                        "A3": "off",
                        "A4": "off",
                        "A5": "off",
                    }
                )
            await _sleep_remaining(stop, cycle_s, started)
    finally:
        server_task.cancel()
        await server.close()
        await _write_outputs(
            io_backend,
            app_config,
            {channel_id: False for channel_id in app_config.io_map.do},
            {channel_id: 0.0 for channel_id in app_config.io_map.ao},
        )
        await io_backend.set_cpu_leds({"A1": "off", "A2": "off", "A3": "off", "A4": "off", "A5": "off"})
        await io_backend.close()
    return 0


async def _write_outputs(
    io_backend: BaseIO,
    app_config: AppConfig,
    do_values: dict[str, bool],
    ao_values: dict[str, float],
) -> tuple[dict[str, bool], dict[str, float]]:
    applied_do: dict[str, bool] = {}
    applied_ao: dict[str, float] = {}
    for channel_id, channel in app_config.io_map.do.items():
        value = bool(do_values.get(channel_id, False))
        await io_backend.write_do(channel, value)
        applied_do[channel_id] = value
    for channel_id, channel in app_config.io_map.ao.items():
        value = float(ao_values.get(channel_id, 0.0))
        await io_backend.write_ao(channel, value)
        applied_ao[channel_id] = value
    return applied_do, applied_ao


def _ao_changed(desired: dict[str, float], applied: dict[str, float], tolerance: float = 0.05) -> bool:
    keys = set(desired) | set(applied)
    return any(abs(float(desired.get(key, 0.0)) - float(applied.get(key, 0.0))) > tolerance for key in keys)


def _heartbeat_led_color(now_ts: float, boot_ts: float, interval_s: float) -> str:
    interval_s = max(0.2, float(interval_s))
    return "blue" if int((now_ts - boot_ts) / interval_s) % 2 else "yellow"


async def _sleep_remaining(stop: asyncio.Event, cycle_s: float, started: float) -> None:
    remaining = max(0.0, cycle_s - (time.monotonic() - started))
    try:
        await asyncio.wait_for(stop.wait(), timeout=remaining)
    except TimeoutError:
        return


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
