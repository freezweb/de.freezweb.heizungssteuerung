from heizung.lib.mqtt_bridge import MqttBridge


class _Msg:
    def __init__(self, topic: str, payload: str) -> None:
        self.topic = topic
        self.payload = payload.encode()


class _Client:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, topic: str, payload: str, qos: int, retain: bool) -> None:
        self.messages.append((topic, payload, qos, retain))


def test_pv_flags_are_received_from_ha_mqtt():
    bridge = MqttBridge({"topics": {"base": "heizung"}})

    bridge._on_message(None, None, _Msg("heizung/pv/ueberschuss/set", "1"))
    bridge._on_message(None, None, _Msg("heizung/pv/mangel/set", "true"))
    bridge._on_message(None, None, _Msg("heizung/pv/mangel/set", "0"))

    assert bridge.pv == {"ueberschuss": True, "mangel": False}


def test_publish_skips_unchanged_payloads():
    bridge = MqttBridge({"topics": {"base": "heizung"}})
    client = _Client()
    bridge._client = client

    bridge.publish("heizung/temp/aussen/state", "20.0", retain=True)
    bridge.publish("heizung/temp/aussen/state", "20.0", retain=True)
    bridge.publish("heizung/temp/aussen/state", "20.1", retain=True)

    assert client.messages == [
        ("heizung/temp/aussen/state", "20.0", 0, True),
        ("heizung/temp/aussen/state", "20.1", 0, True),
    ]


def test_publish_force_resends_same_payload():
    bridge = MqttBridge({"topics": {"base": "heizung"}})
    client = _Client()
    bridge._client = client

    bridge.publish("heizung/status", "online", retain=True)
    bridge.publish("heizung/status", "online", retain=True, force=True)

    assert client.messages == [
        ("heizung/status", "online", 0, True),
        ("heizung/status", "online", 0, True),
    ]
