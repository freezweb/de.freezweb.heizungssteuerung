"""Pool-Nachspeisung und Flockungsmittel-Dosierung."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .state import StateStore


@dataclass(frozen=True)
class PoolProdinoConfig:
    enabled: bool = False
    protocol: str = "modbus_tcp"
    host: str = "10.1.1.146"
    port: int = 502
    unit_id: int = 1
    timeout_s: float = 0.5
    poll_interval_s: float = 1.0
    topic_base: str = "heizung/prodino_pool"
    input_index: int = 1
    float_empty_high: bool = True
    valve_component: str = "pool_nachfuellventil"
    pump_component: str = "pool_flockung_pumpe"
    float_component: str = "pool_schwimmer_zu_leer"
    state_persist_path: str = "state/pool_nachspeisung.json"
    health_timeout_s: float = 90.0

    @classmethod
    def from_settings(cls, settings: dict[str, Any], mqtt_base: str = "heizung") -> "PoolProdinoConfig":
        raw = settings.get("pool_prodino", {})
        if not isinstance(raw, dict):
            raw = {}
        return cls(
            enabled=bool(raw.get("enabled", False)),
            protocol=str(raw.get("protocol", "modbus_tcp")).lower(),
            host=str(raw.get("host", "10.1.1.146")),
            port=int(raw.get("port", 502)),
            unit_id=int(raw.get("unit_id", 1)),
            timeout_s=max(0.1, float(raw.get("timeout_s", 0.5))),
            poll_interval_s=max(0.2, float(raw.get("poll_interval_s", 1.0))),
            topic_base=str(raw.get("topic_base", f"{mqtt_base.strip('/')}/prodino_pool")).strip("/"),
            input_index=max(1, int(raw.get("input_index", 1))),
            float_empty_high=bool(raw.get("float_empty_high", True)),
            valve_component=str(raw.get("valve_component", "pool_nachfuellventil")),
            pump_component=str(raw.get("pump_component", "pool_flockung_pumpe")),
            float_component=str(raw.get("float_component", raw.get("legacy_float_component", "pool_schwimmer_zu_leer"))),
            state_persist_path=str(raw.get("state_persist_path", "state/pool_nachspeisung.json")),
            health_timeout_s=max(1.0, float(raw.get("health_timeout_s", 90.0))),
        )


@dataclass
class PoolRuntimeState:
    pending_since_ts: float | None = None
    filling_since_ts: float | None = None
    fill_start_meter_l: float | None = None
    dosing_until_ts: float | None = None
    last_fill_attempt_day: str = ""
    last_daily_dose_day: str = ""
    last_fill_liters: float = 0.0
    last_fill_seconds: float = 0.0
    last_dose_ts: float | None = None
    last_dose_ml: float = 0.0
    last_dose_seconds: float = 0.0
    last_dose_reason: str = ""

    @classmethod
    def from_store(cls, store: StateStore | None) -> "PoolRuntimeState":
        if store is None:
            return cls()
        raw = store.load()
        if not isinstance(raw, dict):
            return cls()
        return cls(
            pending_since_ts=_optional_float(raw.get("pending_since_ts")),
            filling_since_ts=_optional_float(raw.get("filling_since_ts")),
            fill_start_meter_l=_optional_float(raw.get("fill_start_meter_l")),
            dosing_until_ts=_optional_float(raw.get("dosing_until_ts")),
            last_fill_attempt_day=str(raw.get("last_fill_attempt_day", "")),
            last_daily_dose_day=str(raw.get("last_daily_dose_day", "")),
            last_fill_liters=float(raw.get("last_fill_liters", 0.0) or 0.0),
            last_fill_seconds=float(raw.get("last_fill_seconds", 0.0) or 0.0),
            last_dose_ts=_optional_float(raw.get("last_dose_ts")),
            last_dose_ml=float(raw.get("last_dose_ml", 0.0) or 0.0),
            last_dose_seconds=float(raw.get("last_dose_seconds", 0.0) or 0.0),
            last_dose_reason=str(raw.get("last_dose_reason", "")),
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            "pending_since_ts": self.pending_since_ts,
            "filling_since_ts": self.filling_since_ts,
            "fill_start_meter_l": self.fill_start_meter_l,
            "dosing_until_ts": self.dosing_until_ts,
            "last_fill_attempt_day": self.last_fill_attempt_day,
            "last_daily_dose_day": self.last_daily_dose_day,
            "last_fill_liters": round(self.last_fill_liters, 2),
            "last_fill_seconds": round(self.last_fill_seconds, 1),
            "last_dose_ts": self.last_dose_ts,
            "last_dose_ml": round(self.last_dose_ml, 2),
            "last_dose_seconds": round(self.last_dose_seconds, 1),
            "last_dose_reason": self.last_dose_reason,
        }


@dataclass(frozen=True)
class PoolControlState:
    enabled: bool
    float_empty: bool | None
    float_full: bool | None
    valve_open: bool
    dosing_pump_on: bool
    pending: bool
    filling: bool
    reason: str
    fill_elapsed_s: float
    dosing_remaining_s: float
    last_fill_liters: float
    last_dose_ts: float | None
    last_dose_ml: float
    last_dose_seconds: float
    last_dose_reason: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "float_empty": self.float_empty,
            "float_full": self.float_full,
            "valve_open": self.valve_open,
            "dosing_pump_on": self.dosing_pump_on,
            "pending": self.pending,
            "filling": self.filling,
            "reason": self.reason,
            "fill_elapsed_s": round(self.fill_elapsed_s, 1),
            "dosing_remaining_s": round(self.dosing_remaining_s, 1),
            "last_fill_liters": round(self.last_fill_liters, 2),
            "last_dose_ts": self.last_dose_ts,
            "last_dose_ml": round(self.last_dose_ml, 2),
            "last_dose_seconds": round(self.last_dose_seconds, 1),
            "last_dose_reason": self.last_dose_reason,
        }


class PoolController:
    def __init__(self, config: PoolProdinoConfig, store: StateStore | None = None) -> None:
        self.config = config
        self.store = store
        self.runtime = PoolRuntimeState.from_store(store)
        self.state = PoolControlState(False, None, None, False, False, False, False, "init", 0.0, 0.0, 0.0, None, 0.0, 0.0, "")

    def compute(
        self,
        *,
        now_ts: float,
        float_empty: bool | None,
        test_mode: bool,
        fill_delay_s: float,
        start_hour: int,
        max_fill_s: float,
        daily_dose_ml: float,
        daily_dose_hour: int,
        fresh_ml_per_l: float,
        pump_ml_min: float,
        water_meter_total_l: float | None = None,
    ) -> PoolControlState:
        if not self.config.enabled:
            self._reset_fill()
            self.state = self._state(False, float_empty, False, "deaktiviert", now_ts)
            self._save()
            return self.state

        now_dt = datetime.fromtimestamp(now_ts)
        today = now_dt.date().isoformat()
        fill_delay_s = max(0.0, float(fill_delay_s))
        max_fill_s = max(1.0, float(max_fill_s))
        pump_ml_min = max(0.1, float(pump_ml_min))

        reason = "bereit"
        valve_open = False
        if float_empty is None:
            reason = "schwimmer_unbekannt"
            self._reset_fill()
        elif not float_empty:
            reason = "pool_voll"
            self._finish_fill(now_ts, fresh_ml_per_l, pump_ml_min, water_meter_total_l)
        else:
            allowed = bool(test_mode) or (now_dt.hour == max(0, min(23, int(start_hour))))
            already_tried_today = (not test_mode) and self.runtime.last_fill_attempt_day == today
            if not allowed:
                reason = "wartet_bis_startzeit"
                self.runtime.pending_since_ts = None
            elif already_tried_today and self.runtime.filling_since_ts is None:
                reason = "heute_bereits_versucht"
                self.runtime.pending_since_ts = None
            else:
                if self.runtime.pending_since_ts is None:
                    self.runtime.pending_since_ts = now_ts
                    self.runtime.last_fill_attempt_day = today
                elapsed_pending = now_ts - self.runtime.pending_since_ts
                if elapsed_pending >= fill_delay_s:
                    if self.runtime.filling_since_ts is None:
                        self.runtime.filling_since_ts = now_ts
                        self.runtime.fill_start_meter_l = _optional_float(water_meter_total_l)
                    fill_elapsed_s = now_ts - self.runtime.filling_since_ts
                    if fill_elapsed_s <= max_fill_s:
                        valve_open = True
                        reason = "fuellt"
                    else:
                        reason = "max_fuellzeit_erreicht"
                        self._finish_fill(now_ts, fresh_ml_per_l, pump_ml_min, water_meter_total_l)
                else:
                    reason = "verzoegerung"

        self._schedule_daily_dose(today, now_dt.hour, daily_dose_hour, daily_dose_ml, pump_ml_min, now_ts)
        dosing_on = bool(self.runtime.dosing_until_ts is not None and now_ts < self.runtime.dosing_until_ts)
        if self.runtime.dosing_until_ts is not None and now_ts >= self.runtime.dosing_until_ts:
            self.runtime.dosing_until_ts = None
            dosing_on = False

        self.state = self._state(True, float_empty, valve_open, reason, now_ts, dosing_on)
        self._save()
        return self.state

    def _finish_fill(
        self,
        now_ts: float,
        fresh_ml_per_l: float,
        pump_ml_min: float,
        water_meter_total_l: float | None = None,
    ) -> None:
        if self.runtime.filling_since_ts is not None:
            duration_s = max(0.0, now_ts - self.runtime.filling_since_ts)
            meter_total_l = _optional_float(water_meter_total_l)
            if (
                meter_total_l is not None
                and self.runtime.fill_start_meter_l is not None
                and meter_total_l >= self.runtime.fill_start_meter_l
            ):
                liters = meter_total_l - self.runtime.fill_start_meter_l
            else:
                liters = 0.0
            self.runtime.last_fill_seconds = duration_s
            self.runtime.last_fill_liters = liters
            dose_ml = liters * max(0.0, fresh_ml_per_l)
            self._add_dose_seconds(
                dose_ml / max(0.1, pump_ml_min) * 60.0,
                now_ts,
                dose_ml=dose_ml,
                reason="frischwasser",
            )
        self._reset_fill()

    def _reset_fill(self) -> None:
        self.runtime.pending_since_ts = None
        self.runtime.filling_since_ts = None
        self.runtime.fill_start_meter_l = None

    def _schedule_daily_dose(
        self,
        today: str,
        current_hour: int,
        dose_hour: int,
        dose_ml: float,
        pump_ml_min: float,
        now_ts: float,
    ) -> None:
        if dose_ml <= 0 or current_hour != max(0, min(23, int(dose_hour))):
            return
        if self.runtime.last_daily_dose_day == today:
            return
        self.runtime.last_daily_dose_day = today
        self._add_dose_seconds(
            float(dose_ml) / max(0.1, float(pump_ml_min)) * 60.0,
            now_ts,
            dose_ml=float(dose_ml),
            reason="tagesdosis",
        )

    def _add_dose_seconds(self, seconds: float, now_ts: float, *, dose_ml: float, reason: str) -> None:
        if seconds <= 0:
            return
        base = max(now_ts, self.runtime.dosing_until_ts or now_ts)
        self.runtime.dosing_until_ts = base + seconds
        self.runtime.last_dose_ts = now_ts
        self.runtime.last_dose_ml = max(0.0, float(dose_ml))
        self.runtime.last_dose_seconds = seconds
        self.runtime.last_dose_reason = reason

    def _state(
        self,
        enabled: bool,
        float_empty: bool | None,
        valve_open: bool,
        reason: str,
        now_ts: float,
        dosing_on: bool | None = None,
    ) -> PoolControlState:
        fill_elapsed_s = 0.0
        if self.runtime.filling_since_ts is not None:
            fill_elapsed_s = max(0.0, now_ts - self.runtime.filling_since_ts)
        dosing_remaining_s = 0.0
        if self.runtime.dosing_until_ts is not None:
            dosing_remaining_s = max(0.0, self.runtime.dosing_until_ts - now_ts)
        float_full = None if float_empty is None else not float_empty
        return PoolControlState(
            enabled=enabled,
            float_empty=float_empty,
            float_full=float_full,
            valve_open=valve_open,
            dosing_pump_on=bool(dosing_on) if dosing_on is not None else dosing_remaining_s > 0,
            pending=self.runtime.pending_since_ts is not None and self.runtime.filling_since_ts is None,
            filling=self.runtime.filling_since_ts is not None and valve_open,
            reason=reason,
            fill_elapsed_s=fill_elapsed_s,
            dosing_remaining_s=dosing_remaining_s,
            last_fill_liters=self.runtime.last_fill_liters,
            last_dose_ts=self.runtime.last_dose_ts,
            last_dose_ml=self.runtime.last_dose_ml,
            last_dose_seconds=self.runtime.last_dose_seconds,
            last_dose_reason=self.runtime.last_dose_reason,
        )

    def _save(self) -> None:
        if self.store is not None:
            self.store.save(self.runtime.as_payload())


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
