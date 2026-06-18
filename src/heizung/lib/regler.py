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

    @classmethod
    def from_settings(cls, settings: dict[str, Any], store: StateStore | None = None) -> "ReglerParameter":
        regler = cls(
            store=store,
            mischer_reserve_k=float(_setting(settings, "regelung.mischer_reserve_k", 5.0)),
            wp_parallel_ab_aktive_kreise=int(_setting(settings, "wp.parallel_ab_aktive_kreise", 2)),
            brauchwasser_soll_c=float(_setting(settings, "brauchwasser.soll_c", 50.0)),
            brauchwasser_hysterese_k=float(_setting(settings, "brauchwasser.hysterese_k", 5.0)),
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
        return settings

    def snapshot(self) -> dict[str, float | int]:
        return {
            "mischer_reserve_k": self.mischer_reserve_k,
            "wp_parallel_ab_aktive_kreise": self.wp_parallel_ab_aktive_kreise,
            "brauchwasser_soll_c": self.brauchwasser_soll_c,
            "brauchwasser_hysterese_k": self.brauchwasser_hysterese_k,
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
            except (TypeError, ValueError):
                continue


def _setting(settings: dict[str, Any], path: str, default: Any) -> Any:
    node: Any = settings
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
