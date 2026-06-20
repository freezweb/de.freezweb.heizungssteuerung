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

    settings = regler.as_settings({"regelung": {}, "wp": {}})

    assert settings["regelung"]["mischer_reserve_k"] == 7.5
    assert settings["wp"]["parallel_ab_aktive_kreise"] == 3
    assert settings["brauchwasser"]["soll_c"] == 52.5
    assert settings["brauchwasser"]["hysterese_k"] == 6.0
    assert settings["brunnen"]["min_druck_bar"] == 2.1
    assert settings["brunnen"]["max_druck_bar"] == 4.5
    assert settings["brunnen"]["regeldruck_bar"] == 3.3


def test_regler_parameters_persist(tmp_path: Path):
    store = StateStore(tmp_path / "regler.json")
    regler = ReglerParameter.from_settings({}, store)
    regler.set("mischer_reserve_k", 4)

    reloaded = ReglerParameter.from_settings({}, store)

    assert reloaded.mischer_reserve_k == 4.0
