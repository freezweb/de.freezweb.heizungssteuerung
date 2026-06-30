from heizung.__main__ import _publish_freigaben_state
from heizung.lib.freigaben import Freigaben


class FakeMqtt:
    base = "heizung"

    def __init__(self) -> None:
        self.messages: list[tuple[str, object, bool]] = []

    def publish(self, topic: str, payload: str, retain: bool = False) -> None:
        self.messages.append((topic, payload, retain))

    def publish_json(self, topic: str, payload: dict, retain: bool = False) -> None:
        self.messages.append((topic, payload, retain))


def test_publish_freigaben_state_confirms_switch_states_immediately():
    mqtt = FakeMqtt()
    freigaben = Freigaben(
        sources={"oelbrenner": True, "wp1": False},
        sinks={"fbh_eg": True, "pool": False},
    )

    _publish_freigaben_state(mqtt, freigaben)

    assert ("heizung/freigabe/state", freigaben.snapshot(), True) in mqtt.messages
    assert ("heizung/freigabe/quellen/oelbrenner/state", "1", True) in mqtt.messages
    assert ("heizung/freigabe/quellen/wp1/state", "0", True) in mqtt.messages
    assert ("heizung/freigabe/senken/fbh_eg/state", "1", True) in mqtt.messages
    assert ("heizung/freigabe/senken/pool/state", "0", True) in mqtt.messages
