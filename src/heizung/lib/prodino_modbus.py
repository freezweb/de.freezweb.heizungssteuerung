"""Modbus-TCP Client fuer den KMP Prodino Pool-I/O."""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass

from .pool import PoolProdinoConfig


@dataclass(frozen=True)
class ProdinoPoolSnapshot:
    online: bool
    relays: dict[int, bool]
    inputs: dict[int, bool]
    uptime_s: int = 0
    firmware_version: int = 0


class ProdinoPoolModbusClient:
    def __init__(self, config: PoolProdinoConfig) -> None:
        self.config = config
        self._transaction_id = 0
        self._last_relays: dict[int, bool] = {}

    async def read_snapshot(self) -> ProdinoPoolSnapshot:
        regs = await self._read_registers(function=3, address=0, count=5)
        uptime_s = (regs[1] << 16) | regs[0]
        relay_mask = regs[2]
        input_mask = regs[3]
        relays = {idx + 1: bool(relay_mask & (1 << idx)) for idx in range(4)}
        self._last_relays = dict(relays)
        return ProdinoPoolSnapshot(
            online=True,
            relays=relays,
            inputs={idx + 1: bool(input_mask & (1 << idx)) for idx in range(4)},
            uptime_s=uptime_s,
            firmware_version=regs[4],
        )

    async def write_outputs(self, *, valve_open: bool, dosing_pump_on: bool) -> None:
        desired = {1: valve_open, 2: dosing_pump_on}
        for relay, value in desired.items():
            if self._last_relays.get(relay) == value:
                continue
            await self._write_single_coil(relay - 1, value)
            self._last_relays[relay] = value

    def reset_cache(self) -> None:
        self._last_relays.clear()

    async def all_off(self) -> None:
        await self.write_outputs(valve_open=False, dosing_pump_on=False)

    async def _read_registers(self, *, function: int, address: int, count: int) -> list[int]:
        if function != 3:
            raise ValueError("Prodino unterstuetzt hier nur FC03")
        response = await self._request(bytes([function]) + struct.pack(">HH", address, count))
        if response[0] & 0x80:
            raise RuntimeError(f"Prodino Modbus Exception {response[1]}")
        byte_count = response[1]
        raw = response[2 : 2 + byte_count]
        return [struct.unpack(">H", raw[i : i + 2])[0] for i in range(0, len(raw), 2)]

    async def _write_single_coil(self, address: int, value: bool) -> None:
        pdu = bytes([5]) + struct.pack(">HH", address, 0xFF00 if value else 0x0000)
        response = await self._request(pdu)
        if response[0] & 0x80:
            raise RuntimeError(f"Prodino Modbus Exception {response[1]}")

    async def _request(self, pdu: bytes) -> bytes:
        self._transaction_id = (self._transaction_id + 1) & 0xFFFF
        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.config.host, self.config.port),
            self.config.timeout_s,
        )
        try:
            packet = struct.pack(">HHHB", self._transaction_id, 0, len(pdu) + 1, self.config.unit_id) + pdu
            writer.write(packet)
            await asyncio.wait_for(writer.drain(), self.config.timeout_s)
            header = await asyncio.wait_for(reader.readexactly(7), self.config.timeout_s)
            transaction_id, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
            if transaction_id != self._transaction_id or protocol_id != 0 or length < 2:
                raise RuntimeError("Ungueltiger Prodino Modbus-TCP Header")
            if unit_id != self.config.unit_id:
                raise RuntimeError(f"Prodino falsche Unit-ID in Antwort: {unit_id}")
            return await asyncio.wait_for(reader.readexactly(length - 1), self.config.timeout_s)
        finally:
            writer.close()
            await writer.wait_closed()
