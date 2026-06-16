"""MQTT-Kopplung zu Home Assistant."""

from __future__ import annotations

import json
import logging
import queue
import time
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MqttCommand:
    typ: str
    name: str
    payload: Any = None


@dataclass(frozen=True)
class Demand:
    aktiv: bool
    vl_soll: float | None
    quelle: str = "ha"


class MqttBridge:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.base = config.get("topics", {}).get("base", "heizung").strip("/")
        self.connected = False
        self.last_seen_ts: float | None = None
        self.last_ha_heartbeat_ts: float | None = None
        self.demands: dict[str, Demand] = {}
        self._commands: queue.SimpleQueue[MqttCommand] = queue.SimpleQueue()
        self._client: Any = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def start(self) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            log.warning("paho-mqtt ist nicht installiert, MQTT bleibt deaktiviert")
            return

        broker = self.config.get("broker", {})
        client_id = broker.get("client_id", "heizung-haupt")
        try:
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        except AttributeError:  # pragma: no cover - paho < 2
            self._client = mqtt.Client(client_id=client_id)

        if broker.get("user"):
            self._client.username_pw_set(broker.get("user"), broker.get("passwort"))

        status_topic = self.config.get("topics", {}).get("status", f"{self.base}/status")
        self._client.will_set(status_topic, payload="offline", qos=1, retain=True)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self._client.connect_async(
            broker.get("host", "localhost"),
            int(broker.get("port", 1883)),
            int(broker.get("keepalive_s", 30)),
        )
        self._client.loop_start()

    def stop(self) -> None:
        if self._client is None:
            return
        status_topic = self.config.get("topics", {}).get("status", f"{self.base}/status")
        self.publish(status_topic, "offline", retain=True)
        self._client.loop_stop()
        self._client.disconnect()

    def drain_commands(self) -> list[MqttCommand]:
        commands: list[MqttCommand] = []
        while True:
            try:
                commands.append(self._commands.get_nowait())
            except queue.Empty:
                return commands

    def publish(self, topic: str, payload: Any, retain: bool = False) -> None:
        if self._client is None:
            return
        if not isinstance(payload, str):
            payload = json.dumps(payload, separators=(",", ":"))
        self._client.publish(topic, payload=payload, qos=0, retain=retain)

    def publish_json(self, topic: str, payload: dict[str, Any], retain: bool = False) -> None:
        self.publish(topic, payload, retain=retain)

    def publish_heartbeat(self, uptime_s: int) -> None:
        topic = self.config.get("topics", {}).get("heartbeat", f"{self.base}/heartbeat")
        self.publish(topic, str(uptime_s))

    def _on_connect(self, client: Any, _userdata: Any, _flags: Any, reason_code: Any, _properties: Any = None) -> None:
        if _reason_code_value(reason_code) != 0:
            log.warning("MQTT-Verbindung fehlgeschlagen: %s", reason_code)
            return
        self.connected = True
        self.last_seen_ts = time.time()
        status_topic = self.config.get("topics", {}).get("status", f"{self.base}/status")
        self.publish(status_topic, "online", retain=True)
        for topic in (
            f"{self.base}/anforderung/+/set",
            f"{self.base}/+/hand/set",
            f"{self.base}/+/hand/auto",
            f"{self.base}/tor/+/cmd",
            f"{self.base}/failsafe/force",
            f"{self.base}/ha/heartbeat",
        ):
            client.subscribe(topic)
        log.info("MQTT verbunden")

    def _on_disconnect(self, _client: Any, _userdata: Any, *args: Any) -> None:
        self.connected = False
        log.warning("MQTT getrennt: %s", args[0] if args else "unbekannt")

    def _on_message(self, _client: Any, _userdata: Any, msg: Any) -> None:
        self.last_seen_ts = time.time()
        topic = msg.topic
        payload_raw = msg.payload.decode("utf-8", errors="replace")
        parts = topic.split("/")
        try:
            payload = json.loads(payload_raw) if payload_raw else {}
        except json.JSONDecodeError:
            payload = payload_raw

        if topic == f"{self.base}/ha/heartbeat":
            self.last_ha_heartbeat_ts = time.time()
            return

        if len(parts) == 4 and parts[1] == "anforderung" and parts[3] == "set" and isinstance(payload, dict):
            self.demands[parts[2]] = Demand(
                aktiv=bool(payload.get("aktiv", False)),
                vl_soll=float(payload["vl_soll"]) if payload.get("vl_soll") is not None else None,
                quelle=str(payload.get("quelle", "ha")),
            )
            return

        if len(parts) == 4 and parts[2] == "hand" and parts[3] == "set":
            self._commands.put(MqttCommand("hand_set", parts[1], payload))
            return

        if len(parts) == 4 and parts[2] == "hand" and parts[3] == "auto":
            self._commands.put(MqttCommand("hand_auto", parts[1], payload))
            return

        if len(parts) == 4 and parts[1] == "tor" and parts[3] == "cmd":
            self._commands.put(MqttCommand("pulse", f"tor_{parts[2]}", payload))
            return

        if topic == f"{self.base}/failsafe/force":
            self._commands.put(MqttCommand("failsafe_force", "failsafe", payload))


def _reason_code_value(reason_code: Any) -> int:
    try:
        return int(reason_code)
    except (TypeError, ValueError):
        return int(getattr(reason_code, "value", 1))
