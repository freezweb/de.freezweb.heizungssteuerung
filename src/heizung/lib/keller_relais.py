"""R421B16 Relaismodul ueber Waveshare RS485-TCP-Bruecke."""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from dataclasses import dataclass
from typing import Any

from .config import AppConfig
from .state import StateStore

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RelayGroupConfig:
    name: str
    pump_component: str
    mixer_component: str
    vl_component: str
    target_channel_id: str
    pump_relay: int
    enable_relay: int
    direction_relay: int
    runtime_s: float = 120.0
    tolerance_pct: float = 1.0


@dataclass(frozen=True)
class KellerRelayConfig:
    enabled: bool
    host: str
    port: int
    unit_id: int
    protocol: str
    timeout_s: float
    command_delay_s: float
    health_poll_interval_s: float
    state_persist_path: str
    test_mode_enabled: bool
    test_pump_on: bool
    test_target_pct: float
    groups: dict[str, RelayGroupConfig]

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "KellerRelayConfig":
        raw = settings.get("keller_relais", {})
        if not isinstance(raw, dict):
            raw = {}
        raw_groups = raw.get("groups", {})
        if not isinstance(raw_groups, dict):
            raw_groups = {}

        defaults = {
            "fbh_eg": {
                "pump_component": "pumpe_fbh_eg",
                "mixer_component": "mischer_fbh_eg_pct",
                "vl_component": "fbh_eg_vl",
                "target_channel_id": "K-AO02",
                "pump_relay": 1,
                "enable_relay": 2,
                "direction_relay": 3,
            },
            "hk_backup": {
                "pump_component": "pumpe_hk_backup",
                "mixer_component": "mischer_hk_backup_pct",
                "vl_component": "hk_backup_vl",
                "target_channel_id": "K-AO04",
                "pump_relay": 4,
                "enable_relay": 5,
                "direction_relay": 6,
            },
            "klima_og": {
                "pump_component": "pumpe_klima_og",
                "mixer_component": "mischer_klima_og_pct",
                "vl_component": "klima_og_vl",
                "target_channel_id": "K-AO03",
                "pump_relay": 7,
                "enable_relay": 8,
                "direction_relay": 9,
            },
        }

        groups: dict[str, RelayGroupConfig] = {}
        for name, default in defaults.items():
            group_raw = raw_groups.get(name, {})
            if not isinstance(group_raw, dict):
                group_raw = {}
            relays = group_raw.get("relays", {})
            if not isinstance(relays, dict):
                relays = {}
            groups[name] = RelayGroupConfig(
                name=name,
                pump_component=str(group_raw.get("pump_component", default["pump_component"])),
                mixer_component=str(group_raw.get("mixer_component", default["mixer_component"])),
                vl_component=str(group_raw.get("vl_component", default["vl_component"])),
                target_channel_id=str(group_raw.get("target_channel_id", default["target_channel_id"])),
                pump_relay=int(relays.get("pump", group_raw.get("pump_relay", default["pump_relay"]))),
                enable_relay=int(relays.get("enable", group_raw.get("enable_relay", default["enable_relay"]))),
                direction_relay=int(
                    relays.get("direction", group_raw.get("direction_relay", default["direction_relay"]))
                ),
                runtime_s=max(1.0, float(group_raw.get("runtime_s", raw.get("runtime_s", 120.0)))),
                tolerance_pct=max(0.1, float(group_raw.get("tolerance_pct", raw.get("tolerance_pct", 1.0)))),
            )

        test_raw = raw.get("test_mode", {})
        if not isinstance(test_raw, dict):
            test_raw = {}

        return cls(
            enabled=bool(raw.get("enabled", False)),
            host=str(raw.get("host", "10.1.100.169")),
            port=int(raw.get("port", 26)),
            unit_id=int(raw.get("unit_id", 1)),
            protocol=str(raw.get("protocol", "modbus_tcp")).lower(),
            timeout_s=float(raw.get("timeout_s", 0.5)),
            command_delay_s=float(raw.get("command_delay_s", 0.03)),
            health_poll_interval_s=max(1.0, float(raw.get("health_poll_interval_s", 5.0))),
            state_persist_path=str(raw.get("state_persist_path", "state/keller_relais.json")),
            test_mode_enabled=bool(test_raw.get("enabled", False)),
            test_pump_on=bool(test_raw.get("pump_on", True)),
            test_target_pct=_clamp_pct(float(test_raw.get("target_pct", 100.0))),
            groups=groups,
        )


class KellerRelayClient:
    """Schreibt Pumpen und 3-Punkt-Mischer auf R421B16-Spulen.

    Die Mischerposition ist eine Laufzeit-Schaetzung. Relaisrichtung:
    direction=False -> NC/Zu, direction=True -> NO/Auf.
    """

    def __init__(self, config: KellerRelayConfig, state_store: StateStore) -> None:
        self.config = config
        self.state_store = state_store
        state = state_store.load()
        raw_positions = state.get("positions", {}) if isinstance(state, dict) else {}
        raw_runtimes = state.get("runtimes_s", {}) if isinstance(state, dict) else {}
        self.positions: dict[str, float] = {
            name: _clamp_pct(float(raw_positions.get(name, 0.0))) for name in config.groups
        }
        self.runtimes_s: dict[str, float] = {
            name: _clamp_runtime_s(float(raw_runtimes.get(name, group.runtime_s)))
            for name, group in config.groups.items()
        }
        self.targets: dict[str, float] = {
            name: self.positions.get(name, 0.0) for name in config.groups
        }
        self._moving: dict[str, int] = {name: 0 for name in config.groups}
        self._manual_move: dict[str, bool] = {name: False for name in config.groups}
        self._last_relay_states: dict[int, bool] = {}
        self._last_desired_states: dict[int, bool] = {}
        self._last_status_states: dict[int, bool] = {}
        self._last_update_monotonic = time.monotonic()
        self._last_persist_monotonic = 0.0

    async def write_outputs(
        self,
        app_config: AppConfig,
        applied_do: dict[str, bool],
        applied_ao: dict[str, float],
        manual_overrides: dict[str, bool] | None = None,
    ) -> None:
        now = time.monotonic()
        previous_positions = dict(self.positions)
        previous_moving = dict(self._moving)
        previous_update = self._last_update_monotonic
        try:
            self._advance_positions(now)
            desired: dict[int, bool] = {}

            for group in self.config.groups.values():
                self._manual_move[group.name] = False
                if self.config.test_mode_enabled:
                    pump_on = self.config.test_pump_on
                    target_pct = self.config.test_target_pct
                else:
                    pump_on = _applied_do_by_component(app_config, applied_do, group.pump_component)
                    target_pct = _target_pct(app_config, applied_ao, group.mixer_component, group.target_channel_id)
                current_pct = self.positions[group.name]
                self.targets[group.name] = target_pct

                direction = self._moving.get(group.name, 0)
                if target_pct > current_pct + group.tolerance_pct:
                    direction = 1
                elif target_pct < current_pct - group.tolerance_pct:
                    direction = -1
                else:
                    direction = 0

                self._moving[group.name] = direction
                desired[group.pump_relay] = pump_on
                desired[group.direction_relay] = direction > 0
                desired[group.enable_relay] = direction != 0
                self._apply_manual_relay_overrides(group, desired, manual_overrides or {})

            self._last_desired_states = dict(desired)
            await self._write_changed(desired)
            self._last_status_states = dict(desired)
            self._persist_if_needed(force=any(direction == 0 for direction in self._moving.values()))
        except Exception:
            self.positions = previous_positions
            self._moving = previous_moving
            self._last_update_monotonic = previous_update
            raise

    async def all_off(self) -> None:
        used_relays = sorted(
            {
                relay
                for group in self.config.groups.values()
                for relay in (group.pump_relay, group.enable_relay, group.direction_relay)
            }
        )
        await self._write_changed({relay: False for relay in used_relays}, force=True)
        self._persist_if_needed(force=True)

    async def poll_status(self) -> dict[int, bool]:
        """Liest den R421B16-Relaisstatus zyklisch per Modbus FC03."""
        states = await self._read_relay_states()
        self._last_status_states = dict(states)
        self._last_relay_states = dict(states)
        return states

    def snapshot(self) -> dict[str, dict[str, float | bool | str]]:
        payload: dict[str, dict[str, float | bool | str]] = {}
        for group in self.config.groups.values():
            direction = self._moving.get(group.name, 0)
            payload[group.name] = {
                "position_pct": round(self.positions.get(group.name, 0.0), 1),
                "target_pct": round(self.targets.get(group.name, 0.0), 1),
                "runtime_s": round(self.runtimes_s.get(group.name, group.runtime_s), 1),
                "moving": direction != 0,
                "direction": "auf" if direction > 0 else "zu" if direction < 0 else "stopp",
            }
        return payload

    def set_runtime(self, group_name: str, runtime_s: Any) -> bool:
        if group_name not in self.config.groups:
            return False
        try:
            value = _clamp_runtime_s(float(str(runtime_s).replace(",", ".")))
        except (TypeError, ValueError):
            return False
        self.runtimes_s[group_name] = value
        self._persist_if_needed(force=True)
        return True

    def _advance_positions(self, now: float) -> None:
        dt = max(0.0, now - self._last_update_monotonic)
        self._last_update_monotonic = now
        if dt <= 0:
            return
        for group in self.config.groups.values():
            direction = self._moving.get(group.name, 0)
            if direction == 0:
                continue
            runtime_s = self.runtimes_s.get(group.name, group.runtime_s)
            delta_pct = dt / runtime_s * 100.0 * direction
            next_pct = _clamp_pct(self.positions[group.name] + delta_pct)
            if self._manual_move.get(group.name):
                self.positions[group.name] = _clamp_pct(next_pct)
                if next_pct <= 0.0 or next_pct >= 100.0:
                    self._moving[group.name] = 0
                continue
            target_pct = self.targets.get(group.name, next_pct)
            if direction > 0 and next_pct >= target_pct:
                next_pct = target_pct
                self._moving[group.name] = 0
            elif direction < 0 and next_pct <= target_pct:
                next_pct = target_pct
                self._moving[group.name] = 0
            self.positions[group.name] = _clamp_pct(next_pct)

    async def _write_changed(self, desired: dict[int, bool], *, force: bool = False) -> None:
        changed = {
            relay: state
            for relay, state in sorted(desired.items())
            if force or self._last_relay_states.get(relay) is not state
        }
        for relay, state in changed.items():
            await self._write_single_relay(relay, state)
            self._last_relay_states[relay] = state
            if self.config.command_delay_s > 0:
                await asyncio.sleep(self.config.command_delay_s)

    def relay_component_states(self) -> dict[str, bool]:
        states: dict[str, bool] = {}
        relay_states = self._last_status_states or self._last_desired_states
        for group in self.config.groups.values():
            components = relay_component_names(group.name)
            states[components["pump"]] = bool(relay_states.get(group.pump_relay, False))
            states[components["enable"]] = bool(relay_states.get(group.enable_relay, False))
            states[components["direction"]] = bool(relay_states.get(group.direction_relay, False))
        return states

    def _apply_manual_relay_overrides(
        self,
        group: RelayGroupConfig,
        desired: dict[int, bool],
        manual_overrides: dict[str, bool],
    ) -> None:
        components = relay_component_names(group.name)
        has_manual = any(component in manual_overrides for component in components.values())
        if not has_manual:
            return

        if components["pump"] in manual_overrides:
            desired[group.pump_relay] = manual_overrides[components["pump"]]
        if components["enable"] in manual_overrides:
            desired[group.enable_relay] = manual_overrides[components["enable"]]
        if components["direction"] in manual_overrides:
            desired[group.direction_relay] = manual_overrides[components["direction"]]

        if components["enable"] in manual_overrides or components["direction"] in manual_overrides:
            if desired.get(group.enable_relay, False):
                self._moving[group.name] = 1 if desired.get(group.direction_relay, False) else -1
                self._manual_move[group.name] = True
            else:
                self._moving[group.name] = 0

    async def _write_single_relay(self, relay: int, on: bool) -> None:
        if relay < 1 or relay > 16:
            raise ValueError(f"R421B16 Relaisnummer ausserhalb 1..16: {relay}")
        command = 0x01 if on else 0x02
        pdu = bytes([0x06]) + struct.pack(">HBB", relay, command, 0x00)
        response = await self._request_rtu(pdu, expected_len=8)
        if response[1] & 0x80:
            raise RuntimeError(f"R421B16 Modbus Exception {response[2]}")

    async def _read_relay_states(self) -> dict[int, bool]:
        count = 16
        pdu = bytes([0x03]) + struct.pack(">HH", 1, count)
        response = await self._request_rtu(pdu, expected_len=1 + 1 + 1 + count * 2 + 2)
        if response[1] & 0x80:
            raise RuntimeError(f"R421B16 Modbus Exception {response[2]}")
        if response[1] != 0x03:
            raise RuntimeError(f"R421B16 unerwartete Funktion in Statusantwort: {response[1]}")
        byte_count = response[2]
        if byte_count != count * 2 or len(response) < 3 + byte_count:
            raise RuntimeError("R421B16 Statusantwort hat ungueltige Laenge")
        states: dict[int, bool] = {}
        for index in range(count):
            raw = struct.unpack(">H", response[3 + index * 2 : 5 + index * 2])[0]
            states[index + 1] = raw != 0
        return states

    async def _request_rtu(self, pdu: bytes, *, expected_len: int) -> bytes:
        frame = bytes([self.config.unit_id]) + pdu
        frame += _modbus_crc(frame)
        if self.config.protocol in {"modbus_tcp", "modbus_tcp_gateway", "tcp"}:
            return await self._request_modbus_tcp(pdu)

        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.config.host, self.config.port),
            self.config.timeout_s,
        )
        try:
            writer.write(frame)
            await asyncio.wait_for(writer.drain(), self.config.timeout_s)
            response = await asyncio.wait_for(reader.readexactly(expected_len), self.config.timeout_s)
        finally:
            writer.close()
            await writer.wait_closed()

        if len(response) < 4:
            raise RuntimeError("R421B16 Antwort zu kurz")
        payload, crc = response[:-2], response[-2:]
        if _modbus_crc(payload) != crc:
            raise RuntimeError("R421B16 Modbus-CRC ungueltig")
        if payload[0] != self.config.unit_id:
            raise RuntimeError(f"R421B16 falsche Unit-ID in Antwort: {payload[0]}")
        return payload

    async def _request_modbus_tcp(self, pdu: bytes) -> bytes:
        transaction_id = int(time.monotonic() * 1000) & 0xFFFF
        packet = struct.pack(">HHHB", transaction_id, 0, len(pdu) + 1, self.config.unit_id) + pdu
        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.config.host, self.config.port),
            self.config.timeout_s,
        )
        try:
            writer.write(packet)
            await asyncio.wait_for(writer.drain(), self.config.timeout_s)
            header = await asyncio.wait_for(reader.readexactly(7), self.config.timeout_s)
            response_transaction, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
            if response_transaction != transaction_id or protocol_id != 0 or length < 2:
                raise RuntimeError("R421B16 Modbus-TCP Header ungueltig")
            pdu_response = await asyncio.wait_for(reader.readexactly(length - 1), self.config.timeout_s)
        finally:
            writer.close()
            await writer.wait_closed()

        if unit_id != self.config.unit_id:
            raise RuntimeError(f"R421B16 falsche Unit-ID in Modbus-TCP Antwort: {unit_id}")
        return bytes([unit_id]) + pdu_response

    def _persist_if_needed(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_persist_monotonic < 10:
            return
        self._last_persist_monotonic = now
        self.state_store.save(
            {
                "positions": {name: round(value, 2) for name, value in sorted(self.positions.items())},
                "targets": {name: round(value, 2) for name, value in sorted(self.targets.items())},
                "runtimes_s": {name: round(value, 2) for name, value in sorted(self.runtimes_s.items())},
                "updated_ts": int(time.time()),
            }
        )


def _modbus_crc(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


def _applied_do_by_component(app_config: AppConfig, applied_do: dict[str, bool], component: str) -> bool:
    channel = app_config.io_map.by_component(component)
    if channel is None or channel.kind != "do":
        log.warning("Keller-Relais: DO-Komponente fehlt in IO-Map: %s", component)
        return False
    return bool(applied_do.get(channel.id, False))


def _target_pct(
    app_config: AppConfig,
    applied_ao: dict[str, float],
    component: str,
    fallback_channel_id: str,
) -> float:
    channel = app_config.io_map.by_component(component)
    if channel is not None and channel.kind == "ao":
        return _clamp_pct(float(applied_ao.get(channel.id, 0.0)))
    return _clamp_pct(float(applied_ao.get(fallback_channel_id, 0.0)))


def relay_component_names(group_name: str) -> dict[str, str]:
    return {
        "pump": f"r421_{group_name}_pumpe",
        "enable": f"r421_{group_name}_fahrt",
        "direction": f"r421_{group_name}_richtung",
    }


def _clamp_pct(value: float) -> float:
    return max(0.0, min(100.0, value))


def _clamp_runtime_s(value: float) -> float:
    return max(10.0, min(900.0, value))
