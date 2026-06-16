"""RevPi-I/O-Abstraktion mit Simulator fuer Entwicklung und Tests."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from .config import ChannelConfig, IoMap

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HardwareSnapshot:
    di: dict[str, bool] = field(default_factory=dict)
    ai: dict[str, float | None] = field(default_factory=dict)
    rtd: dict[str, float | None] = field(default_factory=dict)
    do: dict[str, bool] = field(default_factory=dict)
    ao: dict[str, float] = field(default_factory=dict)


class BaseIO:
    def __init__(self, io_map: IoMap) -> None:
        self.io_map = io_map

    async def read_all(self) -> HardwareSnapshot:
        raise NotImplementedError

    async def write_do(self, channel: ChannelConfig, value: bool) -> None:
        raise NotImplementedError

    async def write_ao(self, channel: ChannelConfig, value: float) -> None:
        raise NotImplementedError

    async def pulse(self, channel: ChannelConfig, duration_ms: int) -> None:
        await self.write_do(channel, True)
        await asyncio.sleep(duration_ms / 1000)
        await self.write_do(channel, False)

    async def close(self) -> None:
        return None


class SimulatedIO(BaseIO):
    def __init__(self, io_map: IoMap) -> None:
        super().__init__(io_map)
        self.di_values = {channel_id: False for channel_id in io_map.di}
        self.ai_values = {channel_id: None for channel_id in io_map.ai}
        self.rtd_values = {channel_id: None for channel_id in io_map.rtd}
        self.do_values = {channel_id: False for channel_id in io_map.do}
        self.ao_values = {channel_id: 0.0 for channel_id in io_map.ao}

    async def read_all(self) -> HardwareSnapshot:
        return HardwareSnapshot(
            di=dict(self.di_values),
            ai=dict(self.ai_values),
            rtd=dict(self.rtd_values),
            do=dict(self.do_values),
            ao=dict(self.ao_values),
        )

    async def write_do(self, channel: ChannelConfig, value: bool) -> None:
        self.do_values[channel.id] = bool(value)

    async def write_ao(self, channel: ChannelConfig, value: float) -> None:
        self.ao_values[channel.id] = _clamp_ao(channel, float(value))


class RevPiIO(BaseIO):
    def __init__(self, io_map: IoMap) -> None:
        super().__init__(io_map)
        try:
            import revpimodio2
        except ImportError as exc:  # pragma: no cover - nur auf Nicht-RevPi relevant
            raise RuntimeError("revpimodio2 ist nicht installiert") from exc

        try:
            self._revpi = revpimodio2.RevPiModIO(autorefresh=True)
        except Exception as exc:  # pragma: no cover - abhaengig von PiCtory/Hardwarezustand
            raise RuntimeError("RevPi-I/O konnte nicht initialisiert werden") from exc
        self._missing_ios: set[str] = set()

    async def read_all(self) -> HardwareSnapshot:
        di = {
            channel_id: bool(io.value)
            for channel_id, channel in self.io_map.di.items()
            if (io := self._try_get_io(channel)) is not None
        }
        ai = {
            channel_id: _raw_temp_value(io.value)
            for channel_id, channel in self.io_map.ai.items()
            if (io := self._try_get_io(channel)) is not None
        }
        rtd = {
            channel_id: _raw_temp_value(io.value)
            for channel_id, channel in self.io_map.rtd.items()
            if (io := self._try_get_io(channel)) is not None
        }
        do = {
            channel_id: bool(io.value)
            for channel_id, channel in self.io_map.do.items()
            if (io := self._try_get_io(channel)) is not None
        }
        ao = {
            channel_id: float(io.value)
            for channel_id, channel in self.io_map.ao.items()
            if (io := self._try_get_io(channel)) is not None
        }
        return HardwareSnapshot(di=di, ai=ai, rtd=rtd, do=do, ao=ao)

    async def write_do(self, channel: ChannelConfig, value: bool) -> None:
        io = self._try_get_io(channel)
        if io is not None:
            io.value = bool(value)

    async def write_ao(self, channel: ChannelConfig, value: float) -> None:
        io = self._try_get_io(channel)
        if io is not None:
            io.value = _clamp_ao(channel, float(value))

    async def close(self) -> None:
        self._revpi.exit()

    def _try_get_io(self, channel: ChannelConfig) -> Any | None:
        try:
            return self._revpi.io[channel.pictory_name]
        except (AttributeError, KeyError):
            key = f"{channel.id}->{channel.pictory_name}"
            if key not in self._missing_ios:
                self._missing_ios.add(key)
                log.warning("PiCtory-I/O nicht gefunden, Kanal wird uebersprungen: %s", key)
            return None


def create_io_backend(io_map: IoMap, backend: str = "auto") -> BaseIO:
    if backend == "sim":
        log.warning("Starte mit simuliertem I/O-Backend")
        return SimulatedIO(io_map)
    if backend == "revpi":
        return RevPiIO(io_map)
    try:
        return RevPiIO(io_map)
    except RuntimeError as exc:
        log.warning("RevPi-I/O nicht verfuegbar, nutze Simulator: %s", exc)
        return SimulatedIO(io_map)


def _clamp_ao(channel: ChannelConfig, value: float) -> float:
    if channel.bereich is None:
        return value
    low, high = channel.bereich
    return max(low, min(high, value))


def _raw_temp_value(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    # RevPi-AIO liefert PT100/1000 typischerweise in 1/10 Grad.
    if abs(value) > 200:
        return value / 10
    return value
