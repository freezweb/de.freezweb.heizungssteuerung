"""Modbus-TCP Kopplung zwischen Haupt- und Keller-RevPi."""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from dataclasses import dataclass, field
from typing import Any

from .config import ChannelConfig, IoMap
from .iohw import HardwareSnapshot

log = logging.getLogger(__name__)

HR_COMMAND_COUNTER = 0
HR_ENABLE = 1
HR_DO_MASK = 10
HR_AO_BASE = 20

IR_STATUS = 0
IR_LAST_COMMAND_COUNTER = 1
IR_DO_FEEDBACK = 10
IR_AO_BASE = 20
IR_AI_BASE = 100
IR_RTD_BASE = 120

STATUS_READY = 1 << 0
STATUS_MASTER_FRESH = 1 << 1
STATUS_IO_OK = 1 << 2

REGISTER_COUNT = 160
AO_SCALE = 10.0
AI_SCALE = 100.0
RTD_SCALE = 10.0
SENSOR_MISSING = 0x8000


@dataclass
class RegisterBank:
    holding: list[int] = field(default_factory=lambda: [0] * REGISTER_COUNT)
    input: list[int] = field(default_factory=lambda: [0] * REGISTER_COUNT)
    last_write_ts: float | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def read_holding(self, address: int, count: int) -> list[int]:
        async with self.lock:
            return self._read(self.holding, address, count)

    async def read_input(self, address: int, count: int) -> list[int]:
        async with self.lock:
            return self._read(self.input, address, count)

    async def write_holding(self, address: int, values: list[int]) -> None:
        async with self.lock:
            self._write(self.holding, address, values)
            self.last_write_ts = time.time()

    async def snapshot_holding(self) -> list[int]:
        async with self.lock:
            return list(self.holding)

    async def update_input(self, values: dict[int, int]) -> None:
        async with self.lock:
            for address, value in values.items():
                if 0 <= address < len(self.input):
                    self.input[address] = _uint16(value)

    @staticmethod
    def _read(registers: list[int], address: int, count: int) -> list[int]:
        if address < 0 or count < 1 or address + count > len(registers):
            raise ModbusError(2)
        return registers[address : address + count]

    @staticmethod
    def _write(registers: list[int], address: int, values: list[int]) -> None:
        if address < 0 or address + len(values) > len(registers):
            raise ModbusError(2)
        for offset, value in enumerate(values):
            registers[address + offset] = _uint16(value)


class ModbusError(Exception):
    def __init__(self, code: int) -> None:
        self.code = code


class ModbusTcpRegisterServer:
    def __init__(self, bank: RegisterBank, host: str = "0.0.0.0", port: int = 502) -> None:
        self.bank = bank
        self.host = host
        self.port = port
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        log.info("Keller-Modbus-Server lauscht auf %s:%s", self.host, self.port)

    async def serve_forever(self) -> None:
        if self._server is None:
            await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def close(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while not reader.at_eof():
                header = await reader.readexactly(7)
                transaction_id, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
                if protocol_id != 0 or length < 2:
                    break
                pdu = await reader.readexactly(length - 1)
                response = await self._handle_pdu(pdu)
                packet = struct.pack(">HHHB", transaction_id, 0, len(response) + 1, unit_id) + response
                writer.write(packet)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            return
        finally:
            writer.close()
            await writer.wait_closed()

    async def _handle_pdu(self, pdu: bytes) -> bytes:
        if not pdu:
            raise ModbusError(1)
        function = pdu[0]
        try:
            if function in (3, 4):
                address, count = struct.unpack(">HH", pdu[1:5])
                if count * 2 > 255:
                    raise ModbusError(3)
                values = (
                    await self.bank.read_holding(address, count)
                    if function == 3
                    else await self.bank.read_input(address, count)
                )
                return bytes([function, count * 2]) + b"".join(struct.pack(">H", value) for value in values)
            if function == 6:
                address, value = struct.unpack(">HH", pdu[1:5])
                await self.bank.write_holding(address, [value])
                return pdu[:5]
            if function == 16:
                address, count, byte_count = struct.unpack(">HHB", pdu[1:6])
                raw = pdu[6 : 6 + byte_count]
                values = [struct.unpack(">H", raw[i : i + 2])[0] for i in range(0, len(raw), 2)]
                if count != len(values):
                    raise ModbusError(3)
                await self.bank.write_holding(address, values)
                return bytes([function]) + struct.pack(">HH", address, count)
            raise ModbusError(1)
        except ModbusError as exc:
            return bytes([function | 0x80, exc.code])


class KellerModbusClient:
    def __init__(self, host: str, port: int, io_map: IoMap, timeout_s: float = 1.0) -> None:
        self.host = host
        self.port = port
        self.io_map = io_map
        self.timeout_s = timeout_s
        self.command_counter = 0

    async def read_snapshot(self) -> HardwareSnapshot:
        input_regs = await self._request_registers_chunked(4, 0, REGISTER_COUNT)
        ai = {
            channel_id: _decode_optional(input_regs[IR_AI_BASE + index], AI_SCALE)
            for index, channel_id in enumerate(_ordered_ids(self.io_map.ai))
        }
        rtd = {
            channel_id: _decode_optional(input_regs[IR_RTD_BASE + index], RTD_SCALE)
            for index, channel_id in enumerate(_ordered_ids(self.io_map.rtd))
        }
        do_mask = input_regs[IR_DO_FEEDBACK]
        do = {channel_id: bool(do_mask & (1 << index)) for index, channel_id in enumerate(_ordered_ids(self.io_map.do))}
        ao = {
            channel_id: input_regs[IR_AO_BASE + index] / AO_SCALE
            for index, channel_id in enumerate(_ordered_ids(self.io_map.ao))
        }
        return HardwareSnapshot(ai=ai, rtd=rtd, do=do, ao=ao)

    async def write_outputs(self, do_values: dict[str, bool], ao_values: dict[str, float], enabled: bool = True) -> None:
        self.command_counter = (self.command_counter + 1) & 0xFFFF
        values = [0] * 32
        values[HR_COMMAND_COUNTER] = self.command_counter
        values[HR_ENABLE] = 1 if enabled else 0
        values[HR_DO_MASK] = _encode_do_mask(self.io_map, do_values)
        for index, channel_id in enumerate(_ordered_ids(self.io_map.ao)):
            values[HR_AO_BASE + index] = int(round(max(0.0, ao_values.get(channel_id, 0.0)) * AO_SCALE))
        await self._write_registers(0, values)

    async def _request_registers(self, function: int, address: int, count: int) -> list[int]:
        response = await self._request(bytes([function]) + struct.pack(">HH", address, count))
        if response[0] & 0x80:
            raise RuntimeError(f"Modbus Exception {response[1]}")
        byte_count = response[1]
        raw = response[2 : 2 + byte_count]
        return [struct.unpack(">H", raw[i : i + 2])[0] for i in range(0, len(raw), 2)]

    async def _request_registers_chunked(self, function: int, address: int, count: int) -> list[int]:
        values: list[int] = []
        remaining = count
        current_address = address
        while remaining > 0:
            chunk = min(remaining, 100)
            values.extend(await self._request_registers(function, current_address, chunk))
            current_address += chunk
            remaining -= chunk
        return values

    async def _write_registers(self, address: int, values: list[int]) -> None:
        payload = b"".join(struct.pack(">H", _uint16(value)) for value in values)
        pdu = bytes([16]) + struct.pack(">HHB", address, len(values), len(payload)) + payload
        response = await self._request(pdu)
        if response[0] & 0x80:
            raise RuntimeError(f"Modbus Exception {response[1]}")

    async def _request(self, pdu: bytes) -> bytes:
        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter
        reader, writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), self.timeout_s)
        try:
            packet = struct.pack(">HHHB", 1, 0, len(pdu) + 1, 1) + pdu
            writer.write(packet)
            await asyncio.wait_for(writer.drain(), self.timeout_s)
            header = await asyncio.wait_for(reader.readexactly(7), self.timeout_s)
            _transaction_id, _protocol_id, length, _unit_id = struct.unpack(">HHHB", header)
            return await asyncio.wait_for(reader.readexactly(length - 1), self.timeout_s)
        finally:
            writer.close()
            await writer.wait_closed()


def encode_input_registers(io_map: IoMap, snapshot: HardwareSnapshot, applied_do: dict[str, bool], applied_ao: dict[str, float], *, status: int, command_counter: int) -> dict[int, int]:
    values: dict[int, int] = {
        IR_STATUS: status,
        IR_LAST_COMMAND_COUNTER: command_counter,
        IR_DO_FEEDBACK: _encode_do_mask(io_map, applied_do),
    }
    for index, channel_id in enumerate(_ordered_ids(io_map.ao)):
        values[IR_AO_BASE + index] = int(round(max(0.0, applied_ao.get(channel_id, 0.0)) * AO_SCALE))
    for index, channel_id in enumerate(_ordered_ids(io_map.ai)):
        values[IR_AI_BASE + index] = _encode_optional(snapshot.ai.get(channel_id), AI_SCALE)
    for index, channel_id in enumerate(_ordered_ids(io_map.rtd)):
        values[IR_RTD_BASE + index] = _encode_optional(snapshot.rtd.get(channel_id), RTD_SCALE)
    return values


def decode_output_registers(io_map: IoMap, holding: list[int]) -> tuple[int, bool, dict[str, bool], dict[str, float]]:
    command_counter = holding[HR_COMMAND_COUNTER]
    enabled = bool(holding[HR_ENABLE])
    do_mask = holding[HR_DO_MASK]
    do = {channel_id: bool(do_mask & (1 << index)) for index, channel_id in enumerate(_ordered_ids(io_map.do))}
    ao = {
        channel_id: holding[HR_AO_BASE + index] / AO_SCALE
        for index, channel_id in enumerate(_ordered_ids(io_map.ao))
    }
    return command_counter, enabled, do, ao


def _encode_do_mask(io_map: IoMap, values: dict[str, bool]) -> int:
    mask = 0
    for index, channel_id in enumerate(_ordered_ids(io_map.do)):
        if values.get(channel_id, False):
            mask |= 1 << index
    return mask


def _ordered_ids(channels: dict[str, ChannelConfig]) -> list[str]:
    return sorted(channels)


def _encode_optional(value: float | None, scale: float) -> int:
    if value is None:
        return SENSOR_MISSING
    return _int16_to_uint16(int(round(value * scale)))


def _decode_optional(value: int, scale: float) -> float | None:
    if value == SENSOR_MISSING:
        return None
    return _uint16_to_int16(value) / scale


def _uint16(value: int) -> int:
    return max(0, min(0xFFFF, int(value)))


def _int16_to_uint16(value: int) -> int:
    return int(value) & 0xFFFF


def _uint16_to_int16(value: int) -> int:
    value = _uint16(value)
    return value - 0x10000 if value & 0x8000 else value
