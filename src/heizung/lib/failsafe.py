"""Failsafe-Entscheidung und witterungsgefuehrte Heizkurve."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HeatingCurve:
    points: tuple[tuple[float, float], ...]
    vl_min: float
    vl_max: float

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "HeatingCurve":
        raw_curve = settings.get("heizkurve", {})
        raw_points = raw_curve.get("stuetzpunkte", [])
        points = tuple(
            sorted((float(point["aussen"]), float(point["vl"])) for point in raw_points)
        )
        if len(points) < 2:
            raise ValueError("Heizkurve braucht mindestens zwei Stuetzpunkte")
        return cls(
            points=points,
            vl_min=float(raw_curve.get("vl_min", 20)),
            vl_max=float(raw_curve.get("vl_max", 60)),
        )

    def target_flow(self, outside_temp_c: float) -> float:
        first_x, first_y = self.points[0]
        last_x, last_y = self.points[-1]
        if outside_temp_c <= first_x:
            return self._clamp(first_y)
        if outside_temp_c >= last_x:
            return self._clamp(last_y)

        for (left_x, left_y), (right_x, right_y) in zip(self.points, self.points[1:], strict=False):
            if left_x <= outside_temp_c <= right_x:
                factor = (outside_temp_c - left_x) / (right_x - left_x)
                return self._clamp(left_y + factor * (right_y - left_y))

        return self._clamp(last_y)

    def _clamp(self, value: float) -> float:
        return max(self.vl_min, min(self.vl_max, value))


@dataclass(frozen=True)
class FailsafeState:
    active: bool
    reasons: tuple[str, ...]
    vl_soll: float | None


class FailsafeMonitor:
    def __init__(
        self,
        heating_curve: HeatingCurve,
        mqtt_timeout_s: float,
        ha_heartbeat_timeout_s: float,
        fallback_vl_without_outside_sensor: float,
        require_mqtt_activity: bool = True,
        require_ha_heartbeat: bool = True,
        require_outside_sensor: bool = True,
    ) -> None:
        self.heating_curve = heating_curve
        self.mqtt_timeout_s = mqtt_timeout_s
        self.ha_heartbeat_timeout_s = ha_heartbeat_timeout_s
        self.fallback_vl_without_outside_sensor = fallback_vl_without_outside_sensor
        self.require_mqtt_activity = require_mqtt_activity
        self.require_ha_heartbeat = require_ha_heartbeat
        self.require_outside_sensor = require_outside_sensor
        self.force = False

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "FailsafeMonitor":
        raw = settings.get("failsafe", {})
        return cls(
            heating_curve=HeatingCurve.from_settings(settings),
            mqtt_timeout_s=float(raw.get("mqtt_timeout_s", 60)),
            ha_heartbeat_timeout_s=float(raw.get("ha_heartbeat_timeout_s", 300)),
            fallback_vl_without_outside_sensor=float(raw.get("fallback_vl_ohne_aussenfuehler", 50)),
            require_mqtt_activity=bool(raw.get("mqtt_activity_required", True)),
            require_ha_heartbeat=bool(raw.get("ha_heartbeat_required", True)),
            require_outside_sensor=bool(raw.get("outside_sensor_required", True)),
        )

    def evaluate(
        self,
        *,
        now_ts: float,
        mqtt_connected: bool,
        last_mqtt_seen_ts: float | None,
        last_ha_heartbeat_ts: float | None,
        outside_temp_c: float | None,
    ) -> FailsafeState:
        reasons: list[str] = []

        if self.force:
            reasons.append("force")
        if not mqtt_connected:
            reasons.append("mqtt_disconnected")
        elif self.require_mqtt_activity and (
            last_mqtt_seen_ts is None or now_ts - last_mqtt_seen_ts > self.mqtt_timeout_s
        ):
            reasons.append("mqtt_timeout")

        if self.require_ha_heartbeat:
            if last_ha_heartbeat_ts is None:
                reasons.append("ha_heartbeat_missing")
            elif now_ts - last_ha_heartbeat_ts > self.ha_heartbeat_timeout_s:
                reasons.append("ha_heartbeat_timeout")

        outside_valid = outside_temp_c is not None and -40.0 <= outside_temp_c <= 80.0
        if not outside_valid:
            if self.require_outside_sensor:
                reasons.append("outside_sensor_loss")
            vl_soll = self.fallback_vl_without_outside_sensor
        else:
            vl_soll = self.heating_curve.target_flow(outside_temp_c)

        return FailsafeState(active=bool(reasons), reasons=tuple(reasons), vl_soll=vl_soll)
