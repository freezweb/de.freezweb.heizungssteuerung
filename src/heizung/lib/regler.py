"""Persistente Reglerparameter, die live per MQTT/HA geaendert werden."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .state import StateStore


@dataclass
class ReglerParameter:
    store: StateStore | None = None
    mischer_reserve_k: float = 5.0
    wp_parallel_ab_aktive_kreise: int = 2
    brauchwasser_soll_c: float = 50.0
    brauchwasser_hysterese_k: float = 5.0
    brunnen_min_druck_bar: float = 2.2
    brunnen_max_druck_bar: float = 4.2
    brunnen_regeldruck_bar: float = 3.2
    brunnen_fu_start_pct: float = 35.0
    brunnen_fu_max_pct: float = 100.0
    brunnen_kp_pct_pro_bar: float = 35.0
    brunnen_fu_ramp_up_pct_s: float = 80.0
    brunnen_fu_ramp_down_pct_s: float = 160.0
    brunnen_flow_min_l_min: float = 0.2
    brunnen_flow_timeout_s: float = 120.0
    brunnen_flow_stop_tolerance_bar: float = 0.2

    @classmethod
    def from_settings(cls, settings: dict[str, Any], store: StateStore | None = None) -> "ReglerParameter":
        regler = cls(
            store=store,
            mischer_reserve_k=float(_setting(settings, "regelung.mischer_reserve_k", 5.0)),
            wp_parallel_ab_aktive_kreise=int(_setting(settings, "wp.parallel_ab_aktive_kreise", 2)),
            brauchwasser_soll_c=float(_setting(settings, "brauchwasser.soll_c", 50.0)),
            brauchwasser_hysterese_k=float(_setting(settings, "brauchwasser.hysterese_k", 5.0)),
            brunnen_min_druck_bar=float(_setting(settings, "brunnen.min_druck_bar", 2.2)),
            brunnen_max_druck_bar=float(_setting(settings, "brunnen.max_druck_bar", 4.2)),
            brunnen_regeldruck_bar=float(_setting(settings, "brunnen.regeldruck_bar", 3.2)),
            brunnen_fu_start_pct=float(_setting(settings, "brunnen.fu_start_pct", 35.0)),
            brunnen_fu_max_pct=float(_setting(settings, "brunnen.fu_max_pct", 100.0)),
            brunnen_kp_pct_pro_bar=float(_setting(settings, "brunnen.kp_pct_pro_bar", 35.0)),
            brunnen_fu_ramp_up_pct_s=float(_setting(settings, "brunnen.fu_ramp_up_pct_s", 80.0)),
            brunnen_fu_ramp_down_pct_s=float(_setting(settings, "brunnen.fu_ramp_down_pct_s", 160.0)),
            brunnen_flow_min_l_min=float(_setting(settings, "brunnen.flow_min_l_min", 0.2)),
            brunnen_flow_timeout_s=float(_setting(settings, "brunnen.flow_timeout_s", 120.0)),
            brunnen_flow_stop_tolerance_bar=float(_setting(settings, "brunnen.flow_stop_regeldruck_tolerance_bar", 0.2)),
        )
        if store is not None:
            regler._apply_saved(store.load())
        return regler

    def set(self, name: str, value: Any) -> bool:
        if name == "mischer_reserve_k":
            self.mischer_reserve_k = max(0.0, min(15.0, float(str(value).replace(",", "."))))
        elif name == "wp_parallel_ab_aktive_kreise":
            self.wp_parallel_ab_aktive_kreise = max(1, min(10, int(float(str(value).replace(",", ".")))))
        elif name == "brauchwasser_soll_c":
            self.brauchwasser_soll_c = max(30.0, min(70.0, float(str(value).replace(",", "."))))
        elif name == "brauchwasser_hysterese_k":
            self.brauchwasser_hysterese_k = max(1.0, min(20.0, float(str(value).replace(",", "."))))
        elif name == "brunnen_min_druck_bar":
            self.brunnen_min_druck_bar = max(0.0, min(9.5, float(str(value).replace(",", "."))))
            if self.brunnen_max_druck_bar <= self.brunnen_min_druck_bar:
                self.brunnen_max_druck_bar = min(10.0, self.brunnen_min_druck_bar + 0.2)
            self.brunnen_regeldruck_bar = max(
                self.brunnen_min_druck_bar,
                min(self.brunnen_max_druck_bar, self.brunnen_regeldruck_bar),
            )
        elif name == "brunnen_max_druck_bar":
            self.brunnen_max_druck_bar = max(0.2, min(10.0, float(str(value).replace(",", "."))))
            if self.brunnen_max_druck_bar <= self.brunnen_min_druck_bar:
                self.brunnen_min_druck_bar = max(0.0, self.brunnen_max_druck_bar - 0.2)
            self.brunnen_regeldruck_bar = max(
                self.brunnen_min_druck_bar,
                min(self.brunnen_max_druck_bar, self.brunnen_regeldruck_bar),
            )
        elif name == "brunnen_regeldruck_bar":
            value_float = float(str(value).replace(",", "."))
            self.brunnen_regeldruck_bar = max(self.brunnen_min_druck_bar, min(self.brunnen_max_druck_bar, value_float))
        elif name == "brunnen_fu_start_pct":
            self.brunnen_fu_start_pct = max(0.0, min(100.0, float(str(value).replace(",", "."))))
        elif name == "brunnen_fu_max_pct":
            self.brunnen_fu_max_pct = max(0.0, min(100.0, float(str(value).replace(",", "."))))
        elif name == "brunnen_kp_pct_pro_bar":
            self.brunnen_kp_pct_pro_bar = max(0.0, min(200.0, float(str(value).replace(",", "."))))
        elif name == "brunnen_fu_ramp_up_pct_s":
            self.brunnen_fu_ramp_up_pct_s = max(1.0, min(500.0, float(str(value).replace(",", "."))))
        elif name == "brunnen_fu_ramp_down_pct_s":
            self.brunnen_fu_ramp_down_pct_s = max(1.0, min(1000.0, float(str(value).replace(",", "."))))
        elif name == "brunnen_flow_min_l_min":
            self.brunnen_flow_min_l_min = max(0.0, min(20.0, float(str(value).replace(",", "."))))
        elif name == "brunnen_flow_timeout_s":
            self.brunnen_flow_timeout_s = max(10.0, min(1800.0, float(str(value).replace(",", "."))))
        elif name == "brunnen_flow_stop_tolerance_bar":
            self.brunnen_flow_stop_tolerance_bar = max(0.0, min(2.0, float(str(value).replace(",", "."))))
        else:
            return False
        self.save()
        return True

    def as_settings(self, base: dict[str, Any]) -> dict[str, Any]:
        settings = deepcopy(base)
        settings.setdefault("regelung", {})["mischer_reserve_k"] = self.mischer_reserve_k
        settings.setdefault("wp", {})["parallel_ab_aktive_kreise"] = self.wp_parallel_ab_aktive_kreise
        settings.setdefault("brauchwasser", {})["soll_c"] = self.brauchwasser_soll_c
        settings.setdefault("brauchwasser", {})["hysterese_k"] = self.brauchwasser_hysterese_k
        settings.setdefault("brunnen", {})["min_druck_bar"] = self.brunnen_min_druck_bar
        settings.setdefault("brunnen", {})["max_druck_bar"] = self.brunnen_max_druck_bar
        settings.setdefault("brunnen", {})["regeldruck_bar"] = self.brunnen_regeldruck_bar
        settings.setdefault("brunnen", {})["fu_start_pct"] = self.brunnen_fu_start_pct
        settings.setdefault("brunnen", {})["fu_max_pct"] = self.brunnen_fu_max_pct
        settings.setdefault("brunnen", {})["kp_pct_pro_bar"] = self.brunnen_kp_pct_pro_bar
        settings.setdefault("brunnen", {})["fu_ramp_up_pct_s"] = self.brunnen_fu_ramp_up_pct_s
        settings.setdefault("brunnen", {})["fu_ramp_down_pct_s"] = self.brunnen_fu_ramp_down_pct_s
        settings.setdefault("brunnen", {})["flow_min_l_min"] = self.brunnen_flow_min_l_min
        settings.setdefault("brunnen", {})["flow_timeout_s"] = self.brunnen_flow_timeout_s
        settings.setdefault("brunnen", {})[
            "flow_stop_regeldruck_tolerance_bar"
        ] = self.brunnen_flow_stop_tolerance_bar
        return settings

    def snapshot(self) -> dict[str, float | int]:
        return {
            "mischer_reserve_k": self.mischer_reserve_k,
            "wp_parallel_ab_aktive_kreise": self.wp_parallel_ab_aktive_kreise,
            "brauchwasser_soll_c": self.brauchwasser_soll_c,
            "brauchwasser_hysterese_k": self.brauchwasser_hysterese_k,
            "brunnen_min_druck_bar": self.brunnen_min_druck_bar,
            "brunnen_max_druck_bar": self.brunnen_max_druck_bar,
            "brunnen_regeldruck_bar": self.brunnen_regeldruck_bar,
            "brunnen_fu_start_pct": self.brunnen_fu_start_pct,
            "brunnen_fu_max_pct": self.brunnen_fu_max_pct,
            "brunnen_kp_pct_pro_bar": self.brunnen_kp_pct_pro_bar,
            "brunnen_fu_ramp_up_pct_s": self.brunnen_fu_ramp_up_pct_s,
            "brunnen_fu_ramp_down_pct_s": self.brunnen_fu_ramp_down_pct_s,
            "brunnen_flow_min_l_min": self.brunnen_flow_min_l_min,
            "brunnen_flow_timeout_s": self.brunnen_flow_timeout_s,
            "brunnen_flow_stop_tolerance_bar": self.brunnen_flow_stop_tolerance_bar,
        }

    def save(self) -> None:
        if self.store is not None:
            self.store.save(self.snapshot())

    def _apply_saved(self, raw: dict[str, Any]) -> None:
        if not isinstance(raw, dict):
            return
        for name, value in raw.items():
            try:
                if name == "mischer_reserve_k":
                    self.mischer_reserve_k = max(0.0, min(15.0, float(str(value).replace(",", "."))))
                elif name == "wp_parallel_ab_aktive_kreise":
                    self.wp_parallel_ab_aktive_kreise = max(1, min(10, int(float(str(value).replace(",", ".")))))
                elif name == "brauchwasser_soll_c":
                    self.brauchwasser_soll_c = max(30.0, min(70.0, float(str(value).replace(",", "."))))
                elif name == "brauchwasser_hysterese_k":
                    self.brauchwasser_hysterese_k = max(1.0, min(20.0, float(str(value).replace(",", "."))))
                elif name == "brunnen_min_druck_bar":
                    self.set(name, value)
                elif name == "brunnen_max_druck_bar":
                    self.set(name, value)
                elif name == "brunnen_regeldruck_bar":
                    self.set(name, value)
                elif name in {
                    "brunnen_fu_start_pct",
                    "brunnen_fu_max_pct",
                    "brunnen_kp_pct_pro_bar",
                    "brunnen_fu_ramp_up_pct_s",
                    "brunnen_fu_ramp_down_pct_s",
                    "brunnen_flow_min_l_min",
                    "brunnen_flow_timeout_s",
                    "brunnen_flow_stop_tolerance_bar",
                }:
                    self.set(name, value)
            except (TypeError, ValueError):
                continue


def _setting(settings: dict[str, Any], path: str, default: Any) -> Any:
    node: Any = settings
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
