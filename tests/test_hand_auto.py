from pathlib import Path

from heizung.lib.config import ChannelConfig, IoMap
from heizung.lib.hand_auto import HandAutoManager
from heizung.lib.state import StateStore


def _io_map() -> IoMap:
    return IoMap(
        revpi={},
        do={
            "DO01": ChannelConfig(
                id="DO01",
                kind="do",
                pictory_name="O_01",
                komponente="brenner",
                hand_timeout_min=1,
            )
        },
        di={},
        ai={},
        ao={},
    )


def test_hand_value_overrides_auto_until_explicit_auto(tmp_path: Path):
    manager = HandAutoManager(_io_map(), StateStore(tmp_path / "hand.json"))
    channel = manager.io_map.do["DO01"]

    manager.set_hand("DO01", True, now_ts=100.0)

    assert manager.apply(channel, False, now_ts=120.0) == (True, True)
    assert manager.apply(channel, False, now_ts=10_000.0) == (True, True)

    manager.set_auto("DO01")

    assert manager.apply(channel, False, now_ts=10_001.0) == (False, False)


def test_hand_state_persists(tmp_path: Path):
    store = StateStore(tmp_path / "hand.json")
    manager = HandAutoManager(_io_map(), store)
    manager.set_hand("DO01", True, now_ts=100.0)

    reloaded = HandAutoManager(_io_map(), store)

    assert reloaded.snapshot()["DO01"]["wert"] is True
