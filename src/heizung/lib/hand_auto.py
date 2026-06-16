"""Hand/Auto-Override pro Ausgangskanal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import ChannelConfig, IoMap
from .state import StateStore


@dataclass
class HandState:
    hand: bool = False
    wert: Any = None
    seit_ts: float | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "HandState":
        return cls(
            hand=bool(raw.get("hand", False)),
            wert=raw.get("wert"),
            seit_ts=raw.get("seit_ts"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"hand": self.hand, "wert": self.wert, "seit_ts": self.seit_ts}


class HandAutoManager:
    def __init__(
        self,
        io_map: IoMap,
        store: StateStore,
        default_timeout_min: int | None = None,
    ) -> None:
        self.io_map = io_map
        self.store = store
        self.default_timeout_min = default_timeout_min
        self.states: dict[str, HandState] = {
            channel_id: HandState.from_dict(raw)
            for channel_id, raw in store.load().items()
            if isinstance(raw, dict)
        }

    def set_hand(self, channel_id: str, wert: Any, now_ts: float) -> None:
        self._require_output(channel_id)
        self.states[channel_id] = HandState(hand=True, wert=wert, seit_ts=now_ts)
        self.save()

    def set_auto(self, channel_id: str) -> None:
        self._require_output(channel_id)
        self.states[channel_id] = HandState(hand=False, wert=None, seit_ts=None)
        self.save()

    def apply(self, channel: ChannelConfig, auto_wert: Any, now_ts: float) -> tuple[Any, bool]:
        state = self.states.get(channel.id, HandState())
        if not state.hand:
            return auto_wert, False

        if self._is_expired(channel, state, now_ts):
            self.states[channel.id] = HandState()
            self.save()
            return auto_wert, False

        return state.wert, True

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            channel_id: state.to_dict()
            for channel_id, state in self.states.items()
            if state.hand
        }

    def save(self) -> None:
        self.store.save({channel_id: state.to_dict() for channel_id, state in self.states.items()})

    def _is_expired(self, channel: ChannelConfig, state: HandState, now_ts: float) -> bool:
        timeout_min = channel.hand_timeout_min
        if timeout_min is None:
            timeout_min = self.default_timeout_min
        if timeout_min is None or state.seit_ts is None:
            return False
        return now_ts - state.seit_ts >= timeout_min * 60

    def _require_output(self, channel_id: str) -> None:
        if channel_id not in self.io_map.output_channels:
            raise KeyError(f"Kein Ausgangskanal: {channel_id}")

