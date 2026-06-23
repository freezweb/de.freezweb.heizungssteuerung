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
    flow_l_min: float | None = None
    no_flow_s: float | None = None
    flow_shutdown_remaining_s: float | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "pressure_bar": self.pressure_bar,
            "speed_pct": self.speed_pct,
            "min_bar": self.min_bar,
            "max_bar": self.max_bar,
            "setpoint_bar": self.setpoint_bar,
            "reason": self.reason,
            "flow_l_min": self.flow_l_min,
            "no_flow_s": self.no_flow_s,
            "flow_shutdown_remaining_s": self.flow_shutdown_remaining_s,
        }


def compute_brunnen_pressure(
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
    regler: ReglerParameter,
    previous_active: bool,
    previous_speed_pct: float,
    cycle_s: float = 1.0,
    flow_l_min: float | None = None,
    no_flow_s: float | None = None,
) -> BrunnenPressureState:
    """Regelt den FU-Sollwert auf Konstantdruck mit Ein-/Ausschalt-Hysterese."""
    pressure = _pressure_by_component(app_config, snapshot, "brunnen_druck")
    min_bar = float(regler.brunnen_min_druck_bar)
    max_bar = float(regler.brunnen_max_druck_bar)
    setpoint_bar = float(regler.brunnen_regeldruck_bar)

    if max_bar <= min_bar:
        max_bar = min_bar + 0.2
    setpoint_bar = max(min_bar, min(max_bar, setpoint_bar))
    flow_remaining_s = _flow_shutdown_remaining(regler, flow_l_min, no_flow_s)

    min_valid = float(app_config.setting("brunnen.druck_sensor_min_bar", -0.2))
    max_valid = float(app_config.setting("brunnen.druck_sensor_max_bar", 10.5))
    if pressure is None or pressure < min_valid or pressure > max_valid:
        return BrunnenPressureState(
            False,
            pressure,
            0.0,
            min_bar,
            max_bar,
            setpoint_bar,
            "sensor_unplausibel",
            flow_l_min,
            no_flow_s,
            flow_remaining_s,
        )

    if previous_active:
        if (
            flow_l_min is not None
            and no_flow_s is not None
            and flow_l_min <= float(regler.brunnen_flow_min_l_min)
            and no_flow_s >= float(regler.brunnen_flow_timeout_s)
        ):
            return BrunnenPressureState(
                False,
                pressure,
                0.0,
                min_bar,
                max_bar,
                setpoint_bar,
                "kein_durchfluss_stop",
                flow_l_min,
                no_flow_s,
                flow_remaining_s,
            )
        if pressure >= max_bar:
            return BrunnenPressureState(
                False,
                pressure,
                0.0,
                min_bar,
                max_bar,
                setpoint_bar,
                "maxdruck_erreicht",
                flow_l_min,
                no_flow_s,
                flow_remaining_s,
            )
        active = True
        reason = "regelt"
    else:
        active = pressure <= min_bar
        reason = "minderdruck_start" if active else "bereit"

    if not active:
        return BrunnenPressureState(
            False, pressure, 0.0, min_bar, max_bar, setpoint_bar, reason, flow_l_min, no_flow_s, flow_remaining_s
        )

    min_speed = float(app_config.setting("brunnen.fu_min_pct", 0.0))
    max_speed = float(app_config.setting("brunnen.fu_max_pct", 100.0))
    start_speed = float(regler.brunnen_fu_start_pct)
    kp = float(regler.brunnen_kp_pct_pro_bar)
    ramp_up_pct_s = float(regler.brunnen_fu_ramp_up_pct_s)
    ramp_down_pct_s = float(regler.brunnen_fu_ramp_down_pct_s)

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

    return BrunnenPressureState(
        True, pressure, next_speed, min_bar, max_bar, setpoint_bar, reason, flow_l_min, no_flow_s, flow_remaining_s
    )


def _flow_shutdown_remaining(
    regler: ReglerParameter,
    flow_l_min: float | None,
    no_flow_s: float | None,
) -> float | None:
    if flow_l_min is None or no_flow_s is None:
        return None
    if flow_l_min > float(regler.brunnen_flow_min_l_min):
        return None
    return max(0.0, float(regler.brunnen_flow_timeout_s) - no_flow_s)


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
    min_ma_tolerated = max(0.0, min_ma - float(app_config.setting("brunnen.druck_sensor_min_ma_toleranz", 0.2)))
    if min_ma <= raw <= max_ma:
        return max(0.0, min(sensor_max_bar, (raw - min_ma) / (max_ma - min_ma) * sensor_max_bar))
    if min_ma_tolerated <= raw < min_ma:
        return 0.0

    # RevPi-AIO kann je nach PiCtory-Skalierung Mikroampere oder 0.001 mA liefern.
    raw_ma = raw / 1000.0
    if min_ma <= raw_ma <= max_ma:
        return max(0.0, min(sensor_max_bar, (raw_ma - min_ma) / (max_ma - min_ma) * sensor_max_bar))
    if min_ma_tolerated <= raw_ma < min_ma:
        return 0.0

    return None


def _ramp_limited(current: float, target: float, *, up_step: float, down_step: float) -> float:
    if target > current:
        return min(target, current + up_step)
    if target < current:
        return max(target, current - down_step)
    return target
