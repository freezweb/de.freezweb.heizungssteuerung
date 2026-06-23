from heizung.lib.brunnen import compute_brunnen_pressure
from heizung.lib.config import AppConfig, ChannelConfig, IoMap
from heizung.lib.iohw import HardwareSnapshot
from heizung.lib.regler import ReglerParameter


def _config(settings=None):
    return AppConfig(
        root_dir=None,
        config_dir=None,
        io_map=IoMap(
            revpi={},
            do={},
            di={},
            ai={"AI01": ChannelConfig("AI01", "ai", "AI", "brunnen_druck", einheit="bar")},
            ao={},
            rtd={},
        ),
        settings=settings
        or {
            "brunnen": {
                "druck_sensor_signal": "bar",
                "min_druck_bar": 2.2,
                "max_druck_bar": 4.2,
                "regeldruck_bar": 3.2,
                "fu_min_pct": 0,
                "fu_max_pct": 100,
                "fu_start_pct": 45,
                "kp_pct_pro_bar": 20,
                "fu_ramp_up_pct_s": 35,
                "fu_ramp_down_pct_s": 60,
            }
        },
        mqtt={},
        modbus_map={},
    )


def _snapshot(pressure_bar):
    return HardwareSnapshot(ai={"AI01": pressure_bar})


def test_brunnen_starts_below_min_pressure():
    regler = ReglerParameter.from_settings(_config().settings)

    state = compute_brunnen_pressure(_config(), _snapshot(2.0), regler, False, 0.0)

    assert state.active is True
    assert state.reason == "minderdruck_start"
    assert state.speed_pct == 35.0


def test_brunnen_ramps_up_instead_of_jumping_to_full_speed():
    regler = ReglerParameter.from_settings(_config().settings)

    first = compute_brunnen_pressure(_config(), _snapshot(0.0), regler, False, 0.0)
    second = compute_brunnen_pressure(_config(), _snapshot(0.0), regler, True, first.speed_pct)
    third = compute_brunnen_pressure(_config(), _snapshot(0.0), regler, True, second.speed_pct)

    assert first.speed_pct == 35.0
    assert second.speed_pct == 70.0
    assert third.speed_pct == 100.0


def test_brunnen_100ms_cycle_reaches_full_speed_after_about_three_seconds():
    regler = ReglerParameter.from_settings(_config().settings)
    active = False
    speed = 0.0

    for _ in range(29):
        state = compute_brunnen_pressure(_config(), _snapshot(0.0), regler, active, speed, cycle_s=0.1)
        active = state.active
        speed = state.speed_pct

    assert 98.0 <= speed <= 100.0


def test_brunnen_stops_at_max_pressure():
    regler = ReglerParameter.from_settings(_config().settings)

    state = compute_brunnen_pressure(_config(), _snapshot(4.3), regler, True, 35.0)

    assert state.active is False
    assert state.speed_pct == 0.0
    assert state.reason == "maxdruck_erreicht"


def test_brunnen_regulates_speed_around_setpoint():
    regler = ReglerParameter.from_settings(_config().settings)

    low = compute_brunnen_pressure(_config(), _snapshot(2.8), regler, True, 45.0)
    high = compute_brunnen_pressure(_config(), _snapshot(3.6), regler, True, 45.0)

    assert low.speed_pct > 45.0
    assert high.speed_pct < 45.0


def test_brunnen_scales_4_20ma_pressure_sensor():
    config = _config({"brunnen": {"druck_sensor_signal": "4-20ma", "min_druck_bar": 2.2, "max_druck_bar": 4.2, "regeldruck_bar": 3.2}})
    regler = ReglerParameter.from_settings(config.settings)

    state = compute_brunnen_pressure(config, _snapshot(12.0), regler, False, 0.0)

    assert state.pressure_bar == 5.0
    assert state.active is False


def test_brunnen_accepts_slightly_low_zero_bar_current():
    config = _config({"brunnen": {"druck_sensor_signal": "4-20ma", "min_druck_bar": 2.2, "max_druck_bar": 4.2, "regeldruck_bar": 3.2}})
    regler = ReglerParameter.from_settings(config.settings)

    state = compute_brunnen_pressure(config, _snapshot(3.95), regler, False, 0.0)

    assert state.pressure_bar == 0.0
    assert state.reason == "minderdruck_start"


def test_brunnen_treats_zero_current_as_sensor_fault_for_4_20ma():
    config = _config({"brunnen": {"druck_sensor_signal": "4-20ma", "min_druck_bar": 2.2, "max_druck_bar": 4.2, "regeldruck_bar": 3.2}})
    regler = ReglerParameter.from_settings(config.settings)

    state = compute_brunnen_pressure(config, _snapshot(0.0), regler, False, 0.0)

    assert state.active is False
    assert state.speed_pct == 0.0
    assert state.reason == "sensor_unplausibel"
