from heizung.__main__ import _controller_role, _freshness_led_color, _heartbeat_led_color, _peer_led_color, _update_cpu_leds
from heizung.lib.config import AppConfig, IoMap
from heizung.lib.failsafe import FailsafeState
from heizung.lib.iohw import SimulatedIO
from heizung.lib.mqtt_bridge import MqttBridge


def _app(client_id: str, hostname: str) -> AppConfig:
    return AppConfig(
        root_dir=None,  # type: ignore[arg-type]
        config_dir=None,  # type: ignore[arg-type]
        io_map=IoMap(revpi={"hostname": hostname}, do={}, di={}, ai={}, ao={}),
        settings={
            "failsafe": {"ha_heartbeat_timeout_s": 300, "ha_heartbeat_required": True},
            "leds": {"peer_timeout_s": 90},
        },
        mqtt={"broker": {"client_id": client_id}, "topics": {"base": "heizung"}},
        modbus_map={},
    )


def test_controller_role_detects_keller_from_client_id():
    assert _controller_role(_app("heizung-keller", "RevPi107293")) == "keller"


def test_peer_led_color_uses_recent_peer_heartbeat():
    mqtt = MqttBridge({"broker": {"client_id": "heizung-haupt"}, "topics": {"base": "heizung"}})
    mqtt.peer_last_seen_ts = 100.0
    mqtt.peer_online = True

    assert _peer_led_color(mqtt, now_ts=120.0, boot_ts=0.0, timeout_s=90.0) == "green"
    assert _peer_led_color(mqtt, now_ts=250.0, boot_ts=0.0, timeout_s=90.0) == "red"


def test_freshness_led_color_allows_optional_missing_heartbeat():
    assert _freshness_led_color(None, now_ts=120.0, timeout_s=60.0, required=False) == "yellow"
    assert _freshness_led_color(None, now_ts=120.0, timeout_s=60.0, required=True) == "red"


def test_heartbeat_led_color_is_time_based_not_cycle_based():
    assert _heartbeat_led_color(now_ts=0.1, boot_ts=0.0, interval_s=1.0) == "yellow"
    assert _heartbeat_led_color(now_ts=1.1, boot_ts=0.0, interval_s=1.0) == "blue"
    assert _heartbeat_led_color(now_ts=2.1, boot_ts=0.0, interval_s=1.0) == "yellow"


async def test_update_cpu_leds_main_uses_all_status_leds():
    app = _app("heizung-haupt", "RevPi107273")
    io = SimulatedIO(app.io_map)
    mqtt = MqttBridge(app.mqtt)
    mqtt.connected = True
    mqtt.peer_last_seen_ts = 100.0
    mqtt.peer_online = True
    mqtt.last_ha_heartbeat_ts = 100.0

    await _update_cpu_leds(
        io,
        app,
        mqtt,
        FailsafeState(active=False, reasons=(), vl_soll=None),
        now_ts=110.0,
        boot_ts=0.0,
        cycle_count=1,
    )

    assert io.cpu_leds == {"A1": "yellow", "A2": "green", "A3": "green", "A4": "green", "A5": "green"}


async def test_update_cpu_leds_keller_clears_unused_leds():
    app = _app("heizung-keller", "RevPi107293")
    io = SimulatedIO(app.io_map)
    mqtt = MqttBridge(app.mqtt)

    await _update_cpu_leds(
        io,
        app,
        mqtt,
        FailsafeState(active=False, reasons=(), vl_soll=None),
        now_ts=10.0,
        boot_ts=0.0,
        cycle_count=2,
    )

    assert io.cpu_leds == {"A1": "yellow", "A2": "yellow", "A3": "off", "A4": "off", "A5": "off"}
