"""Small token-safe Home Assistant WebSocket helper for live Lovelace work."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pylib"))
import websocket


def token() -> str:
    path = os.path.join(os.environ["APPDATA"], "Code", "User", "mcp.json")
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)["servers"]["HomeAssistant"]["headers"]["Authorization"]
    return value.removeprefix("Bearer ").strip()


def connect():
    ws = websocket.create_connection("ws://10.1.20.2:8123/api/websocket", timeout=15)
    assert json.loads(ws.recv())["type"] == "auth_required"
    ws.send(json.dumps({"type": "auth", "access_token": token()}))
    auth = json.loads(ws.recv())
    if auth.get("type") != "auth_ok":
        raise RuntimeError(f"Home Assistant WebSocket auth failed: {auth.get('type')}")
    return ws


def request(ws, message: dict) -> dict:
    ws.send(json.dumps(message, ensure_ascii=False))
    while True:
        response = json.loads(ws.recv())
        if response.get("id") == message["id"]:
            if not response.get("success"):
                raise RuntimeError(response.get("error", "unknown Home Assistant error"))
            return response["result"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("inspect", "install", "verify"))
    args = parser.parse_args()
    ws = connect()
    try:
        config = request(ws, {"id": 1, "type": "lovelace/config", "url_path": "dashboard-og"})
        target = next(
            view
            for view in config.get("views", [])
            if view.get("path") == "haustechnik" or view.get("title", "").lower() == "haustechnik"
        )
        if args.mode == "inspect":
            print(json.dumps(target, ensure_ascii=False, indent=2))
            return

        marker = "hoftor_status_und_kameraauswertung"
        card = {
            "type": "vertical-stack",
            "cards": [
                {
                    "type": "picture-entity",
                    "entity": "camera.g3_bullet_high_resolution_channel_4",
                    "name": "Hoftor - Livebild",
                    "camera_view": "live",
                    "show_state": False,
                    "show_name": True,
                },
                {
                    "type": "entities",
                    "title": "Hoftor - Zustand und lokale Bildauswertung",
                    "show_header_toggle": False,
                    "entities": [
                        {"entity": "sensor.heizung_hauptsteuerung_tor_status", "name": "Virtueller Torzustand"},
                        {"entity": "sensor.hoftor_kameraauswertung_hoftor_kamera_position", "name": "Letzte bestätigte Kameraposition"},
                        {"entity": "sensor.hoftor_kameraauswertung_hoftor_kamera_auswertungsgrund", "name": "Auswertung"},
                        {"entity": "sensor.hoftor_kameraauswertung_hoftor_kamera_abstand_offen", "name": "Abstand Referenz offen"},
                        {"entity": "sensor.hoftor_kameraauswertung_hoftor_kamera_abstand_geschlossen", "name": "Abstand Referenz geschlossen"},
                        {"entity": "sensor.hoftor_kameraauswertung_hoftor_kamera_referenzabstand", "name": "Trennung der Referenzbilder"},
                        {"entity": "sensor.hoftor_kameraauswertung_hoftor_kamera_ausgewertete_bilder", "name": "Ausgewertete Bilder"},
                        {"entity": "sensor.hoftor_kameraauswertung_hoftor_kamera_verworfene_bilder", "name": "Verworfene Bilder"},
                        {"entity": "sensor.hoftor_kameraauswertung_hoftor_kamera_letzte_pruefung", "name": "Letzte lokale Prüfung"},
                        {"entity": "binary_sensor.g3_bullet_bewegung_4", "name": "Bewegung im Kamerabild"},
                        {"entity": "binary_sensor.hoftor_kameraauswertung_hoftor_schliesswunsch_ausstehend", "name": "Schließen vorgemerkt"},
                        {"entity": "binary_sensor.g3_bullet_ist_dunkel_4", "name": "Kamerabild dunkel"},
                    ],
                },
                {
                    "type": "horizontal-stack",
                    "cards": [
                        {
                            "type": "button",
                            "entity": "button.heizung_hauptsteuerung_tor_oeffnen_ganz",
                            "name": "Ganz öffnen",
                            "icon": "mdi:gate-open",
                            "show_state": False,
                            "tap_action": {
                                "action": "perform-action",
                                "perform_action": "button.press",
                                "target": {"entity_id": "button.heizung_hauptsteuerung_tor_oeffnen_ganz"},
                                "confirmation": {"text": "Hoftor ganz öffnen? Die Kamera prüft vorher die Position."},
                            },
                            "hold_action": {"action": "more-info"},
                        },
                        {
                            "type": "button",
                            "entity": "button.heizung_hauptsteuerung_tor_schliessen",
                            "name": "Schließen",
                            "icon": "mdi:gate",
                            "show_state": False,
                            "tap_action": {
                                "action": "perform-action",
                                "perform_action": "button.press",
                                "target": {"entity_id": "button.heizung_hauptsteuerung_tor_schliessen"},
                                "confirmation": {"text": "Hoftor schließen? Die Kamera prüft vorher die Position."},
                            },
                            "hold_action": {"action": "more-info"},
                        },
                    ],
                },
            ],
        }
        sections = target.get("sections")
        if sections is not None:
            section = {
                "type": "grid",
                "_freezweb_marker": marker,
                "cards": [
                    {"type": "heading", "heading": "Hoftor", "heading_style": "title"},
                    card,
                ],
            }
            existing = next((index for index, item in enumerate(sections) if item.get("_freezweb_marker") == marker), None)
            if existing is None:
                sections.insert(0, section)
            else:
                sections[existing] = section
        else:
            cards = target.setdefault("cards", [])
            card["_freezweb_marker"] = marker
            existing = next((index for index, item in enumerate(cards) if item.get("_freezweb_marker") == marker), None)
            if existing is None:
                cards.insert(0, card)
            else:
                cards[existing] = card

        if args.mode == "install":
            request(
                ws,
                {
                    "id": 2,
                    "type": "lovelace/config/save",
                    "url_path": "dashboard-og",
                    "config": config,
                },
            )
            config = request(ws, {"id": 3, "type": "lovelace/config", "url_path": "dashboard-og"})
            target = next(view for view in config["views"] if view.get("path") == "haustechnik")
            sections = target.get("sections")

        installed = (
            [item for item in sections if item.get("_freezweb_marker") == marker]
            if sections is not None
            else [item for item in target.get("cards", []) if item.get("_freezweb_marker") == marker]
        )
        print(json.dumps({"view": target.get("path"), "installed_cards": len(installed), "section_count": len(target.get("sections", []))}, ensure_ascii=False))
    finally:
        ws.close()


if __name__ == "__main__":
    main()
