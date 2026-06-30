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
        self.peer_last_seen_ts: float | None = None
        self.peer_online: bool | None = None
        self.demands: dict[str, Demand] = {}
        self.pv: dict[str, bool] = {"ueberschuss": False, "mangel": False}
        self._commands: queue.SimpleQueue[MqttCommand] = queue.SimpleQueue()
        self._client: Any = None
        self._last_published: dict[str, str] = {}

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
        self.publish(status_topic, "offline", retain=True, force=True)
        self._client.loop_stop()
        self._client.disconnect()

    def drain_commands(self) -> list[MqttCommand]:
        commands: list[MqttCommand] = []
        while True:
            try:
                commands.append(self._commands.get_nowait())
            except queue.Empty:
                return commands

    def publish(self, topic: str, payload: Any, retain: bool = False, force: bool = False) -> None:
        if self._client is None:
            return
        if not isinstance(payload, str):
            payload = json.dumps(payload, separators=(",", ":"))
        if not force and self._last_published.get(topic) == payload:
            return
        self._last_published[topic] = payload
        self._client.publish(topic, payload=payload, qos=0, retain=retain)

    def publish_json(self, topic: str, payload: dict[str, Any], retain: bool = False) -> None:
        self.publish(topic, payload, retain=retain)

    def publish_heartbeat(self, uptime_s: int) -> None:
        topic = self.config.get("topics", {}).get("heartbeat", f"{self.base}/heartbeat")
        self.publish(topic, str(uptime_s))

    def _peer_status_topic(self) -> str:
        leds = self.config.get("leds", {})
        if leds.get("peer_status_topic"):
            return str(leds["peer_status_topic"])
        broker = self.config.get("broker", {})
        status_topic, _heartbeat_topic = _default_peer_topics(self.base, str(broker.get("client_id", "")))
        return status_topic

    def _peer_heartbeat_topic(self) -> str:
        leds = self.config.get("leds", {})
        if leds.get("peer_heartbeat_topic"):
            return str(leds["peer_heartbeat_topic"])
        broker = self.config.get("broker", {})
        _status_topic, heartbeat_topic = _default_peer_topics(self.base, str(broker.get("client_id", "")))
        return heartbeat_topic

    def _peer_topics(self) -> tuple[str, str]:
        return self._peer_status_topic(), self._peer_heartbeat_topic()

    def set_default_demands(self, defaults: dict[str, Any]) -> None:
        for name, raw in defaults.items():
            if not isinstance(raw, dict):
                continue
            self.demands.setdefault(
                str(name),
                Demand(
                    aktiv=bool(raw.get("aktiv", False)),
                    vl_soll=float(raw["vl_soll"]) if raw.get("vl_soll") is not None else None,
                    quelle=str(raw.get("quelle", "default")),
                ),
            )

    def _on_connect(self, client: Any, _userdata: Any, _flags: Any, reason_code: Any, _properties: Any = None) -> None:
        if _reason_code_value(reason_code) != 0:
            log.warning("MQTT-Verbindung fehlgeschlagen: %s", reason_code)
            return
        self.connected = True
        self.last_seen_ts = time.time()
        status_topic = self.config.get("topics", {}).get("status", f"{self.base}/status")
        self.publish(status_topic, "online", retain=True, force=True)
        for topic in (
            f"{self.base}/anforderung/+/set",
            f"{self.base}/anforderung/+/aktiv/set",
            f"{self.base}/anforderung/+/vl_soll/set",
            f"{self.base}/freigabe/+/+/set",
            f"{self.base}/regler/+/set",
            f"{self.base}/pv/+/set",
            f"{self.base}/+/hand/set",
            f"{self.base}/+/hand/auto",
            f"{self.base}/tor/+/cmd",
            f"{self.base}/failsafe/force",
            f"{self.base}/ha/heartbeat",
            *self._peer_topics(),
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

        log.info("MQTT Kommando empfangen: %s payload=%r", topic, payload_raw)

        if topic == f"{self.base}/ha/heartbeat":
            self.last_ha_heartbeat_ts = time.time()
            return

        if topic in self._peer_topics():
            self.peer_last_seen_ts = time.time()
            if topic == self._peer_status_topic():
                self.peer_online = _as_bool(payload)
            return

        if len(parts) == 4 and parts[1] == "anforderung" and parts[3] == "set" and isinstance(payload, dict):
            self.demands[parts[2]] = Demand(
                aktiv=bool(payload.get("aktiv", False)),
                vl_soll=float(payload["vl_soll"]) if payload.get("vl_soll") is not None else None,
                quelle=str(payload.get("quelle", "ha")),
            )
            return

        if len(parts) == 5 and parts[1] == "anforderung" and parts[4] == "set":
            current = self.demands.get(parts[2], Demand(False, None))
            if parts[3] == "aktiv":
                self.demands[parts[2]] = Demand(
                    aktiv=_as_bool(payload),
                    vl_soll=current.vl_soll,
                    quelle="ha",
                )
                return
            if parts[3] == "vl_soll":
                self.demands[parts[2]] = Demand(
                    aktiv=current.aktiv,
                    vl_soll=float(str(payload).replace(",", ".")),
                    quelle="ha",
                )
                return

        if len(parts) == 5 and parts[1] == "freigabe" and parts[4] == "set":
            self._commands.put(MqttCommand("freigabe_set", f"{parts[2]}/{parts[3]}", payload))
            return

        if len(parts) == 4 and parts[1] == "regler" and parts[3] == "set":
            self._commands.put(MqttCommand("regler_set", parts[2], payload))
            return

        if len(parts) == 4 and parts[1] == "pv" and parts[3] == "set":
            if parts[2] in self.pv:
                self.pv[parts[2]] = _as_bool(payload)
            return

        if len(parts) == 4 and parts[2] == "hand" and parts[3] == "set":
            self._commands.put(MqttCommand("hand_set", parts[1], payload))
            return

        if len(parts) == 4 and parts[2] == "hand" and parts[3] == "auto":
            self._commands.put(MqttCommand("hand_auto", parts[1], payload))
            return

        if len(parts) == 4 and parts[1] == "tor" and parts[3] == "cmd":
            command_name = {
                "ganz": "oeffnen_ganz",
                "halb": "oeffnen_halb",
                "auf": "oeffnen_ganz",
                "zu": "schliessen",
            }.get(parts[2], parts[2])
            self._commands.put(MqttCommand("tor_command", command_name, payload))
            return

        if topic == f"{self.base}/failsafe/force":
            self._commands.put(MqttCommand("failsafe_force", "failsafe", payload))


def _reason_code_value(reason_code: Any) -> int:
    try:
        return int(reason_code)
    except (TypeError, ValueError):
        return int(getattr(reason_code, "value", 1))


def _as_bool(value: Any) -> bool:
    if isinstance(value, dict):
        for key in ("aktiv", "enabled", "state", "value"):
            if key in value:
                return _as_bool(value[key])
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "on", "online", "yes", "ja", "ein"}
    return bool(value)


def _default_peer_topics(base: str, client_id: str) -> tuple[str, str]:
    if "keller" in client_id.lower():
        return f"{base}/status", f"{base}/heartbeat"
    return f"{base}/keller/status", f"{base}/keller/heartbeat"
