"""Modbus-TCP Leser fuer den Brunnen-Durchflusszaehler."""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FlowmeterModbusConfig:
    enabled: bool = False
    host: str = "wasserverbrauch-pumpe.local"
    port: int = 502
    unit_id: int = 1
    register: int = 0
    function: int = 4
    scale: float = 100.0
    timeout_s: float = 0.3
    poll_interval_s: float = 1.0

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "FlowmeterModbusConfig":
        raw = _setting(settings, "brunnen.flow_modbus", {})
        if not isinstance(raw, dict):
            raw = {}
        register_type = str(raw.get("register_type", raw.get("type", "input"))).strip().lower()
        function = int(raw.get("function", 4 if register_type in {"input", "input_register"} else 3))
        return cls(
            enabled=bool(raw.get("enabled", False)),
            host=str(raw.get("host", "wasserverbrauch-pumpe.local")),
            port=int(raw.get("port", 502)),
            unit_id=int(raw.get("unit_id", 1)),
            register=int(raw.get("register", 0)),
            function=function,
            scale=float(raw.get("scale", 100.0)),
            timeout_s=float(raw.get("timeout_s", 0.3)),
            poll_interval_s=float(raw.get("poll_interval_s", 1.0)),
        )


class FlowmeterModbusClient:
    def __init__(self, config: FlowmeterModbusConfig) -> None:
        self.config = config

    async def read_flow_l_min(self) -> float:
        value = await self._read_register(self.config.function, self.config.register)
        scale = self.config.scale if self.config.scale else 1.0
        return max(0.0, value / scale)

    async def _read_register(self, function: int, address: int) -> int:
        if function not in (3, 4):
            raise ValueError(f"Modbus-Funktion {function} wird fuer Flowmeter nicht unterstuetzt")
        pdu = bytes([function]) + struct.pack(">HH", address, 1)
        response = await self._request(pdu)
        if response[0] & 0x80:
            raise RuntimeError(f"Modbus Exception {response[1]}")
        if response[1] != 2:
            raise RuntimeError(f"Ungueltige Modbus-Antwortlaenge: {response[1]}")
        return struct.unpack(">H", response[2:4])[0]

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
            _transaction_id, _protocol_id, length, _unit_id = struct.unpack(">HHHB", header)
            return await asyncio.wait_for(reader.readexactly(length - 1), self.config.timeout_s)
        finally:
            writer.close()
            await writer.wait_closed()


def _setting(settings: dict[str, Any], path: str, default: Any) -> Any:
    node: Any = settings
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
