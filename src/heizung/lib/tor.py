"""Sicherer virtueller Torzustand fuer Betrieb ohne Endlagensensoren."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .state import StateStore


@dataclass(frozen=True)
class TorEntscheidung:
    ausgang: str | None
    ausfuehren: bool
    grund: str
    ziel: str | None = None


class TorRuntime:
    """Persistiert Position und blockiert Folgeimpulse waehrend einer Torfahrt."""

    VALID_POSITIONS = {"offen", "geschlossen"}

    def __init__(
        self,
        store: StateStore,
        *,
        fahrzeit_s: float = 30.0,
        initial_position: str = "geschlossen",
        halb_aktiv: bool = False,
    ) -> None:
        self.store = store
        self.fahrzeit_s = max(1.0, float(fahrzeit_s))
        self.halb_aktiv = bool(halb_aktiv)
        loaded = store.load()
        position = str(loaded.get("position", initial_position)).strip().lower()
        if position not in self.VALID_POSITIONS:
            position = "geschlossen"
        self._state: dict[str, Any] = {
            "position": position,
            "ziel": loaded.get("ziel"),
            "started_at": loaded.get("started_at"),
            "busy_until": float(loaded.get("busy_until", 0.0) or 0.0),
            "verified_at": loaded.get("verified_at"),
        }
        self._save()

    def entscheide(self, command: str, now_ts: float) -> TorEntscheidung:
        command = command.strip().lower()
        if command in {"oeffnen_halb", "halb"}:
            return TorEntscheidung(None, False, "tor_halb_nicht_angeschlossen")
        if command in {"oeffnen_ganz", "ganz", "auf"}:
            ziel = "offen"
        elif command in {"schliessen", "zu"}:
            ziel = "geschlossen"
        else:
            return TorEntscheidung(None, False, "unbekannter_torbefehl")

        if now_ts < self.busy_until:
            return TorEntscheidung(None, False, "tor_faehrt_bereits", ziel)
        if self._state.get("ziel") is not None:
            return TorEntscheidung(None, False, "kamerapruefung_ausstehend", ziel)
        if self.position == ziel:
            return TorEntscheidung(None, False, f"tor_bereits_{ziel}", ziel)

        # Vor dem Hardwareimpuls speichern: selbst ein Fehler danach darf keinen
        # zweiten Toggle-Impuls waehrend der angenommenen Fahrt erlauben.
        self._state.update(
            {
                "ziel": ziel,
                "started_at": float(now_ts),
                "busy_until": float(now_ts) + self.fahrzeit_s,
            }
        )
        self._save()
        return TorEntscheidung("tor_ganz", True, f"tor_{ziel}_fahren", ziel)

    def bestaetige_position(self, position: str, now_ts: float) -> bool:
        position = position.strip().lower()
        if position in {"zu", "closed"}:
            position = "geschlossen"
        elif position in {"auf", "open"}:
            position = "offen"
        if position not in self.VALID_POSITIONS or now_ts < self.busy_until:
            return False
        self._state.update(
            {
                "position": position,
                "ziel": None,
                "started_at": None,
                "busy_until": 0.0,
                "verified_at": float(now_ts),
            }
        )
        self._save()
        return True

    @property
    def position(self) -> str:
        return str(self._state["position"])

    @property
    def busy_until(self) -> float:
        return float(self._state.get("busy_until", 0.0) or 0.0)

    def snapshot(self, now_ts: float) -> dict[str, Any]:
        ziel = self._state.get("ziel")
        if ziel is not None and now_ts < self.busy_until:
            status = "Tor Oeffnet" if ziel == "offen" else "Tor Schliesst"
        elif ziel is not None:
            status = "Kamerapruefung ausstehend"
        else:
            status = "Tor Offen" if self.position == "offen" else "Tor Geschlossen"
        return {
            **self._state,
            "status": status,
            "gesperrt": bool(ziel is not None),
            "restzeit_s": max(0, int(round(self.busy_until - now_ts))),
            "fahrzeit_s": self.fahrzeit_s,
            "halb_aktiv": self.halb_aktiv,
        }

    def _save(self) -> None:
        self.store.save(self._state)


def entscheide_tor_command(command: str, links_zu: bool | None, rechts_zu: bool | None) -> TorEntscheidung:
    """Legacy-Entscheidung fuer Installationen mit echten Endschaltern."""
    beide_zu = links_zu is True and rechts_zu is True
    beide_nicht_zu = links_zu is False and rechts_zu is False

    if command in {"schliessen", "zu"}:
        if beide_zu:
            return TorEntscheidung(None, False, "beide_fluegel_bereits_geschlossen")
        if links_zu is True and rechts_zu is False:
            return TorEntscheidung("tor_halb", True, "rechter_fluegel_schliessen")
        return TorEntscheidung("tor_ganz", True, "tor_schliessen")
    if command in {"oeffnen_halb", "halb"}:
        if rechts_zu is False:
            return TorEntscheidung(None, False, "rechter_fluegel_bereits_nicht_geschlossen")
        return TorEntscheidung("tor_halb", True, "rechten_fluegel_oeffnen")
    if command in {"oeffnen_ganz", "ganz", "auf"}:
        if beide_nicht_zu:
            return TorEntscheidung(None, False, "beide_fluegel_bereits_nicht_geschlossen")
        return TorEntscheidung("tor_ganz", True, "tor_ganz_oeffnen")
    return TorEntscheidung(None, False, "unbekannter_torbefehl")
