"""Hydraulik-Routing fuer den gemeinsamen Gesamtwaermekreis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .failsafe import FailsafeState
from .freigaben import Freigaben
from .mqtt_bridge import Demand


DEFAULT_COMMON_DEMANDS = ("fbh_eg", "klima_og", "nebengeb", "pool", "hk_backup")


@dataclass(frozen=True)
class RoutingState:
    common_active: bool
    active_demands: tuple[str, ...]
    common_demands: tuple[str, ...]
    source_count: int
    active_sources: tuple[str, ...]
    vl_soll: float | None
    pool_active: bool
    bwwp_active: bool
    failsafe_active: bool
    heat_demand_kw: float | None = None
    single_wp_available_kw: float | None = None
    wp_parallel_threshold_kw: float | None = None
    wp_count_reason: str = "keine_anforderung"

    def as_payload(self) -> dict[str, Any]:
        return {
            "common_active": self.common_active,
            "active_demands": list(self.active_demands),
            "common_demands": list(self.common_demands),
            "source_count": self.source_count,
            "active_sources": list(self.active_sources),
            "vl_soll": self.vl_soll,
            "pool_active": self.pool_active,
            "bwwp_active": self.bwwp_active,
            "failsafe_active": self.failsafe_active,
            "heat_demand_kw": self.heat_demand_kw,
            "single_wp_available_kw": self.single_wp_available_kw,
            "wp_parallel_threshold_kw": self.wp_parallel_threshold_kw,
            "wp_count_reason": self.wp_count_reason,
        }


def compute_routing(
    settings: dict[str, Any],
    demands: dict[str, Demand],
    failsafe_state: FailsafeState,
    freigaben: Freigaben | None = None,
    outside_temp_c: float | None = None,
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
    allowed_active = {
        name: demand
        for name, demand in active.items()
        if name == "bwwp" or _sink_enabled(freigaben, name)
    }
    common_active = {name: demand for name, demand in allowed_active.items() if name in common_names}
    reserve_k = float(_setting(settings, "regelung.mischer_reserve_k", 5))

    vl_values = [float(demand.vl_soll) for demand in common_active.values() if demand.vl_soll is not None]
    vl_soll = max(vl_values) + reserve_k if vl_values else None
    if failsafe_state.active:
        vl_soll = failsafe_state.vl_soll

    common_requested = bool(common_active) or (failsafe_state.active and vl_soll is not None)
    parallel_ab_kreise = int(_setting(settings, "wp.parallel_ab_aktive_kreise", 2))
    heat_demand_kw = _sum_heat_demand_kw(common_active)
    single_wp_available_kw = _wp_available_kw(settings, outside_temp_c)
    parallel_ab_pct = float(_setting(settings, "wp.parallel_ab_pct", 50))
    wp_parallel_threshold_kw = (
        single_wp_available_kw * parallel_ab_pct / 100.0 if single_wp_available_kw is not None else None
    )
    wp_count_reason = "keine_anforderung"
    active_wps: tuple[str, ...] = ()
    if common_requested:
        wanted_wp_count = 1
        if heat_demand_kw is not None and wp_parallel_threshold_kw is not None:
            wanted_wp_count = 2 if heat_demand_kw >= wp_parallel_threshold_kw else 1
            wp_count_reason = "waermebedarf_kw"
        else:
            wanted_wp_count = 2 if len(common_active) >= parallel_ab_kreise else 1
            wp_count_reason = "aktive_kreise_fallback"
        enabled_wps = [name for name in ("wp1", "wp2") if _source_enabled(freigaben, name)]
        active_wps = tuple(enabled_wps[:wanted_wp_count])
    oel_active = bool(
        common_requested
        and _source_enabled(freigaben, "oelbrenner")
        and _setting(settings, "regelung.oelbrenner_unterstuetzung", True)
    )
    active_sources = tuple([*(["oelbrenner"] if oel_active else []), *active_wps])
    common_is_active = common_requested and bool(active_sources)
    source_count = len(active_wps)

    pool_active = common_is_active and "pool" in common_active
    bwwp_demand = demands.get("bwwp")
    bwwp_active = bool(bwwp_demand and bwwp_demand.aktiv and _source_enabled(freigaben, "bwwp"))
    bwwp_soll = (
        float(bwwp_demand.vl_soll)
        if bwwp_demand and bwwp_demand.vl_soll is not None
        else float(_setting(settings, "wp.bwwp.soll_normal", 50))
    )

    state = RoutingState(
        common_active=common_is_active,
        active_demands=tuple(sorted(allowed_active)),
        common_demands=tuple(sorted(common_active if common_is_active else {})),
        source_count=source_count,
        active_sources=active_sources,
        vl_soll=vl_soll,
        pool_active=pool_active,
        bwwp_active=bwwp_active,
        failsafe_active=failsafe_state.active,
        heat_demand_kw=heat_demand_kw,
        single_wp_available_kw=single_wp_available_kw,
        wp_parallel_threshold_kw=wp_parallel_threshold_kw,
        wp_count_reason=wp_count_reason,
    )

    do = {
        # DO01 kann zusaetzlich durch die Brauchwasserladung angefordert werden.
        # DO02 gehoert nur zur separaten Brauchwasser-Laderegelung.
        "DO01": oel_active,
        "DO02": False,
        "DO03": "wp1" in active_wps,
        "DO04": "wp2" in active_wps,
        "DO05": bwwp_active,
        # Brunnenkuehlung ist eine eigene Betriebsart und wird hier nicht automatisch aktiviert.
        "DO06": False,
        "DO07": pool_active,
        # WP1/WP2 in den gemeinsamen Erzeuger-/Verteilerkreis oeffnen.
        "DO08": "wp1" in active_wps,
        "DO09": False,
        "DO10": "wp2" in active_wps,
        "DO11": False,
        # Pool ist Senke am Gesamtwaermekreis, nicht exklusiv an einer WP.
        "DO12": pool_active,
        "DO13": False,
        "DO14": "nebengeb" in common_active,
        "DO15": False,
        # HK-Backup-OG Mischer/Pumpe sitzen am Keller-Slave, nicht auf der Hauptsteuerung.
        "DO16": False,
        "DO17": False,
        "DO18": "nebengeb" in common_active,
        "DO19": pool_active,
        "K-DO01": "fbh_eg" in common_active,
        "K-DO02": "klima_og" in common_active,
        "K-DO03": "hk_backup" in common_active,
    }

    ao = {
        "AO01": float(vl_soll) if vl_soll is not None and "wp1" in active_wps else 0.0,
        "AO02": float(vl_soll) if vl_soll is not None and "wp2" in active_wps else 0.0,
        "AO03": bwwp_soll if bwwp_active else 0.0,
        "AO04": 100.0 if "nebengeb" in common_active else 0.0,
        "AO05": 0.0,
        "AO06": 100.0 if "wp1" in active_wps else 0.0,
        "AO07": 100.0 if "wp2" in active_wps else 0.0,
        "AO08": 100.0 if pool_active else 0.0,
        "AO09": float(_setting(settings, "pool.filter_speed_pct", 100)) if pool_active else 0.0,
        "K-AO02": 100.0 if "fbh_eg" in common_active else 0.0,
        "K-AO03": 100.0 if "klima_og" in common_active else 0.0,
        "K-AO04": 100.0 if "hk_backup" in common_active else 0.0,
    }

    return state, do, ao


def _setting(settings: dict[str, Any], path: str, default: Any) -> Any:
    node: Any = settings
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _sum_heat_demand_kw(common_active: dict[str, Demand]) -> float | None:
    values: list[float] = []
    for demand in common_active.values():
        if demand.leistung_kw is None:
            continue
        value = max(0.0, float(demand.leistung_kw))
        if value > 0.0:
            values.append(value)
    return round(sum(values), 3) if values else None


def _wp_available_kw(settings: dict[str, Any], outside_temp_c: float | None) -> float | None:
    points_raw = _setting(settings, "wp.leistungskurve_kw", None)
    if isinstance(points_raw, list) and points_raw:
        points: list[tuple[float, float]] = []
        for point in points_raw:
            if not isinstance(point, dict):
                continue
            try:
                points.append((float(point["aussen"]), float(point["kw"])))
            except (KeyError, TypeError, ValueError):
                continue
        if points:
            return round(_interpolate(points, outside_temp_c), 3)
    try:
        return float(_setting(settings, "wp.nennleistung_kw", 18.0))
    except (TypeError, ValueError):
        return None


def _interpolate(points: list[tuple[float, float]], outside_temp_c: float | None) -> float:
    points = sorted(points)
    if outside_temp_c is None:
        # Ohne Aussenfuehler konservativ den kuehlsten Stuetzpunkt nutzen.
        return points[0][1]
    temp = float(outside_temp_c)
    if temp <= points[0][0]:
        return points[0][1]
    if temp >= points[-1][0]:
        return points[-1][1]
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if x1 <= temp <= x2:
            span = x2 - x1
            if span == 0:
                return y2
            ratio = (temp - x1) / span
            return y1 + ratio * (y2 - y1)
    return points[-1][1]


def _source_enabled(freigaben: Freigaben | None, name: str) -> bool:
    return True if freigaben is None else freigaben.source_enabled(name)


def _sink_enabled(freigaben: Freigaben | None, name: str) -> bool:
    return True if freigaben is None else freigaben.sink_enabled(name)
