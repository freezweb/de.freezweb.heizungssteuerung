"""Persistente Anlagenfreigaben fuer Quellen und Senken."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .state import StateStore


DEFAULT_SOURCES = {
    "oelbrenner": True,
    "wp1": False,
    "wp2": False,
    "bwwp": False,
}

DEFAULT_SINKS = {
    "brauchwasser": True,
    "fbh_eg": True,
    "klima_og": False,
    "nebengeb": False,
    "hk_backup": False,
    "pool": False,
}


@dataclass
class Freigaben:
    sources: dict[str, bool]
    sinks: dict[str, bool]
    store: StateStore | None = None

    @classmethod
    def from_settings(cls, settings: dict[str, Any], store: StateStore | None = None) -> "Freigaben":
        raw = settings.get("freigaben", {})
        sources = {**DEFAULT_SOURCES, **_bool_mapping(raw.get("quellen", {}))}
        sinks = {**DEFAULT_SINKS, **_bool_mapping(raw.get("senken", {}))}
        state = store.load() if store is not None else {}
        sources.update(_bool_mapping(state.get("quellen", {})))
        sinks.update(_bool_mapping(state.get("senken", {})))
        return cls(sources=sources, sinks=sinks, store=store)

    def set(self, group: str, name: str, enabled: bool) -> bool:
        if group == "quellen" and name in self.sources:
            self.sources[name] = bool(enabled)
            self.save()
            return True
        if group == "senken" and name in self.sinks:
            self.sinks[name] = bool(enabled)
            self.save()
            return True
        return False

    def source_enabled(self, name: str) -> bool:
        return bool(self.sources.get(name, False))

    def sink_enabled(self, name: str) -> bool:
        return bool(self.sinks.get(name, False))

    def snapshot(self) -> dict[str, dict[str, bool]]:
        return {
            "quellen": dict(sorted(self.sources.items())),
            "senken": dict(sorted(self.sinks.items())),
        }

    def save(self) -> None:
        if self.store is not None:
            self.store.save(self.snapshot())


def _bool_mapping(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    return {str(key): _as_bool(value) for key, value in raw.items()}


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "on", "yes", "ja", "ein"}
    return bool(value)
