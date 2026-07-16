from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "pylib"))
import websocket


def _token() -> str:
    path = Path(os.environ["APPDATA"]) / "Code" / "User" / "mcp.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["servers"]["HomeAssistant"]["headers"]["Authorization"].removeprefix("Bearer ").strip()


def _request(ws, message: dict) -> dict:
    ws.send(json.dumps(message, ensure_ascii=False))
    while True:
        response = json.loads(ws.recv())
        if response.get("id") == message["id"]:
            if not response.get("success"):
                raise RuntimeError(response.get("error", "unknown Home Assistant error"))
            return response["result"]


def main() -> None:
    ws = websocket.create_connection("ws://10.1.20.2:8123/api/websocket", timeout=15)
    try:
        assert json.loads(ws.recv())["type"] == "auth_required"
        ws.send(json.dumps({"type": "auth", "access_token": _token()}))
        auth = json.loads(ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"Home Assistant WebSocket auth failed: {auth!r}")

        prefs = _request(ws, {"id": 1, "type": "energy/get_prefs"})
        backup = Path("tmp") / "ha-energy-prefs-before-oel-current-fix.json"
        backup.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")

        gas_sources = [source for source in prefs["energy_sources"] if source.get("type") == "gas"]
        if not gas_sources:
            prefs["energy_sources"].append({"type": "gas"})
            gas_sources = [prefs["energy_sources"][-1]]

        gas = gas_sources[0]
        gas.update(
            {
                "stat_energy_from": "sensor.heizung_hauptsteuerung_oelverbrauch_liter",
                "stat_cost": None,
                "entity_energy_price": "sensor.heizung_hauptsteuerung_oelpreis_diesel_wez",
                "number_energy_price": None,
                "stat_rate": "sensor.heizung_hauptsteuerung_oelverbrauch_aktuell",
            }
        )

        for stale in gas_sources[1:]:
            prefs["energy_sources"].remove(stale)

        _request(ws, {"id": 2, "type": "energy/save_prefs", **prefs})
        verify = _request(ws, {"id": 3, "type": "energy/get_prefs"})
        print(json.dumps([s for s in verify["energy_sources"] if s.get("type") == "gas"], ensure_ascii=False, indent=2))
    finally:
        ws.close()


if __name__ == "__main__":
    main()
