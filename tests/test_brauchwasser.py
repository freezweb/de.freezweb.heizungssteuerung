from pathlib import Path

from heizung.lib.brauchwasser import compute_brauchwasser
from heizung.lib.config import AppConfig, ChannelConfig, IoMap
from heizung.lib.freigaben import Freigaben
from heizung.lib.iohw import HardwareSnapshot
from heizung.lib.regler import ReglerParameter


def _config() -> AppConfig:
    io_map = IoMap(
        revpi={},
        do={},
        di={},
        ai={},
        ao={},
        rtd={
            "RTD03": ChannelConfig("RTD03", "rtd", "RTDValue_1_i13", "bw_oben"),
            "RTD04": ChannelConfig("RTD04", "rtd", "RTDValue_2_i13", "bw_unten"),
        },
    )
    return AppConfig(
        root_dir=Path("."),
        config_dir=Path("config"),
        io_map=io_map,
        settings={"brauchwasser": {"sensor_max_c": 95}},
        mqtt={},
        modbus_map={},
    )


def _freigaben(enabled: bool = True, oel: bool = True) -> Freigaben:
    return Freigaben(
        sources={"oelbrenner": oel, "wp1": False, "wp2": False, "bwwp": False},
        sinks={
            "brauchwasser": enabled,
            "fbh_eg": True,
            "klima_og": False,
            "nebengeb": False,
            "hk_backup": False,
            "pool": False,
        },
    )


def _regler() -> ReglerParameter:
    return ReglerParameter(brauchwasser_soll_c=50.0, brauchwasser_hysterese_k=5.0)


def _snapshot(temp_oben: float | None) -> HardwareSnapshot:
    rtd = {}
    if temp_oben is not None:
        rtd["RTD03"] = temp_oben
    rtd["RTD04"] = 42.0
    return HardwareSnapshot(di={}, do={}, ai={}, ao={}, rtd=rtd)


def test_brauchwasser_starts_below_hysteresis_threshold():
    state = compute_brauchwasser(_config(), _snapshot(44.9), _freigaben(), _regler(), previous_active=False)

    assert state.active is True
    assert state.reason == "unter_einschaltschwelle"


def test_brauchwasser_holds_until_soll_is_reached():
    state = compute_brauchwasser(_config(), _snapshot(49.9), _freigaben(), _regler(), previous_active=True)

    assert state.active is True
    assert state.reason == "hysterese_halten"


def test_brauchwasser_stops_at_soll():
    state = compute_brauchwasser(_config(), _snapshot(50.0), _freigaben(), _regler(), previous_active=True)

    assert state.active is False
    assert state.reason == "soll_erreicht"


def test_brauchwasser_freigabe_disables_loading():
    state = compute_brauchwasser(_config(), _snapshot(30.0), _freigaben(enabled=False), _regler(), previous_active=True)

    assert state.active is False
    assert state.reason == "freigabe_aus"


def test_invalid_top_sensor_disables_loading():
    state = compute_brauchwasser(_config(), _snapshot(850.0), _freigaben(), _regler(), previous_active=True)

    assert state.active is False
    assert state.reason == "sensor_bw_oben_ungueltig"
