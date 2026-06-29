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

    async def set_cpu_leds(self, colors: dict[str, str]) -> None:
        return None

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
        self.cpu_leds: dict[str, str] = {}

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

    async def set_cpu_leds(self, colors: dict[str, str]) -> None:
        self.cpu_leds.update({name.upper(): _normalize_led_color(color) for name, color in colors.items()})


class RevPiIO(BaseIO):
    def __init__(self, io_map: IoMap) -> None:
        super().__init__(io_map)
        try:
            import revpimodio2
        except ImportError as exc:  # pragma: no cover - nur auf Nicht-RevPi relevant
            raise RuntimeError("revpimodio2 ist nicht installiert") from exc

        try:
            self._revpi = revpimodio2.RevPiModIO(autorefresh=False)
        except Exception as exc:  # pragma: no cover - abhaengig von PiCtory/Hardwarezustand
            raise RuntimeError("RevPi-I/O konnte nicht initialisiert werden") from exc
        self._missing_ios: set[str] = set()
        self._cpu_led_colors: dict[str, str] = {}

    async def read_all(self) -> HardwareSnapshot:
        self._revpi.readprocimg()
        di = {
            channel_id: bool(io.value)
            for channel_id, channel in self.io_map.di.items()
            if (io := self._try_get_io(channel)) is not None
        }
        ai = {
            channel_id: _raw_ai_value(io.value, channel)
            for channel_id, channel in self.io_map.ai.items()
            if (io := self._try_get_io(channel)) is not None
        }
        rtd = {
            channel_id: _raw_temp_value(io.value)
            for channel_id, channel in self.io_map.rtd.items()
            if (io := self._try_get_io(channel)) is not None
        }
        do = {
            channel_id: _read_do_value(io.value, channel)
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
            if _is_grouped_dio(channel):
                current = int(getattr(io, "value", 0) or 0)
                bit = _channel_bit_index(channel)
                if bit is not None:
                    if value:
                        current |= 1 << bit
                    else:
                        current &= ~(1 << bit)
                    io.value = current
                else:
                    io.value = bool(value)
            else:
                io.value = bool(value)
            self._revpi.writeprocimg()

    async def write_ao(self, channel: ChannelConfig, value: float) -> None:
        io = self._try_get_io(channel)
        if io is not None:
            io.value = int(round(_raw_ao_output_value(channel, float(value))))
            self._revpi.writeprocimg()

    async def set_cpu_leds(self, colors: dict[str, str]) -> None:
        core = getattr(self._revpi, "core", None)
        if core is None:
            return
        changed = False
        cached_colors = getattr(self, "_cpu_led_colors", {})
        self._cpu_led_colors = cached_colors
        for name, color in colors.items():
            led_name = name.upper()
            normalized_color = _normalize_led_color(color)
            if cached_colors.get(led_name) == normalized_color:
                continue
            if not led_name.startswith("A"):
                continue
            try:
                setattr(core, led_name, _LED_COLORS[normalized_color])
                cached_colors[led_name] = normalized_color
                changed = True
            except (AttributeError, ValueError, KeyError) as exc:
                log.debug("CPU-LED %s konnte nicht gesetzt werden: %s", led_name, exc)
        if changed:
            self._revpi.writeprocimg()

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
    if value <= 0:
        return 0.0
    if channel.bereich is None:
        return value
    low, high = channel.bereich
    return max(low, min(high, value))


def _raw_ao_output_value(channel: ChannelConfig, value: float) -> float:
    logical = _clamp_ao(channel, value)
    if not channel.pictory_name.startswith("OutputValue_"):
        return logical

    percent = _ao_logical_percent(channel, logical)
    signal = str(channel.signal or "0-10v").strip().lower()
    if "4-20" in signal and "ma" in signal:
        return 4000.0 + percent * 16000.0
    if "0-20" in signal and "ma" in signal:
        return percent * 20000.0
    return percent * 10000.0


def _ao_logical_percent(channel: ChannelConfig, value: float) -> float:
    if channel.bereich is not None:
        low, high = channel.bereich
        if high > low:
            return max(0.0, min(1.0, (value - low) / (high - low)))
    if str(channel.einheit or "").strip() == "%":
        return max(0.0, min(1.0, value / 100.0))
    return max(0.0, min(1.0, value / 10000.0))


def _raw_temp_value(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    # RevPi-AIO liefert PT100/1000 typischerweise in 1/10 Grad.
    if abs(value) > 200:
        value = value / 10
    if abs(value) >= 800:
        return None
    return value


def _raw_ai_value(raw: Any, channel: ChannelConfig) -> float | None:
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if _is_current_input(channel):
        return _raw_current_input_ma(value, channel)
    if _is_voltage_input(channel):
        return value / 1000.0
    # AI-Kanaele mit physikalischer Nicht-Temperatur-Skalierung werden im
    # jeweiligen Regler passend skaliert.
    if channel.einheit and channel.einheit.lower() not in {"c", "grad c", "°c"}:
        return value
    return _raw_temp_value(value)


def _is_current_input(channel: ChannelConfig) -> bool:
    text = f"{channel.sensor or ''} {channel.einheit or ''}".lower()
    return "ma" in text or "4-20" in text or "0-20" in text or "0-24" in text


def _raw_current_input_ma(value: float, channel: ChannelConfig) -> float:
    # RevPi AIO current inputs can appear either as microamps (4000..20000)
    # or, if PiCtory is intentionally left in voltage mode, as millivolts
    # across the 250-ohm current shunt (about 1000..5000).
    if "shunt" in str(channel.signal or "").strip().lower():
        return value / 250.0
    return value / 1000.0


def _is_voltage_input(channel: ChannelConfig) -> bool:
    text = f"{channel.sensor or ''} {channel.einheit or ''}".lower()
    return "0-10v" in text or "0-5v" in text or "10v" in text or "5v" in text


def _read_do_value(raw: Any, channel: ChannelConfig) -> bool:
    if _is_grouped_dio(channel):
        bit = _channel_bit_index(channel)
        if bit is not None:
            try:
                return bool(int(raw) & (1 << bit))
            except (TypeError, ValueError):
                return False
    return bool(raw)


def _is_grouped_dio(channel: ChannelConfig) -> bool:
    return channel.pictory_name.startswith(("Input_", "Output_"))


def _channel_bit_index(channel: ChannelConfig) -> int | None:
    raw = channel.channel or channel.id
    for prefix in ("O_", "I_", "DO", "DI", "K-DO", "K-DI"):
        if str(raw).startswith(prefix):
            raw = str(raw)[len(prefix) :]
            break
    try:
        index = int(str(raw).split("_", 1)[0])
    except (TypeError, ValueError):
        return None
    return max(0, index - 1)


_LED_COLORS = {
    "off": 0,
    "green": 1,
    "red": 2,
    "yellow": 3,
    "blue": 4,
    "magenta": 6,
    "white": 7,
}


def _normalize_led_color(color: str) -> str:
    normalized = str(color).strip().lower()
    aliases = {
        "aus": "off",
        "gruen": "green",
        "grün": "green",
        "rot": "red",
        "gelb": "yellow",
        "blau": "blue",
        "violett": "magenta",
        "weiss": "white",
        "weiß": "white",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in _LED_COLORS:
        return "off"
    return normalized
