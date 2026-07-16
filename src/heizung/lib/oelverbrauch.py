"""Geschaetzter Oelverbrauch aus der Brenner-Betriebsmeldung."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from html import unescape
from typing import Any
from urllib.request import Request, urlopen

from .state import StateStore


@dataclass(frozen=True)
class OelverbrauchConfig:
    enabled: bool = True
    burner_component: str = "brenner_betrieb"
    brenner_kw: float = 25.0
    kwh_per_liter: float = 10.0
    dieselpreis_eur_l: float = 2.079
    dieselpreis_url: str = "https://www.clever-tanken.de/tankstelle_details/wittenberge-lenzener-chaussee-tankstelle-am-e-cen"
    dieselpreis_poll_interval_s: float = 1800.0
    dieselpreis_timeout_s: float = 10.0
    max_update_interval_s: float = 300.0
    state_persist_path: str = "state/oelverbrauch.json"

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "OelverbrauchConfig":
        raw = settings.get("oelverbrauch", {})
        if not isinstance(raw, dict):
            raw = {}
        return cls(
            enabled=bool(raw.get("enabled", True)),
            burner_component=str(raw.get("burner_component", "brenner_betrieb")),
            brenner_kw=float(raw.get("brenner_kw", 25.0)),
            kwh_per_liter=max(0.1, float(raw.get("kwh_per_liter", 10.0))),
            dieselpreis_eur_l=max(0.0, float(raw.get("dieselpreis_eur_l", 2.079))),
            dieselpreis_url=str(
                raw.get(
                    "dieselpreis_url",
                    "https://www.clever-tanken.de/tankstelle_details/wittenberge-lenzener-chaussee-tankstelle-am-e-cen",
                )
            ),
            dieselpreis_poll_interval_s=max(60.0, float(raw.get("dieselpreis_poll_interval_s", 1800.0))),
            dieselpreis_timeout_s=max(1.0, float(raw.get("dieselpreis_timeout_s", 10.0))),
            max_update_interval_s=max(1.0, float(raw.get("max_update_interval_s", 300.0))),
            state_persist_path=str(raw.get("state_persist_path", "state/oelverbrauch.json")),
        )


@dataclass(frozen=True)
class DieselPriceSnapshot:
    price_eur_l: float
    station: str
    source_url: str
    remote_updated: str | None = None


@dataclass(frozen=True)
class OelverbrauchSnapshot:
    burner_running: bool | None
    total_liter: float
    total_m3: float
    total_kwh: float
    runtime_h: float
    cost_eur: float
    dieselpreis_eur_l: float
    dieselpreis_remote_updated: str | None
    dieselpreis_last_ok_ts: float | None
    dieselpreis_error: str
    dieselpreis_source: str
    liter_per_hour: float
    current_liter_per_hour: float
    current_kw: float
    current_cost_eur_per_hour: float

    def as_payload(self) -> dict[str, Any]:
        return {
            "burner_running": self.burner_running,
            "total_liter": round(self.total_liter, 4),
            "total_m3": round(self.total_m3, 6),
            "total_kwh": round(self.total_kwh, 3),
            "runtime_h": round(self.runtime_h, 4),
            "cost_eur": round(self.cost_eur, 2),
            "dieselpreis_eur_l": round(self.dieselpreis_eur_l, 4),
            "dieselpreis_remote_updated": self.dieselpreis_remote_updated,
            "dieselpreis_last_ok_ts": self.dieselpreis_last_ok_ts,
            "dieselpreis_error": self.dieselpreis_error,
            "dieselpreis_source": self.dieselpreis_source,
            "liter_per_hour": round(self.liter_per_hour, 4),
            "current_liter_per_hour": round(self.current_liter_per_hour, 4),
            "current_kw": round(self.current_kw, 3),
            "current_cost_eur_per_hour": round(self.current_cost_eur_per_hour, 4),
        }


class OelverbrauchTracker:
    def __init__(self, config: OelverbrauchConfig, store: StateStore) -> None:
        self.store = store
        data = store.load()
        state_price = _optional_float(data.get("dieselpreis_eur_l"))
        self.config = replace(config, dieselpreis_eur_l=state_price) if state_price is not None else config
        self.total_liter = max(0.0, float(data.get("total_liter", 0.0)))
        self.runtime_s = max(0.0, float(data.get("runtime_s", 0.0)))
        self.dieselpreis_last_ok_ts = _optional_float(data.get("dieselpreis_last_ok_ts"))
        self.dieselpreis_remote_updated = _optional_str(data.get("dieselpreis_remote_updated"))
        self.dieselpreis_error = ""
        self._last_update_ts: float | None = None
        self._last_save_ts: float = 0.0
        self._dirty = False

    @property
    def liter_per_hour(self) -> float:
        return self.config.brenner_kw / self.config.kwh_per_liter

    def update(self, now_ts: float, burner_running: bool | None) -> OelverbrauchSnapshot:
        if not self.config.enabled:
            return self.snapshot(burner_running)

        if self._last_update_ts is None:
            self._last_update_ts = now_ts
            return self.snapshot(burner_running)

        elapsed_s = max(0.0, min(now_ts - self._last_update_ts, self.config.max_update_interval_s))
        self._last_update_ts = now_ts
        if burner_running is True and elapsed_s > 0:
            self.runtime_s += elapsed_s
            self.total_liter += self.liter_per_hour * elapsed_s / 3600.0
            self._dirty = True

        if self._dirty and now_ts - self._last_save_ts >= 10.0:
            self.save(now_ts)
        return self.snapshot(burner_running)

    def update_dieselpreis(self, price: DieselPriceSnapshot, now_ts: float) -> None:
        self.config = replace(self.config, dieselpreis_eur_l=max(0.0, price.price_eur_l))
        self.dieselpreis_last_ok_ts = now_ts
        self.dieselpreis_remote_updated = price.remote_updated
        self.dieselpreis_error = ""
        self._dirty = True
        self.save(now_ts)

    def mark_price_error(self, error: str) -> None:
        self.dieselpreis_error = error

    def snapshot(self, burner_running: bool | None) -> OelverbrauchSnapshot:
        total_kwh = self.total_liter * self.config.kwh_per_liter
        current_liter_per_hour = self.liter_per_hour if burner_running is True else 0.0
        current_kw = self.config.brenner_kw if burner_running is True else 0.0
        return OelverbrauchSnapshot(
            burner_running=burner_running,
            total_liter=self.total_liter,
            # Home Assistant kann den Energie-Gasreiter gut mit m3-Zaehlern
            # nutzen. Hier ist der "m3"-Wert bewusst ein Liter-Aequivalent,
            # damit der Oelverbrauch im Dashboard lesbar als Literzahl steht.
            total_m3=self.total_liter,
            total_kwh=total_kwh,
            runtime_h=self.runtime_s / 3600.0,
            cost_eur=self.total_liter * self.config.dieselpreis_eur_l,
            dieselpreis_eur_l=self.config.dieselpreis_eur_l,
            dieselpreis_remote_updated=self.dieselpreis_remote_updated,
            dieselpreis_last_ok_ts=self.dieselpreis_last_ok_ts,
            dieselpreis_error=self.dieselpreis_error,
            dieselpreis_source=self.config.dieselpreis_url,
            liter_per_hour=self.liter_per_hour,
            current_liter_per_hour=current_liter_per_hour,
            current_kw=current_kw,
            current_cost_eur_per_hour=current_liter_per_hour * self.config.dieselpreis_eur_l,
        )

    def save(self, now_ts: float | None = None) -> None:
        self.store.save(
            {
                "runtime_s": self.runtime_s,
                "total_liter": self.total_liter,
                "dieselpreis_eur_l": self.config.dieselpreis_eur_l,
                "dieselpreis_last_ok_ts": self.dieselpreis_last_ok_ts,
                "dieselpreis_remote_updated": self.dieselpreis_remote_updated,
            }
        )
        self._dirty = False
        if now_ts is not None:
            self._last_save_ts = now_ts


class DieselPriceClient:
    _PRICE_RE = re.compile(
        r'<div class="price-type-name">\s*Diesel\s*</div>.*?'
        r'<span id="current-price-\d+">(?P<price>\d+[,.]\d+)</span>\s*'
        r'<sup id="suffix-price-\d+">(?P<suffix>\d)</sup>',
        re.DOTALL | re.IGNORECASE,
    )
    _UPDATED_RE = re.compile(r"Letzte MTS-K Preisänderung:\s*([^<]+)", re.IGNORECASE)

    def __init__(self, config: OelverbrauchConfig) -> None:
        self.config = config

    def fetch(self) -> DieselPriceSnapshot:
        if not self.config.dieselpreis_url:
            raise RuntimeError("kein Dieselpreis-URL konfiguriert")
        request = Request(
            self.config.dieselpreis_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; heizung-oelverbrauch/1.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urlopen(request, timeout=self.config.dieselpreis_timeout_s) as response:  # noqa: S310
            html = response.read().decode("utf-8", errors="replace")
        return parse_clever_tanken_dieselpreis(html, self.config.dieselpreis_url)


def parse_clever_tanken_dieselpreis(html: str, source_url: str = "") -> DieselPriceSnapshot:
    match = DieselPriceClient._PRICE_RE.search(html)
    if match is None:
        raise ValueError("Dieselpreis im clever-tanken HTML nicht gefunden")
    price = float(match.group("price").replace(",", ".")) + int(match.group("suffix")) / 1000.0
    updated_match = DieselPriceClient._UPDATED_RE.search(html)
    remote_updated = unescape(updated_match.group(1)).strip() if updated_match else None
    return DieselPriceSnapshot(
        price_eur_l=price,
        station="Oktan/E-Center Lenzener Chaussee 21 Wittenberge",
        source_url=source_url,
        remote_updated=remote_updated,
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
