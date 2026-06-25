from pathlib import Path

from heizung.lib.regler import ReglerParameter
from heizung.lib.state import StateStore


def test_regler_parameters_overlay_settings(tmp_path: Path):
    regler = ReglerParameter.from_settings(
        {"regelung": {"mischer_reserve_k": 5}, "wp": {"parallel_ab_aktive_kreise": 2}},
        StateStore(tmp_path / "regler.json"),
    )

    assert regler.set("mischer_reserve_k", "7,5") is True
    assert regler.set("wp_parallel_ab_aktive_kreise", 3) is True
    assert regler.set("brauchwasser_soll_c", "52,5") is True
    assert regler.set("brauchwasser_hysterese_k", 6) is True
    assert regler.set("brunnen_min_druck_bar", "2,1") is True
    assert regler.set("brunnen_max_druck_bar", "4,5") is True
    assert regler.set("brunnen_regeldruck_bar", "3,3") is True
    assert regler.set("brunnen_fu_start_pct", "28") is True
    assert regler.set("brunnen_fu_max_pct", "75") is True
    assert regler.set("brunnen_kp_pct_pro_bar", "45") is True
    assert regler.set("brunnen_fu_ramp_up_pct_s", "120") is True
    assert regler.set("brunnen_fu_ramp_down_pct_s", "240") is True
    assert regler.set("brunnen_flow_min_l_min", "0,3") is True
    assert regler.set("brunnen_flow_timeout_s", "180") is True
    assert regler.set("brunnen_flow_stop_tolerance_bar", "0,4") is True

    settings = regler.as_settings({"regelung": {}, "wp": {}})

    assert settings["regelung"]["mischer_reserve_k"] == 7.5
    assert settings["wp"]["parallel_ab_aktive_kreise"] == 3
    assert settings["brauchwasser"]["soll_c"] == 52.5
    assert settings["brauchwasser"]["hysterese_k"] == 6.0
    assert settings["brunnen"]["min_druck_bar"] == 2.1
    assert settings["brunnen"]["max_druck_bar"] == 4.5
    assert settings["brunnen"]["regeldruck_bar"] == 3.3
    assert settings["brunnen"]["fu_start_pct"] == 28.0
    assert settings["brunnen"]["fu_max_pct"] == 75.0
    assert settings["brunnen"]["kp_pct_pro_bar"] == 45.0
    assert settings["brunnen"]["fu_ramp_up_pct_s"] == 120.0
    assert settings["brunnen"]["fu_ramp_down_pct_s"] == 240.0
    assert settings["brunnen"]["flow_min_l_min"] == 0.3
    assert settings["brunnen"]["flow_timeout_s"] == 180.0
    assert settings["brunnen"]["flow_stop_regeldruck_tolerance_bar"] == 0.4


def test_regler_parameters_persist(tmp_path: Path):
    store = StateStore(tmp_path / "regler.json")
    regler = ReglerParameter.from_settings({}, store)
    regler.set("mischer_reserve_k", 4)

    reloaded = ReglerParameter.from_settings({}, store)

    assert reloaded.mischer_reserve_k == 4.0


def test_brunnen_regler_parameters_are_clamped():
    regler = ReglerParameter.from_settings({})

    assert regler.set("brunnen_fu_start_pct", 150) is True
    assert regler.set("brunnen_fu_max_pct", 150) is True
    assert regler.set("brunnen_kp_pct_pro_bar", 300) is True
    assert regler.set("brunnen_fu_ramp_up_pct_s", 0) is True
    assert regler.set("brunnen_fu_ramp_down_pct_s", 2000) is True
    assert regler.set("brunnen_flow_min_l_min", 99) is True
    assert regler.set("brunnen_flow_timeout_s", 1) is True
    assert regler.set("brunnen_flow_stop_tolerance_bar", 99) is True

    assert regler.brunnen_fu_start_pct == 100.0
    assert regler.brunnen_fu_max_pct == 100.0
    assert regler.brunnen_kp_pct_pro_bar == 200.0
    assert regler.brunnen_fu_ramp_up_pct_s == 1.0
    assert regler.brunnen_fu_ramp_down_pct_s == 1000.0
    assert regler.brunnen_flow_min_l_min == 20.0
    assert regler.brunnen_flow_timeout_s == 10.0
    assert regler.brunnen_flow_stop_tolerance_bar == 2.0
