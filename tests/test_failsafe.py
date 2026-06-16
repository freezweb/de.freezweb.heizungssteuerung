from heizung.lib.failsafe import FailsafeMonitor, HeatingCurve


def test_heating_curve_interpolates_and_clamps():
    curve = HeatingCurve(points=((-12.0, 45.0), (0.0, 38.0), (15.0, 25.0)), vl_min=25.0, vl_max=55.0)

    assert curve.target_flow(-20.0) == 45.0
    assert round(curve.target_flow(-6.0), 2) == 41.5
    assert curve.target_flow(20.0) == 25.0


def test_failsafe_detects_missing_heartbeat_and_uses_curve():
    monitor = FailsafeMonitor(
        HeatingCurve(points=((-12.0, 45.0), (0.0, 38.0), (15.0, 25.0)), vl_min=25.0, vl_max=55.0),
        mqtt_timeout_s=60.0,
        ha_heartbeat_timeout_s=300.0,
        fallback_vl_without_outside_sensor=50.0,
    )

    state = monitor.evaluate(
        now_ts=1_000.0,
        mqtt_connected=True,
        last_mqtt_seen_ts=990.0,
        last_ha_heartbeat_ts=None,
        outside_temp_c=0.0,
    )

    assert state.active is True
    assert state.reasons == ("ha_heartbeat_missing",)
    assert state.vl_soll == 38.0


def test_failsafe_uses_fallback_when_outside_sensor_invalid():
    monitor = FailsafeMonitor(
        HeatingCurve(points=((-12.0, 45.0), (0.0, 38.0), (15.0, 25.0)), vl_min=25.0, vl_max=55.0),
        mqtt_timeout_s=60.0,
        ha_heartbeat_timeout_s=300.0,
        fallback_vl_without_outside_sensor=50.0,
    )

    state = monitor.evaluate(
        now_ts=1_000.0,
        mqtt_connected=True,
        last_mqtt_seen_ts=999.0,
        last_ha_heartbeat_ts=999.0,
        outside_temp_c=None,
    )

    assert state.active is True
    assert "outside_sensor_loss" in state.reasons
    assert state.vl_soll == 50.0

