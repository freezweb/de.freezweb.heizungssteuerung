from pathlib import Path
from datetime import datetime

import pytest

from heizung.lib.config import AppConfig, ChannelConfig, IoMap
from heizung.lib.iohw import HardwareSnapshot
from heizung.lib.mqtt_bridge import MqttBridge
from heizung.lib.pool import PoolController, PoolProdinoConfig
from heizung.__main__ import _merge_prodino_pool_snapshot


def test_prodino_float_closed_means_pool_too_empty():
    app_config = _config()
    mqtt = MqttBridge({"topics": {"base": "heizung"}})
    mqtt.prodino_pool_inputs[1] = True
    config = PoolProdinoConfig(enabled=True, float_empty_high=True)

    snapshot = _merge_prodino_pool_snapshot(app_config, HardwareSnapshot(), mqtt, config)

    assert snapshot.di["P-DI01"] is True


def test_pool_valve_opens_after_test_delay_when_pool_empty():
    controller = PoolController(PoolProdinoConfig(enabled=True))

    state = controller.compute(
        now_ts=1000.0,
        float_empty=True,
        test_mode=True,
        fill_delay_s=30.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )
    assert state.valve_open is False
    assert state.pending is True

    state = controller.compute(
        now_ts=1030.1,
        float_empty=True,
        test_mode=True,
        fill_delay_s=30.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )

    assert state.valve_open is True
    assert state.filling is True


def test_fresh_water_requires_water_meter_delta_for_flockung_runtime():
    controller = PoolController(PoolProdinoConfig(enabled=True))
    controller.compute(
        now_ts=1000.0,
        float_empty=True,
        test_mode=True,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=0.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=1.0,
        pump_ml_min=60.0,
    )

    state = controller.compute(
        now_ts=1060.0,
        float_empty=False,
        test_mode=True,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=0.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=1.0,
        pump_ml_min=60.0,
    )

    assert state.valve_open is False
    assert state.dosing_pump_on is False
    assert state.last_fill_liters == 0.0


def test_fresh_water_uses_water_meter_delta_when_available():
    controller = PoolController(PoolProdinoConfig(enabled=True))
    controller.compute(
        now_ts=1000.0,
        float_empty=True,
        test_mode=True,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=0.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.1,
        pump_ml_min=133.33,
        water_meter_total_l=1000.0,
    )

    state = controller.compute(
        now_ts=1060.0,
        float_empty=False,
        test_mode=True,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=0.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.1,
        pump_ml_min=133.33,
        water_meter_total_l=1025.0,
    )

    assert state.dosing_pump_on is True
    assert state.last_fill_liters == 25.0
    assert state.last_dose_ml == 2.5
    assert state.last_dose_reason == "frischwasser"
    assert state.last_dose_ts == 1060.0


def test_daily_flockung_records_last_dose():
    controller = PoolController(PoolProdinoConfig(enabled=True))
    now_ts = 3600.0

    state = controller.compute(
        now_ts=now_ts,
        float_empty=False,
        test_mode=True,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=36.0,
        daily_dose_hour=datetime.fromtimestamp(now_ts).hour,
        fresh_ml_per_l=0.0,
        pump_ml_min=120.0,
    )

    assert state.dosing_pump_on is True
    assert state.last_dose_ml == 36.0
    assert state.last_dose_seconds == 18.0
    assert state.last_dose_reason == "tagesdosis"
    assert state.last_dose_ts == now_ts


def test_normal_pool_fill_starts_after_delay_inside_time_window():
    controller = PoolController(PoolProdinoConfig(enabled=True))
    start_ts = datetime(2026, 7, 12, 2, 0, 2).timestamp()

    state = controller.compute(
        now_ts=start_ts,
        float_empty=True,
        test_mode=False,
        fill_delay_s=30.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )

    assert state.reason == "verzoegerung"
    assert state.valve_open is False

    state = controller.compute(
        now_ts=start_ts + 31.0,
        float_empty=True,
        test_mode=False,
        fill_delay_s=30.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )

    assert state.reason == "fuellt"
    assert state.valve_open is True
    assert state.filling is True


def test_normal_pool_fill_can_start_later_in_time_window():
    controller = PoolController(PoolProdinoConfig(enabled=True))
    start_ts = datetime(2026, 7, 12, 7, 30, 0).timestamp()

    controller.compute(
        now_ts=start_ts,
        float_empty=True,
        test_mode=False,
        fill_delay_s=30.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )
    state = controller.compute(
        now_ts=start_ts + 31.0,
        float_empty=True,
        test_mode=False,
        fill_delay_s=30.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )

    assert state.reason == "fuellt"
    assert state.valve_open is True


def test_pool_fill_closes_only_after_stable_full_delay():
    controller = PoolController(PoolProdinoConfig(enabled=True))
    start_ts = datetime(2026, 7, 12, 2, 0, 0).timestamp()

    state = controller.compute(
        now_ts=start_ts,
        float_empty=True,
        test_mode=False,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )
    assert state.reason == "fuellt"
    assert state.valve_open is True

    state = controller.compute(
        now_ts=start_ts + 5.0,
        float_empty=False,
        test_mode=False,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )
    assert state.reason == "schliessverzoegerung"
    assert state.valve_open is True

    state = controller.compute(
        now_ts=start_ts + 6.0,
        float_empty=True,
        test_mode=False,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )
    assert state.reason == "fuellt"
    assert state.valve_open is True

    controller.compute(
        now_ts=start_ts + 7.0,
        float_empty=False,
        test_mode=False,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )
    state = controller.compute(
        now_ts=start_ts + 17.1,
        float_empty=False,
        test_mode=False,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )
    assert state.reason == "pool_voll"
    assert state.valve_open is False


def test_pool_can_fill_multiple_times_inside_time_window():
    controller = PoolController(PoolProdinoConfig(enabled=True))
    first_ts = datetime(2026, 7, 12, 2, 0, 0).timestamp()

    controller.compute(
        now_ts=first_ts,
        float_empty=True,
        test_mode=False,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=0.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )
    controller.compute(
        now_ts=first_ts + 30.0,
        float_empty=False,
        test_mode=False,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=0.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )

    second_ts = datetime(2026, 7, 12, 6, 30, 0).timestamp()
    state = controller.compute(
        now_ts=second_ts,
        float_empty=True,
        test_mode=False,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=0.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )

    assert state.reason == "fuellt"
    assert state.valve_open is True


def test_fresh_water_dose_waits_for_late_water_meter_update():
    controller = PoolController(PoolProdinoConfig(enabled=True))
    start_ts = datetime(2026, 7, 12, 2, 0, 0).timestamp()

    controller.compute(
        now_ts=start_ts,
        float_empty=True,
        test_mode=True,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=0.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.1,
        pump_ml_min=133.33,
        water_meter_total_l=1000.0,
    )
    state = controller.compute(
        now_ts=start_ts + 30.0,
        float_empty=False,
        test_mode=True,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=0.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.1,
        pump_ml_min=133.33,
        water_meter_total_l=1000.0,
    )
    assert state.reason == "warte_wasserzaehler"
    assert state.valve_open is False
    assert state.last_dose_reason == ""

    state = controller.compute(
        now_ts=start_ts + 60.0,
        float_empty=False,
        test_mode=True,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=0.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.1,
        pump_ml_min=133.33,
        water_meter_total_l=1012.0,
    )
    assert state.reason == "pool_voll"
    assert state.last_fill_liters == 12.0
    assert state.last_dose_ml == pytest.approx(1.2)
    assert state.last_dose_reason == "frischwasser"


def test_running_pool_fill_continues_after_time_window_end():
    controller = PoolController(PoolProdinoConfig(enabled=True))
    start_ts = datetime(2026, 7, 12, 7, 59, 50).timestamp()

    controller.compute(
        now_ts=start_ts,
        float_empty=True,
        test_mode=False,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )
    state = controller.compute(
        now_ts=start_ts + 20.0,
        float_empty=True,
        test_mode=False,
        fill_delay_s=0.0,
        start_hour=2,
        end_hour=8,
        close_delay_s=10.0,
        meter_settle_s=120.0,
        max_fill_s=3600.0,
        daily_dose_ml=0.0,
        daily_dose_hour=2,
        fresh_ml_per_l=0.0,
        pump_ml_min=60.0,
    )

    assert state.reason == "fuellt"
    assert state.valve_open is True


def _config() -> AppConfig:
    io_map = IoMap(
        revpi={},
        do={},
        di={"P-DI01": ChannelConfig("P-DI01", "di", "MQTT_Input_1", "pool_schwimmer_zu_leer")},
        ai={},
        ao={},
        rtd={},
    )
    return AppConfig(
        root_dir=Path("."),
        config_dir=Path("config"),
        io_map=io_map,
        settings={},
        mqtt={},
        modbus_map={},
    )
