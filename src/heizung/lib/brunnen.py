"""Konstantdruckregelung fuer die Brunnenpumpe am FU."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import AppConfig
from .iohw import HardwareSnapshot
from .regler import ReglerParameter


@dataclass(frozen=True)
class BrunnenPressureState:
    active: bool
    pressure_bar: float | None
    speed_pct: float
    min_bar: float
    max_bar: float
    setpoint_bar: float
    reason: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "pressure_bar": self.pressure_bar,
            "speed_pct": self.speed_pct,
            "min_bar": self.min_bar,
            "max_bar": self.max_bar,
            "setpoint_bar": self.setpoint_bar,
            "reason": self.reason,
        }


def compute_brunnen_pressure(
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
    regler: ReglerParameter,
    previous_active: bool,
    previous_speed_pct: float,
    cycle_s: float = 1.0,
) -> BrunnenPressureState:
    """Regelt den FU-Sollwert auf Konstantdruck mit Ein-/Ausschalt-Hysterese."""
    pressure = _pressure_by_component(app_config, snapshot, "brunnen_druck")
    min_bar = float(regler.brunnen_min_druck_bar)
    max_bar = float(regler.brunnen_max_druck_bar)
    setpoint_bar = float(regler.brunnen_regeldruck_bar)

    if max_bar <= min_bar:
        max_bar = min_bar + 0.2
    setpoint_bar = max(min_bar, min(max_bar, setpoint_bar))

    min_valid = float(app_config.setting("brunnen.druck_sensor_min_bar", -0.2))
    max_valid = float(app_config.setting("brunnen.druck_sensor_max_bar", 10.5))
    if pressure is None or pressure < min_valid or pressure > max_valid:
        return BrunnenPressureState(False, pressure, 0.0, min_bar, max_bar, setpoint_bar, "sensor_unplausibel")

    if previous_active:
        if pressure >= max_bar:
            return BrunnenPressureState(False, pressure, 0.0, min_bar, max_bar, setpoint_bar, "maxdruck_erreicht")
        active = True
        reason = "regelt"
    else:
        active = pressure <= min_bar
        reason = "minderdruck_start" if active else "bereit"

    if not active:
        return BrunnenPressureState(False, pressure, 0.0, min_bar, max_bar, setpoint_bar, reason)

    min_speed = float(app_config.setting("brunnen.fu_min_pct", 20.0))
    max_speed = float(app_config.setting("brunnen.fu_max_pct", 100.0))
    start_speed = float(app_config.setting("brunnen.fu_start_pct", 45.0))
    kp = float(app_config.setting("brunnen.kp_pct_pro_bar", 18.0))
    ramp_up_pct_s = float(app_config.setting("brunnen.fu_ramp_up_pct_s", 35.0))
    ramp_down_pct_s = float(app_config.setting("brunnen.fu_ramp_down_pct_s", 60.0))

    base_speed = previous_speed_pct if previous_active and previous_speed_pct > 0 else start_speed
    target_speed = base_speed + (setpoint_bar - pressure) * kp
    target_speed = max(min_speed, min(max_speed, target_speed))
    ramp_base = previous_speed_pct if previous_active else 0.0
    next_speed = _ramp_limited(
        ramp_base,
        target_speed,
        up_step=max(0.0, ramp_up_pct_s) * max(0.0, cycle_s),
        down_step=max(0.0, ramp_down_pct_s) * max(0.0, cycle_s),
    )

    return BrunnenPressureState(True, pressure, next_speed, min_bar, max_bar, setpoint_bar, reason)


def _pressure_by_component(app_config: AppConfig, snapshot: HardwareSnapshot, component: str) -> float | None:
    for channel_id, channel in app_config.io_map.ai.items():
        if channel.komponente != component:
            continue
        value = snapshot.ai.get(channel_id)
        if value is None:
            return None
        return _scale_pressure(app_config, value)
    return None


def _scale_pressure(app_config: AppConfig, raw_value: float) -> float | None:
    """Skaliert den 4-20-mA-Drucksensor auf bar.

    Fuer Tests/Simulation und bereits skalierte IO-Backends wird ein Wert im
    plausiblen Druckbereich direkt als bar behandelt.
    """
    sensor_max_bar = float(app_config.setting("brunnen.druck_sensor_bereich_bar", 10.0))
    raw = float(raw_value)
    signal = str(app_config.setting("brunnen.druck_sensor_signal", "4-20ma")).strip().lower()
    if signal in {"bar", "scaled_bar", "0-10bar"} and 0.0 <= raw <= sensor_max_bar:
        return raw

    min_ma = float(app_config.setting("brunnen.druck_sensor_min_ma", 4.0))
    max_ma = float(app_config.setting("brunnen.druck_sensor_max_ma", 20.0))
    if min_ma <= raw <= max_ma:
        return max(0.0, min(sensor_max_bar, (raw - min_ma) / (max_ma - min_ma) * sensor_max_bar))

    # RevPi-AIO kann je nach PiCtory-Skalierung Mikroampere oder 0.001 mA liefern.
    raw_ma = raw / 1000.0
    if min_ma <= raw_ma <= max_ma:
        return max(0.0, min(sensor_max_bar, (raw_ma - min_ma) / (max_ma - min_ma) * sensor_max_bar))

    return None


def _ramp_limited(current: float, target: float, *, up_step: float, down_step: float) -> float:
    if target > current:
        return min(target, current + up_step)
    if target < current:
        return max(target, current - down_step)
    return target
