"""Leser fuer Brunnen-Durchfluss und Wasserzaehler."""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass
from typing import Any
from urllib.request import urlopen


@dataclass(frozen=True)
class FlowmeterSnapshot:
    flow_l_min: float
    total_l: float | None = None


@dataclass(frozen=True)
class WatermeterHttpSnapshot:
    total_l: float
    value: float
    raw: str


@dataclass(frozen=True)
class FlowmeterModbusConfig:
    enabled: bool = False
    host: str = "wasserverbrauch-pumpe.local"
    port: int = 502
    unit_id: int = 1
    register: int = 0
    function: int = 4
    scale: float = 100.0
    total_register: int = 1
    total_scale: float = 1000.0
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
            total_register=int(raw.get("total_register", 1)),
            total_scale=float(raw.get("total_scale", 1000.0)),
            timeout_s=float(raw.get("timeout_s", 0.3)),
            poll_interval_s=float(raw.get("poll_interval_s", 1.0)),
        )


@dataclass(frozen=True)
class WatermeterHttpConfig:
    enabled: bool = False
    url: str = "http://10.1.20.191/value?all=true&type=value"
    number_name: str = "zaehlerstand"
    total_scale_l_per_unit: float = 1000.0
    timeout_s: float = 2.0
    poll_interval_s: float = 10.0
    mqtt_mirror_enabled: bool = True
    mqtt_topic_base: str = "watermeter/zaehlerstand"

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "WatermeterHttpConfig":
        raw = _setting(settings, "brunnen.watermeter_http", {})
        if not isinstance(raw, dict):
            raw = {}
        return cls(
            enabled=bool(raw.get("enabled", False)),
            url=str(raw.get("url", "http://10.1.20.191/value?all=true&type=value")),
            number_name=str(raw.get("number_name", "zaehlerstand")),
            total_scale_l_per_unit=float(raw.get("total_scale_l_per_unit", 1000.0)),
            timeout_s=float(raw.get("timeout_s", 2.0)),
            poll_interval_s=float(raw.get("poll_interval_s", 10.0)),
            mqtt_mirror_enabled=bool(raw.get("mqtt_mirror_enabled", True)),
            mqtt_topic_base=str(raw.get("mqtt_topic_base", "watermeter/zaehlerstand")).strip("/"),
        )


class FlowmeterModbusClient:
    def __init__(self, config: FlowmeterModbusConfig) -> None:
        self.config = config

    async def read_flow_l_min(self) -> float:
        value = await self._read_register(self.config.function, self.config.register)
        scale = self.config.scale if self.config.scale else 1.0
        return max(0.0, value / scale)

    async def read_snapshot(self) -> FlowmeterSnapshot:
        flow = await self.read_flow_l_min()
        total_l: float | None = None
        try:
            total_l = await self.read_total_l()
        except Exception:
            total_l = None
        return FlowmeterSnapshot(flow_l_min=flow, total_l=total_l)

    async def read_total_l(self) -> float:
        hi, lo = await self._read_registers(self.config.function, self.config.total_register, 2)
        raw = (hi << 16) | lo
        scale = self.config.total_scale if self.config.total_scale else 1.0
        return max(0.0, raw / scale)

    async def _read_register(self, function: int, address: int) -> int:
        return (await self._read_registers(function, address, 1))[0]

    async def _read_registers(self, function: int, address: int, count: int) -> tuple[int, ...]:
        if function not in (3, 4):
            raise ValueError(f"Modbus-Funktion {function} wird fuer Flowmeter nicht unterstuetzt")
        pdu = bytes([function]) + struct.pack(">HH", address, count)
        response = await self._request(pdu)
        if response[0] & 0x80:
            raise RuntimeError(f"Modbus Exception {response[1]}")
        expected_bytes = count * 2
        if response[1] != expected_bytes:
            raise RuntimeError(f"Ungueltige Modbus-Antwortlaenge: {response[1]}")
        return struct.unpack(">" + "H" * count, response[2 : 2 + expected_bytes])

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


class WatermeterHttpClient:
    def __init__(self, config: WatermeterHttpConfig) -> None:
        self.config = config

    async def read_snapshot(self) -> WatermeterHttpSnapshot:
        return await asyncio.to_thread(self._read_snapshot_sync)

    def _read_snapshot_sync(self) -> WatermeterHttpSnapshot:
        with urlopen(self.config.url, timeout=self.config.timeout_s) as response:  # noqa: S310
            payload = response.read().decode("utf-8", errors="replace")
        return parse_watermeter_http_payload(
            payload,
            self.config.number_name,
            self.config.total_scale_l_per_unit,
        )


def parse_watermeter_http_payload(
    payload: str,
    number_name: str = "zaehlerstand",
    total_scale_l_per_unit: float = 1000.0,
) -> WatermeterHttpSnapshot:
    """Parst AI-on-the-edge /value Ausgabe und gibt den absoluten Zaehlerstand in Litern zurueck."""
    expected = number_name.strip()
    for line in payload.splitlines():
        parts = [part.strip() for part in line.replace(";", "\t").split("\t") if part.strip()]
        if len(parts) < 2 or parts[0] != expected:
            continue
        raw = parts[1]
        value = float(raw.replace(",", "."))
        return WatermeterHttpSnapshot(
            total_l=max(0.0, value * total_scale_l_per_unit),
            value=value,
            raw=raw,
        )
    raise ValueError(f"Wasserzaehler {expected!r} nicht in AI-on-the-edge Antwort gefunden")


def _setting(settings: dict[str, Any], path: str, default: Any) -> Any:
    node: Any = settings
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
