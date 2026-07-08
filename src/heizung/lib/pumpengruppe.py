"""Modbus-TCP Client fuer dezentrale Pumpengruppen-Boards."""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass
from typing import Any


HR_COMMAND_SEQ = 0
HR_PUMP = 1
HR_TARGET_PCT_X10 = 2
HR_MODE = 3

IR_STATUS = 0
IR_POSITION_PCT_X10 = 1
IR_VL_TEMP_X10 = 2
IR_RL_TEMP_X10 = 3
IR_LAST_COMMAND_SEQ = 4
IR_FAULT_CODE = 5

MODE_AUTO = 0


@dataclass(frozen=True)
class PumpGroupConfig:
    name: str
    enabled: bool = False
    host: str = ""
    port: int = 502
    unit_id: int = 30
    timeout_s: float = 0.5
    poll_interval_s: float = 1.0
    pump_component: str = ""
    mixer_component: str = ""
    vl_component: str = ""
    rl_component: str = ""
    disable_local_outputs: bool = True

    @classmethod
    def from_settings(cls, name: str, raw: dict[str, Any]) -> "PumpGroupConfig":
        return cls(
            name=name,
            enabled=bool(raw.get("enabled", False)),
            host=str(raw.get("host", "")),
            port=int(raw.get("port", 502)),
            unit_id=int(raw.get("unit_id", 30)),
            timeout_s=float(raw.get("timeout_s", 0.5)),
            poll_interval_s=float(raw.get("poll_interval_s", 1.0)),
            pump_component=str(raw.get("pump_component", "")),
            mixer_component=str(raw.get("mixer_component", "")),
            vl_component=str(raw.get("vl_component", "")),
            rl_component=str(raw.get("rl_component", "")),
            disable_local_outputs=bool(raw.get("disable_local_outputs", True)),
        )


@dataclass(frozen=True)
class PumpGroupSnapshot:
    online: bool
    status: int = 0
    position_pct: float | None = None
    vl_temp_c: float | None = None
    rl_temp_c: float | None = None
    last_command_seq: int = 0
    fault_code: int = 0

    @property
    def moving(self) -> bool:
        return bool(self.status & (1 << 2))

    @property
    def pump_on(self) -> bool:
        return bool(self.status & (1 << 3))


class PumpGroupModbusClient:
    def __init__(self, config: PumpGroupConfig) -> None:
        self.config = config
        self.command_seq = 0
        self._last_pump_on: bool | None = None
        self._last_target_x10: int | None = None

    async def read_snapshot(self) -> PumpGroupSnapshot:
        regs = await self._read_registers(4, 0, 9)
        return PumpGroupSnapshot(
            online=True,
            status=regs[IR_STATUS],
            position_pct=_uint16_to_int16(regs[IR_POSITION_PCT_X10]) / 10.0,
            vl_temp_c=_uint16_to_int16(regs[IR_VL_TEMP_X10]) / 10.0,
            rl_temp_c=_uint16_to_int16(regs[IR_RL_TEMP_X10]) / 10.0,
            last_command_seq=regs[IR_LAST_COMMAND_SEQ],
            fault_code=regs[IR_FAULT_CODE],
        )

    async def write_command(self, *, pump_on: bool, target_pct: float) -> None:
        target_x10 = int(round(max(0.0, min(100.0, target_pct)) * 10.0))
        if self._last_pump_on == pump_on and self._last_target_x10 == target_x10:
            return
        self.command_seq = (self.command_seq + 1) & 0xFFFF
        await self._write_registers(
            0,
            [
                self.command_seq,
                1 if pump_on else 0,
                target_x10,
                MODE_AUTO,
            ],
        )
        self._last_pump_on = pump_on
        self._last_target_x10 = target_x10

    async def _read_registers(self, function: int, address: int, count: int) -> list[int]:
        if function not in (3, 4):
            raise ValueError(f"Modbus-Funktion {function} wird fuer Pumpengruppen nicht unterstuetzt")
        response = await self._request(bytes([function]) + struct.pack(">HH", address, count))
        if response[0] & 0x80:
            raise RuntimeError(f"Modbus Exception {response[1]}")
        byte_count = response[1]
        raw = response[2 : 2 + byte_count]
        return [struct.unpack(">H", raw[i : i + 2])[0] for i in range(0, len(raw), 2)]

    async def _write_registers(self, address: int, values: list[int]) -> None:
        payload = b"".join(struct.pack(">H", _uint16(value)) for value in values)
        pdu = bytes([16]) + struct.pack(">HHB", address, len(values), len(payload)) + payload
        response = await self._request(pdu)
        if response[0] & 0x80:
            raise RuntimeError(f"Modbus Exception {response[1]}")

    async def _request(self, pdu: bytes) -> bytes:
        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.config.host, self.config.port),
            self.config.timeout_s,
        )
        try:
            packet = struct.pack(">HHHB", 1, 0, len(pdu) + 1, self.config.unit_id) + pdu
            writer.write(packet)
            await asyncio.wait_for(writer.drain(), self.config.timeout_s)
            header = await asyncio.wait_for(reader.readexactly(7), self.config.timeout_s)
            _transaction_id, protocol_id, length, _unit_id = struct.unpack(">HHHB", header)
            if protocol_id != 0 or length < 2:
                raise RuntimeError("Ungueltiger Modbus-TCP-Header")
            return await asyncio.wait_for(reader.readexactly(length - 1), self.config.timeout_s)
        finally:
            writer.close()
            await writer.wait_closed()


def pump_group_configs_from_settings(settings: dict[str, Any]) -> dict[str, PumpGroupConfig]:
    raw = settings.get("pumpengruppen", {})
    if not isinstance(raw, dict):
        return {}
    configs: dict[str, PumpGroupConfig] = {}
    for name, group_raw in raw.items():
        if isinstance(group_raw, dict):
            config = PumpGroupConfig.from_settings(str(name), group_raw)
            if config.enabled and config.host:
                configs[config.name] = config
    return configs


def _uint16(value: int) -> int:
    return max(0, min(0xFFFF, int(value)))


def _uint16_to_int16(value: int) -> int:
    value = _uint16(value)
    return value - 0x10000 if value & 0x8000 else value
