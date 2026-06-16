# MQTT-Topic-Struktur

Broker: `mqtt.esrv.center` mit User `vbnet`/`vbnet`. Basis-Pfad: `heizung/...`

## Status & Heartbeat
| Topic | Richtung | Payload | Retain |
|---|---|---|---|
| `heizung/status` | RevPi -> | `online` / `offline` (LWT) | yes |
| `heizung/heartbeat` | RevPi -> | `<sec_uptime>` (alle 30 s) | no |
| `heizung/ha/heartbeat` | HA -> RevPi | beliebig, z.B. Unix-Timestamp (Automation alle 60 s) | no |
| `heizung/failsafe/active` | RevPi -> | `0` / `1` | yes |
| `heizung/failsafe/grund` | RevPi -> | `mqtt_timeout` / `sensor_loss` / ... | yes |
| `heizung/gesamt/active` | RevPi -> | `0` / `1` | yes |
| `heizung/gesamt/vl_soll/state` | RevPi -> | Gemeinsamer Soll-Vorlauf fuer WP1/WP2 | yes |
| `heizung/routing/state` | RevPi -> | JSON mit aktiven Senken, Quellenanzahl, Pool/BWWP-Status | yes |

## Komponenten-State (RevPi publisht)
| Topic | Payload | Beispiel |
|---|---|---|
| `heizung/wp1/state` | JSON | `{"freigabe": true, "vl_soll": 38.0, "vl_ist": 37.5, "rl_ist": 32.0, "leistung_pct": 65, "modus": "heizen", "stoerung": false}` |
| `heizung/wp2/state` | JSON | s.o. |
| `heizung/bwwp/state` | JSON | s.o. |
| `heizung/mischer/fbh/state` | JSON | `{"position_pct": 60, "vl_soll": 35.0, "vl_ist": 34.8, "hand": false}` |
| `heizung/mischer/klima_og/state` | JSON | s.o. |
| `heizung/pumpe/<name>/state` | JSON | `{"an": true, "hand": false}` |
| `heizung/temp/<sensorname>/state` | float | `45.2` |
| `heizung/tor/status` | string | `offen` / `halb_offen` / `zu` / `unbekannt` |
| `heizung/anforderung/<kreis>/aktuell` | JSON | `{"vl_soll": 42, "aktiv": true, "quelle": "ha"}` (vom RevPi rueckgespiegelt) |

Wichtig: `fbh_eg`, `klima_og`, `nebengeb`, `hk_backup` und `pool` sind Senken
am gemeinsamen Gesamtwaermekreis. WP1/WP2 werden nicht fest einer Senke
zugeordnet; beide koennen jede aktive Senke bedienen.

## Command-Topics (HA -> RevPi)
| Topic | Payload | Aktion |
|---|---|---|
| `heizung/anforderung/fbh_eg/set` | JSON `{"vl_soll": 42, "aktiv": true}` | Anforderung von HA |
| `heizung/anforderung/klima_og/set` | JSON | dito |
| `heizung/anforderung/nebengeb/set` | JSON | dito |
| `heizung/anforderung/pool/set` | JSON | Pool als Senke am Gesamtwaermekreis |
| `heizung/anforderung/bwwp/set` | JSON | dito |
| `heizung/<komponente>/hand/set` | JSON `{"hand": true, "wert": 80}` | Hand-Modus aktivieren mit Wert |
| `heizung/<komponente>/hand/auto` | leer | Hand-Modus deaktivieren |
| `heizung/tor/ganz/cmd` | leer | Impuls 250 ms am DO20 |
| `heizung/tor/halb/cmd` | leer | Impuls 250 ms am DO21 |
| `heizung/heizkurve/set` | JSON `{"stuetzpunkte":[{"aussen":-12,"vl":45}, ...]}` | Heizkurve aktualisieren |
| `heizung/failsafe/force` | `0`/`1` | Failsafe manuell forcieren (Test) |

## Home Assistant Auto-Discovery
Der Service publisht beim Start unter `homeassistant/...` die Discovery-Configs
mit `retain=true`. Bei Topic-Aenderungen alte Discovery zuerst raeumen
(`MQTT Explorer` oder via Code-Migration).

Beispiel `homeassistant/sensor/heizung_aussen/config`:
```json
{
  "device": {"identifiers": ["heizung-haupt"], "name": "Heizung Hauptsteuerung"},
  "name": "Aussentemperatur",
  "unique_id": "heizung_aussen",
  "state_topic": "heizung/temp/aussen/state",
  "unit_of_measurement": "C",
  "device_class": "temperature",
  "expire_after": 120
}
```
