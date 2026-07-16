"""Tor-Kommandos mit Endschalter-Guards."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TorEntscheidung:
    ausgang: str | None
    ausfuehren: bool
    grund: str


def entscheide_tor_command(command: str, links_zu: bool | None, rechts_zu: bool | None) -> TorEntscheidung:
    """Mappt semantische Torbefehle auf die vorhandenen Tastereingänge."""
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
