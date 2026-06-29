import pytest

from heizung.__main__ import _brunnen_output_ids, _compute_auto_outputs, _compute_oelbrenner_common_heat, _write_outputs
from heizung.lib.config import ChannelConfig, IoMap
from heizung.lib.failsafe import FailsafeState
from heizung.lib.freigaben import Freigaben
from heizung.lib.hand_auto import HandAutoManager
from heizung.lib.iohw import HardwareSnapshot, SimulatedIO
from heizung.lib.mqtt_bridge import Demand
from heizung.lib.regler import ReglerParameter
from heizung.lib.routing import RoutingState
from heizung.lib.state import StateStore


def _io_map() -> IoMap:
    return IoMap(
        revpi={},
        do={
            "DO01": ChannelConfig("DO01", "do", "O_1", "brenner"),
            "DO02": ChannelConfig("DO02", "do", "O_2", "pumpe_bw_lade"),
            "DO18": ChannelConfig("DO18", "do", "O_4_i17", "pumpe_nebengeb"),
            "DO19": ChannelConfig("DO19", "do", "O_5_i17", "pumpe_pool"),
            "K-DO01": ChannelConfig("K-DO01", "do", "O_1", "pumpe_fbh_eg"),
            "K-DO02": ChannelConfig("K-DO02", "do", "O_2", "pumpe_klima_og"),
            "K-DO03": ChannelConfig("K-DO03", "do", "O_3", "pumpe_hk_backup"),
            "K-DO04": ChannelConfig("K-DO04", "do", "O_4", "brunnen_pumpe_freigabe"),
            "DO06": ChannelConfig("DO06", "do", "O_6", "brunnen_mv"),
        },
        di={
            "DI12": ChannelConfig(
                "DI12",
                "di",
                "I_12",
                "oelbrenner_wasserdruck_stoerung",
                polaritaet="NC_SAFE_HIGH",
            ),
            "DI13": ChannelConfig("DI13", "di", "I_13", "brenner_stoerung"),
            "DI15": ChannelConfig(
                "DI15",
                "di",
                "I_1_i17",
                "oelbrenner_stb_stoerung",
                polaritaet="NC_SAFE_HIGH",
            ),
        },
        ai={},
        ao={
            "K-AO01": ChannelConfig("K-AO01", "ao", "AO_1", "brunnen_fu_soll"),
            "K-AO03": ChannelConfig("K-AO03", "ao", "AO_3", "mischer_klima_og_pct"),
        },
        rtd={
            "RTD01": ChannelConfig("RTD01", "rtd", "RTD_1", "vl_sammel"),
            "K-RTD03": ChannelConfig("K-RTD03", "rtd", "RTD_3", "klima_og_vl"),
        },
    )


class _TestConfig:
    def __init__(self, io_map: IoMap, settings: dict) -> None:
        self.io_map = io_map
        self.settings = settings

    def setting(self, path: str, default=None):
        node = self.settings
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("di", "expected"),
    [
        ({"DI12": True, "DI13": False, "DI15": True}, True),
        ({"DI12": False, "DI13": False, "DI15": True}, False),
        ({"DI12": True, "DI13": False, "DI15": False}, False),
        ({"DI12": True, "DI13": True, "DI15": True}, True),
    ],
)
async def test_oelbrenner_safety_chain_hard_locks_burner_output(tmp_path, di, expected):
    io_map = _io_map()
    io = SimulatedIO(io_map)
    hand = HandAutoManager(io_map, StateStore(tmp_path / "hand.json"), default_timeout_min=None)
    hand.set_hand("DO01", True, now_ts=100.0)

    applied_do, _applied_ao = await _write_outputs(
        app_config=type("Config", (), {"io_map": io_map})(),
        local_io_map=io_map,
        io_backend=io,
        hand_auto=hand,
        auto_do={"DO01": True},
        auto_ao={},
        snapshot=HardwareSnapshot(di=di),
        now_ts=101.0,
    )

    assert applied_do["DO01"] is expected
    assert io.do_values["DO01"] is expected


@pytest.mark.asyncio
async def test_burner_fault_keeps_burner_demand_for_physical_reset(tmp_path):
    io_map = _io_map()
    io = SimulatedIO(io_map)
    hand = HandAutoManager(io_map, StateStore(tmp_path / "hand.json"), default_timeout_min=None)

    applied_do, _applied_ao = await _write_outputs(
        app_config=type("Config", (), {"io_map": io_map})(),
        local_io_map=io_map,
        io_backend=io,
        hand_auto=hand,
        auto_do={"DO01": True},
        auto_ao={},
        snapshot=HardwareSnapshot(di={"DI12": True, "DI13": True, "DI15": True}),
        now_ts=101.0,
    )

    assert applied_do["DO01"] is True
    assert io.do_values["DO01"] is True


@pytest.mark.asyncio
async def test_water_shortage_hard_locks_heating_pumps_even_in_hand_mode(tmp_path):
    io_map = _io_map()
    io = SimulatedIO(io_map)
    hand = HandAutoManager(io_map, StateStore(tmp_path / "hand.json"), default_timeout_min=None)
    pump_ids = ("DO02", "DO18", "DO19", "K-DO01", "K-DO02", "K-DO03")
    for channel_id in pump_ids:
        hand.set_hand(channel_id, True, now_ts=100.0)

    applied_do, _applied_ao = await _write_outputs(
        app_config=type("Config", (), {"io_map": io_map})(),
        local_io_map=io_map,
        io_backend=io,
        hand_auto=hand,
        auto_do={channel_id: True for channel_id in pump_ids},
        auto_ao={},
        snapshot=HardwareSnapshot(di={"DI12": False, "DI13": False, "DI15": True}),
        now_ts=101.0,
    )

    for channel_id in pump_ids:
        assert applied_do[channel_id] is False
        assert io.do_values[channel_id] is False

    assert applied_do["K-DO04"] is False


def test_fast_output_set_includes_burner_for_safety_checks():
    io_map = _io_map()
    app_config = type("Config", (), {"io_map": io_map})()

    assert "DO01" in _brunnen_output_ids(app_config)
    for channel_id in ("DO02", "DO18", "DO19", "K-DO01", "K-DO02", "K-DO03"):
        assert channel_id in _brunnen_output_ids(app_config)


def test_oelbrenner_common_heat_stops_when_flow_temperature_is_satisfied():
    io_map = _io_map()
    app_config = type("Config", (), {"io_map": io_map, "setting": lambda _self, _path, default=None: default})()
    routing = RoutingState(
        common_active=True,
        active_demands=("klima_og",),
        common_demands=("klima_og",),
        source_count=0,
        active_sources=("oelbrenner",),
        vl_soll=23.0,
        pool_active=False,
        bwwp_active=False,
        failsafe_active=False,
    )
    snapshot = HardwareSnapshot(rtd={"RTD01": 26.5})

    assert _compute_oelbrenner_common_heat(app_config, snapshot, routing, True, True) is False


def test_oelbrenner_common_heat_uses_hysteresis_for_on_off_control():
    io_map = _io_map()
    app_config = type("Config", (), {"io_map": io_map, "setting": lambda _self, _path, default=None: default})()
    routing = RoutingState(
        common_active=True,
        active_demands=("fbh_eg",),
        common_demands=("fbh_eg",),
        source_count=0,
        active_sources=("oelbrenner",),
        vl_soll=40.0,
        pool_active=False,
        bwwp_active=False,
        failsafe_active=False,
    )

    assert _compute_oelbrenner_common_heat(app_config, HardwareSnapshot(rtd={"RTD01": 38.8}), routing, True, False) is True
    assert _compute_oelbrenner_common_heat(app_config, HardwareSnapshot(rtd={"RTD01": 39.5}), routing, True, True) is True
    assert _compute_oelbrenner_common_heat(app_config, HardwareSnapshot(rtd={"RTD01": 39.5}), routing, True, False) is False


def test_klima_og_cooling_takes_sink_out_of_heating_and_opens_well_loop():
    io_map = _io_map()
    app_config = _TestConfig(
        io_map,
        {
            "hydraulik": {"common_heat_demands": ["klima_og"]},
            "regelung": {"mischer_reserve_k": 5, "oelbrenner_unterstuetzung": True},
            "klima_og": {
                "kuehlung_enabled": True,
                "kuehlung_max_vl_soll_c": 25,
                "kuehlung_hysterese_k": 1,
            },
            "brunnen": {"fu_start_pct": 22},
        },
    )
    mqtt = type("Mqtt", (), {"demands": {"klima_og": Demand(True, 18.0)}})()
    freigaben = Freigaben(
        sources={"oelbrenner": True, "wp1": False, "wp2": False, "bwwp": False},
        sinks={"brauchwasser": False, "fbh_eg": False, "klima_og": True, "nebengeb": False, "hk_backup": False, "pool": False},
    )

    routing_state, _bw, _brunnen, auto_do, auto_ao, oelbrenner_common_active, cooling_active = _compute_auto_outputs(
        app_config,
        mqtt,
        HardwareSnapshot(rtd={"K-RTD03": 26.0, "RTD01": 20.0}),
        FailsafeState(False, (), None),
        freigaben,
        ReglerParameter.from_settings(app_config.settings),
        False,
        False,
        0.0,
        False,
        False,
    )

    assert cooling_active is True
    assert oelbrenner_common_active is False
    assert routing_state.common_demands == ()
    assert auto_do["DO01"] is False
    assert auto_do["DO06"] is True
    assert auto_do["K-DO02"] is True
    assert auto_do["K-DO04"] is True
    assert auto_ao["K-AO03"] == 0.0
    assert auto_ao["K-AO01"] == 22.0


def test_klima_og_cooling_is_disabled_by_default():
    io_map = _io_map()
    app_config = _TestConfig(
        io_map,
        {
            "hydraulik": {"common_heat_demands": ["klima_og"]},
            "regelung": {"mischer_reserve_k": 5, "oelbrenner_unterstuetzung": True},
        },
    )
    mqtt = type("Mqtt", (), {"demands": {"klima_og": Demand(True, 18.0)}})()
    freigaben = Freigaben(
        sources={"oelbrenner": True, "wp1": False, "wp2": False, "bwwp": False},
        sinks={"brauchwasser": False, "fbh_eg": False, "klima_og": True, "nebengeb": False, "hk_backup": False, "pool": False},
    )

    _routing_state, _bw, _brunnen, auto_do, _auto_ao, _burner, cooling_active = _compute_auto_outputs(
        app_config,
        mqtt,
        HardwareSnapshot(rtd={"K-RTD03": 26.0, "RTD01": 20.0}),
        FailsafeState(False, (), None),
        freigaben,
        ReglerParameter.from_settings(app_config.settings),
        False,
        False,
        0.0,
        False,
        False,
    )

    assert cooling_active is False
    assert auto_do["DO06"] is False
