"""Brauchwasser-Laderegelung fuer den Bestandsspeicher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import AppConfig
from .freigaben import Freigaben
from .iohw import HardwareSnapshot
from .regler import ReglerParameter


@dataclass(frozen=True)
class BrauchwasserState:
    enabled: bool
    active: bool
    temp_oben_c: float | None
    temp_unten_c: float | None
    soll_c: float
    hysterese_k: float
    einschalt_c: float
    reason: str
    quelle: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "active": self.active,
            "temp_oben_c": self.temp_oben_c,
            "temp_unten_c": self.temp_unten_c,
            "soll_c": self.soll_c,
            "hysterese_k": self.hysterese_k,
            "einschalt_c": self.einschalt_c,
            "reason": self.reason,
            "quelle": self.quelle,
        }


def compute_brauchwasser(
    app_config: AppConfig,
    snapshot: HardwareSnapshot,
    freigaben: Freigaben,
    regler: ReglerParameter,
    previous_active: bool,
) -> BrauchwasserState:
    """Berechnet, ob der aktuelle Brauchwasserspeicher geladen werden soll."""

    enabled = freigaben.sink_enabled("brauchwasser")
    source_enabled = freigaben.source_enabled("oelbrenner")
    soll_c = float(regler.brauchwasser_soll_c)
    hysterese_k = float(regler.brauchwasser_hysterese_k)
    einschalt_c = soll_c - hysterese_k
    temp_oben = _sensor_value_by_component(app_config, snapshot, "bw_oben")
    temp_unten = _sensor_value_by_component(app_config, snapshot, "bw_unten")
    min_c = float(app_config.setting("brauchwasser.sensor_min_c", -20.0))
    max_c = float(app_config.setting("brauchwasser.sensor_max_c", 95.0))

    active = False
    reason = "warte"
    if not enabled:
        reason = "freigabe_aus"
    elif not source_enabled:
        reason = "quelle_oelbrenner_gesperrt"
    elif not _valid_temp(temp_oben, min_c, max_c):
        reason = "sensor_bw_oben_ungueltig"
    elif previous_active and temp_oben < soll_c:
        active = True
        reason = "hysterese_halten"
    elif temp_oben <= einschalt_c:
        active = True
        reason = "unter_einschaltschwelle"
    elif temp_oben >= soll_c:
        reason = "soll_erreicht"

    return BrauchwasserState(
        enabled=enabled,
        active=active,
        temp_oben_c=temp_oben,
        temp_unten_c=temp_unten,
        soll_c=soll_c,
        hysterese_k=hysterese_k,
        einschalt_c=einschalt_c,
        reason=reason,
        quelle="oelbrenner",
    )


def _sensor_value_by_component(app_config: AppConfig, snapshot: HardwareSnapshot, component: str) -> float | None:
    for channel_id, channel in app_config.io_map.rtd.items():
        if channel.komponente == component:
            return snapshot.rtd.get(channel_id)
    for channel_id, channel in app_config.io_map.ai.items():
        if channel.komponente == component:
            return snapshot.ai.get(channel_id)
    return None


def _valid_temp(value: float | None, min_c: float, max_c: float) -> bool:
    return value is not None and min_c <= value <= max_c
