from heizung.__main__ import _brunnen_flow_runtime
from heizung.lib.config import AppConfig, IoMap
from heizung.lib.regler import ReglerParameter


def _config() -> AppConfig:
    return AppConfig(
        root_dir=None,
        config_dir=None,
        io_map=IoMap(revpi={}, do={}, di={}, ai={}, ao={}, rtd={}),
        settings={"brunnen": {"flow_stale_timeout_s": 15}},
        mqtt={},
        modbus_map={},
    )


def test_no_flow_timer_is_reset_while_pump_is_off():
    regler = ReglerParameter.from_settings({})

    flow, no_flow_s, since = _brunnen_flow_runtime(
        _config(),
        regler,
        flow_l_min=0.0,
        flow_last_seen_ts=100.0,
        no_flow_since_ts=10.0,
        pump_active=False,
        timer_armed=True,
        now_ts=101.0,
    )

    assert flow == 0.0
    assert no_flow_s is None
    assert since is None


def test_no_flow_timer_counts_only_while_pump_is_active():
    regler = ReglerParameter.from_settings({})

    flow, no_flow_s, since = _brunnen_flow_runtime(
        _config(),
        regler,
        flow_l_min=0.0,
        flow_last_seen_ts=100.0,
        no_flow_since_ts=None,
        pump_active=True,
        timer_armed=True,
        now_ts=101.0,
    )

    assert flow == 0.0
    assert no_flow_s == 0.0
    assert since == 101.0


def test_no_flow_timer_is_reset_below_regeldruck_window():
    regler = ReglerParameter.from_settings({})

    flow, no_flow_s, since = _brunnen_flow_runtime(
        _config(),
        regler,
        flow_l_min=0.0,
        flow_last_seen_ts=100.0,
        no_flow_since_ts=10.0,
        pump_active=True,
        timer_armed=False,
        now_ts=101.0,
    )

    assert flow == 0.0
    assert no_flow_s is None
    assert since is None
