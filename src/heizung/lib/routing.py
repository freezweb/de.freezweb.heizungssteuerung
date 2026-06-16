"""Hydraulik-Routing fuer den gemeinsamen Gesamtwaermekreis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .failsafe import FailsafeState
from .mqtt_bridge import Demand


DEFAULT_COMMON_DEMANDS = ("fbh_eg", "klima_og", "nebengeb", "pool", "hk_backup")


@dataclass(frozen=True)
class RoutingState:
    common_active: bool
    active_demands: tuple[str, ...]
    common_demands: tuple[str, ...]
    source_count: int
    vl_soll: float | None
    pool_active: bool
    bwwp_active: bool
    failsafe_active: bool

    def as_payload(self) -> dict[str, Any]:
        return {
            "common_active": self.common_active,
            "active_demands": list(self.active_demands),
            "common_demands": list(self.common_demands),
            "source_count": self.source_count,
            "vl_soll": self.vl_soll,
            "pool_active": self.pool_active,
            "bwwp_active": self.bwwp_active,
            "failsafe_active": self.failsafe_active,
        }


def compute_routing(
    settings: dict[str, Any],
    demands: dict[str, Demand],
    failsafe_state: FailsafeState,
) -> tuple[RoutingState, dict[str, bool], dict[str, float]]:
    """Berechnet Erzeuger, Senken und Sollwerte fuer den gemeinsamen Heizkreis.

    Beide Haupt-Waermepumpen speisen denselben Gesamtwaermekreis. Pool,
    Hauptgebaeude, Nebengebaeude und spaetere Backup-Strange sind Senken dieses
    Kreises und nicht fest einer bestimmten Waermepumpe zugeordnet.
    """

    common_names = tuple(_setting(settings, "hydraulik.common_heat_demands", DEFAULT_COMMON_DEMANDS))
    active = {
        name: demand
        for name, demand in demands.items()
        if demand.aktiv and demand.vl_soll is not None
    }
    common_active = {name: demand for name, demand in active.items() if name in common_names}
    reserve_k = float(_setting(settings, "regelung.mischer_reserve_k", 5))

    vl_values = [float(demand.vl_soll) for demand in common_active.values() if demand.vl_soll is not None]
    vl_soll = max(vl_values) + reserve_k if vl_values else None
    if failsafe_state.active:
        vl_soll = failsafe_state.vl_soll

    common_is_active = bool(common_active) or (failsafe_state.active and vl_soll is not None)
    parallel_ab_kreise = int(_setting(settings, "wp.parallel_ab_aktive_kreise", 2))
    source_count = 0
    if common_is_active:
        source_count = 2 if len(common_active) >= parallel_ab_kreise else 1

    pool_active = "pool" in common_active
    bwwp_demand = demands.get("bwwp")
    bwwp_active = bool(bwwp_demand and bwwp_demand.aktiv)
    bwwp_soll = (
        float(bwwp_demand.vl_soll)
        if bwwp_demand and bwwp_demand.vl_soll is not None
        else float(_setting(settings, "wp.bwwp.soll_normal", 50))
    )

    state = RoutingState(
        common_active=common_is_active,
        active_demands=tuple(sorted(active)),
        common_demands=tuple(sorted(common_active)),
        source_count=source_count,
        vl_soll=vl_soll,
        pool_active=pool_active,
        bwwp_active=bwwp_active,
        failsafe_active=failsafe_state.active,
    )

    do = {
        # Uebergangsweise alter Kessel/BW-Pumpe. WPs sind DO03/DO04.
        "DO01": bool(common_is_active and _setting(settings, "regelung.oelbrenner_unterstuetzung", True)),
        "DO02": bwwp_active,
        "DO03": source_count >= 1,
        "DO04": source_count >= 2,
        "DO05": bwwp_active,
        # Brunnenkuehlung ist eine eigene Betriebsart und wird hier nicht automatisch aktiviert.
        "DO06": False,
        "DO07": pool_active,
        # WP1/WP2 in den gemeinsamen Erzeuger-/Verteilerkreis oeffnen.
        "DO08": source_count >= 1,
        "DO09": False,
        "DO10": source_count >= 2,
        "DO11": False,
        # Pool ist Senke am Gesamtwaermekreis, nicht exklusiv an einer WP.
        "DO12": pool_active,
        "DO13": False,
        "DO14": "nebengeb" in common_active,
        "DO15": False,
        "DO16": "hk_backup" in common_active,
        "DO17": False,
        "DO18": "nebengeb" in common_active,
        "DO19": pool_active,
    }

    ao = {
        "AO01": float(vl_soll) if vl_soll is not None else 0.0,
        "AO02": float(vl_soll) if vl_soll is not None else 0.0,
        "AO03": bwwp_soll if bwwp_active else 0.0,
        "AO04": 100.0 if "nebengeb" in common_active else 0.0,
        "AO05": 100.0 if "hk_backup" in common_active else 0.0,
        "AO06": 100.0 if source_count >= 1 else 0.0,
        "AO07": 100.0 if source_count >= 2 else 0.0,
        "AO08": 100.0 if pool_active else 0.0,
        "AO09": float(_setting(settings, "pool.filter_speed_pct", 100)) if pool_active else 0.0,
    }

    return state, do, ao


def _setting(settings: dict[str, Any], path: str, default: Any) -> Any:
    node: Any = settings
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
