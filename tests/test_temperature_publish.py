from heizung.__main__ import _publish_temperature, _sensor_value_by_component
from heizung.lib.config import ChannelConfig, IoMap
from heizung.lib.iohw import HardwareSnapshot


class FakeMqtt:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, bool]] = []

    def publish(self, topic: str, payload: str, retain: bool = False) -> None:
        self.messages.append((topic, payload, retain))


def test_missing_850_degree_temperature_is_published_as_empty_retained_state():
    mqtt = FakeMqtt()

    _publish_temperature(mqtt, "heizung/temp/fbh_eg_rl/state", 850.0)

    assert mqtt.messages == [
        ("heizung/temp/fbh_eg_rl/availability", "offline", True),
        ("heizung/temp/fbh_eg_rl/state", "", True),
    ]


def test_plausible_temperature_is_published_normally():
    mqtt = FakeMqtt()

    _publish_temperature(mqtt, "heizung/temp/fbh_eg_rl/state", 26.42)

    assert mqtt.messages == [
        ("heizung/temp/fbh_eg_rl/availability", "online", True),
        ("heizung/temp/fbh_eg_rl/state", "26.4", True),
    ]


def test_sensor_value_by_component_ignores_missing_850_degree_rtd():
    io_map = IoMap(
        revpi={},
        do={},
        di={},
        ai={},
        ao={},
        rtd={"K-RTD02": ChannelConfig("K-RTD02", "rtd", "RTD_2", "fbh_eg_rl")},
    )
    app_config = type("Config", (), {"io_map": io_map})()

    assert _sensor_value_by_component(app_config, HardwareSnapshot(rtd={"K-RTD02": 850.0}), "fbh_eg_rl") is None
