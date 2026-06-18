from heizung.lib.failsafe import FailsafeState
from heizung.lib.freigaben import Freigaben
from heizung.lib.mqtt_bridge import Demand
from heizung.lib.routing import compute_routing


def test_pool_and_house_share_common_heat_loop():
    settings = {"regelung": {"mischer_reserve_k": 5}, "wp": {"parallel_ab_aktive_kreise": 2}}
    demands = {
        "fbh_eg": Demand(aktiv=True, vl_soll=35.0),
        "pool": Demand(aktiv=True, vl_soll=38.0),
    }

    state, do, ao = compute_routing(settings, demands, FailsafeState(False, (), None))

    assert state.common_active is True
    assert state.common_demands == ("fbh_eg", "pool")
    assert state.vl_soll == 43.0
    assert state.source_count == 2
    assert do["DO03"] is True
    assert do["DO04"] is True
    assert do["DO12"] is True
    assert do["DO19"] is True
    assert ao["AO01"] == 43.0
    assert ao["AO02"] == 43.0
    assert ao["AO08"] == 100.0


def test_single_common_demand_uses_one_heat_pump():
    state, do, ao = compute_routing(
        {"regelung": {"mischer_reserve_k": 5}, "wp": {"parallel_ab_aktive_kreise": 2}},
        {"nebengeb": Demand(aktiv=True, vl_soll=40.0)},
        FailsafeState(False, (), None),
    )

    assert state.source_count == 1
    assert do["DO03"] is True
    assert do["DO04"] is False
    assert do["DO14"] is True
    assert do["DO18"] is True
    assert ao["AO04"] == 100.0


def test_bwwp_stays_separate_from_common_loop():
    state, do, ao = compute_routing(
        {"wp": {"bwwp": {"soll_normal": 50}}},
        {"bwwp": Demand(aktiv=True, vl_soll=55.0)},
        FailsafeState(False, (), None),
    )

    assert state.common_active is False
    assert state.bwwp_active is True
    assert do["DO03"] is False
    assert do["DO02"] is False
    assert do["DO05"] is True
    assert ao["AO03"] == 55.0


def test_failsafe_drives_common_loop_without_ha_demand():
    state, do, ao = compute_routing({}, {}, FailsafeState(True, ("mqtt_timeout",), 38.0))

    assert state.common_active is True
    assert state.failsafe_active is True
    assert state.vl_soll == 38.0
    assert do["DO03"] is True
    assert ao["AO01"] == 38.0


def test_disabled_sink_is_ignored():
    freigaben = Freigaben(
        sources={"oelbrenner": True, "wp1": True, "wp2": True, "bwwp": False},
        sinks={"fbh_eg": True, "pool": False, "nebengeb": False, "klima_og": False, "hk_backup": False},
    )

    state, do, ao = compute_routing(
        {"regelung": {"mischer_reserve_k": 5}},
        {"pool": Demand(aktiv=True, vl_soll=38.0)},
        FailsafeState(False, (), None),
        freigaben,
    )

    assert state.common_active is False
    assert state.common_demands == ()
    assert do["DO12"] is False
    assert ao["AO08"] == 0.0


def test_oil_can_run_while_heat_pumps_are_disabled():
    freigaben = Freigaben(
        sources={"oelbrenner": True, "wp1": False, "wp2": False, "bwwp": False},
        sinks={"fbh_eg": True, "pool": False, "nebengeb": False, "klima_og": False, "hk_backup": False},
    )

    state, do, ao = compute_routing(
        {"regelung": {"mischer_reserve_k": 5}},
        {"fbh_eg": Demand(aktiv=True, vl_soll=35.0)},
        FailsafeState(False, (), None),
        freigaben,
    )

    assert state.active_sources == ("oelbrenner",)
    assert do["DO01"] is True
    assert do["DO03"] is False
    assert do["DO04"] is False
    assert state.vl_soll == 40.0
    assert ao["AO01"] == 0.0
    assert ao["AO02"] == 0.0


def test_heat_pump_checkbox_adds_source_to_sequence():
    freigaben = Freigaben(
        sources={"oelbrenner": True, "wp1": True, "wp2": False, "bwwp": False},
        sinks={"fbh_eg": True, "pool": False, "nebengeb": False, "klima_og": False, "hk_backup": False},
    )

    state, do, ao = compute_routing(
        {"regelung": {"mischer_reserve_k": 5}},
        {"fbh_eg": Demand(aktiv=True, vl_soll=35.0)},
        FailsafeState(False, (), None),
        freigaben,
    )

    assert state.active_sources == ("oelbrenner", "wp1")
    assert do["DO01"] is True
    assert do["DO03"] is True
    assert do["DO04"] is False
    assert ao["AO01"] == 40.0
    assert ao["AO02"] == 0.0


def test_hk_backup_mixer_is_not_driven_on_main_controller():
    state, do, ao = compute_routing(
        {"regelung": {"mischer_reserve_k": 5}},
        {"hk_backup": Demand(aktiv=True, vl_soll=45.0)},
        FailsafeState(False, (), None),
    )

    assert state.common_active is True
    assert do["DO16"] is False
    assert do["DO17"] is False
    assert ao["AO05"] == 0.0
