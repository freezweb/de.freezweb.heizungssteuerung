from heizung.lib.mqtt_bridge import MqttBridge


class _Msg:
    def __init__(self, topic: str, payload: str) -> None:
        self.topic = topic
        self.payload = payload.encode()


def test_pv_flags_are_received_from_ha_mqtt():
    bridge = MqttBridge({"topics": {"base": "heizung"}})

    bridge._on_message(None, None, _Msg("heizung/pv/ueberschuss/set", "1"))
    bridge._on_message(None, None, _Msg("heizung/pv/mangel/set", "true"))
    bridge._on_message(None, None, _Msg("heizung/pv/mangel/set", "0"))

    assert bridge.pv == {"ueberschuss": True, "mangel": False}
