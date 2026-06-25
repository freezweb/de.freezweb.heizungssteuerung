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
| `heizung/brauchwasser/ladung_aktiv` | RevPi -> | `0` / `1`, aktuelle Speicherladung ueber Oelbrenner + BW-Ladepumpe | yes |
| `heizung/brauchwasser/grund` | RevPi -> | Regelgrund, z.B. `unter_einschaltschwelle`, `soll_erreicht`, `sensor_bw_oben_ungueltig` | yes |
| `heizung/brauchwasser/state` | RevPi -> | JSON mit Freigabe, Aktivstatus, Temperaturen, Sollwert, Hysterese und Grund | yes |
| `heizung/brunnen/active` | RevPi -> | `0` / `1`, Brunnenpumpe/FU aktiv | yes |
| `heizung/brunnen/druck_bar/state` | RevPi -> | Leitungsdruck in bar vom 4-20-mA-Sensor | yes |
| `heizung/brunnen/fu_soll_pct/state` | RevPi -> | Drehzahlsollwert an den FU in Prozent | yes |
| `heizung/brunnen/fluss_l_min/state` | RevPi -> | Momentaner Durchfluss vom Modbus-Flowmeter in L/min | yes |
| `heizung/brunnen/kein_durchfluss_s/state` | RevPi -> | Sekunden seit letztem echten Durchfluss, leer wenn kein frischer Modbuswert vorliegt | yes |
| `heizung/brunnen/abschaltung_in_s/state` | RevPi -> | Restzeit bis Flow-basierter Abschaltung in Sekunden, leer wenn Timer nicht laeuft | yes |
| `heizung/brunnen/grund` | RevPi -> | Regelgrund, z.B. `bereit`, `minderdruck_start`, `regelt`, `maxdruck_erreicht`, `sensor_unplausibel` | yes |
| `heizung/brunnen/state` | RevPi -> | JSON mit Aktivstatus, Druck, FU-Sollwert, Flow, Min/Max/Regeldruck und Grund | yes |
| `heizung/pv/ueberschuss/state` | RevPi -> | `0` / `1`, von HA empfangenes PV-Ueberschuss-Signal | yes |
| `heizung/pv/mangel/state` | RevPi -> | `0` / `1`, von HA empfangenes PV-Mangel-Signal | yes |
| `heizung/freigabe/state` | RevPi -> | JSON mit allen Quellen-/Senkenfreigaben | yes |
| `heizung/freigabe/quellen/<quelle>/state` | RevPi -> | `0` / `1` fuer `oelbrenner`, `wp1`, `wp2`, `bwwp` | yes |
| `heizung/freigabe/senken/<senke>/state` | RevPi -> | `0` / `1` fuer `brauchwasser`, `fbh_eg`, `klima_og`, `nebengeb`, `hk_backup`, `pool` | yes |
| `heizung/regler/<name>/state` | RevPi -> | Reglerparameter, z.B. `mischer_reserve_k` | yes |

## Komponenten-State (RevPi publisht)
| Topic | Payload | Beispiel |
|---|---|---|
| `heizung/wp1/state` | JSON | `{"freigabe": true, "vl_soll": 38.0, "vl_ist": 37.5, "rl_ist": 32.0, "leistung_pct": 65, "modus": "heizen", "stoerung": false}` |
| `heizung/wp2/state` | JSON | s.o. |
| `heizung/bwwp/state` | JSON | s.o. |
| `heizung/mischer/fbh/state` | JSON | `{"position_pct": 60, "vl_soll": 35.0, "vl_ist": 34.8, "hand": false}` |
| `heizung/mischer/klima_og/state` | JSON | s.o. |
| `heizung/pumpe/<name>/state` | JSON | `{"an": true, "hand": false}` |
| `heizung/do/<komponente>/state` | `0` / `1` | Tatsachlich geschriebener Digitalausgang |
| `heizung/ao/<komponente>/state` | float | Tatsachlich geschriebener Analogausgang |
| `heizung/<komponente>/hand/mode/state` | `0` / `1` | Handbetrieb aktiv |
| `heizung/<komponente>/hand/value/state` | bool/float | Aktueller Handwert |
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
| `heizung/anforderung/<kreis>/aktiv/set` | `0` / `1` | Direkter HA-MQTT-Switch fuer Anforderung |
| `heizung/anforderung/<kreis>/vl_soll/set` | Zahl | Direkter HA-MQTT-Number fuer Sollwert |
| `heizung/<komponente>/hand/set` | JSON `{"hand": true, "wert": 80}` | Hand-Modus aktivieren mit Wert |
| `heizung/<komponente>/hand/auto` | leer | Hand-Modus deaktivieren |
| `heizung/freigabe/quellen/<quelle>/set` | `0` / `1` | Waermequelle erlauben/sperren |
| `heizung/freigabe/senken/<senke>/set` | `0` / `1` | Heizkreis/Senke erlauben/sperren |
| `heizung/regler/mischer_reserve_k/set` | Zahl `0..15` | Aufschlag auf hoechste Senkenanforderung |
| `heizung/regler/wp_parallel_ab_aktive_kreise/set` | Zahl `1..10` | Ab wie vielen aktiven Senken beide WPs laufen duerfen |
| `heizung/regler/brauchwasser_soll_c/set` | Zahl `30..70` | Abschalttemperatur der aktuellen Brauchwasserladung |
| `heizung/regler/brauchwasser_hysterese_k/set` | Zahl `1..20` | Einschaltdifferenz unterhalb des Sollwerts |
| `heizung/regler/brunnen_min_druck_bar/set` | Zahl `0..9.5` | Unterschreiten startet Brunnenpumpe/FU |
| `heizung/regler/brunnen_max_druck_bar/set` | Zahl `0.2..10` | Ueberschreiten stoppt Brunnenpumpe/FU |
| `heizung/regler/brunnen_regeldruck_bar/set` | Zahl `0..10` | Konstantdruck-Sollwert bei offenem Verbraucher |
| `heizung/regler/brunnen_fu_start_pct/set` | Zahl `0..100` | Start-Sollwert beim Anlaufen der Brunnenpumpe |
| `heizung/regler/brunnen_fu_max_pct/set` | Zahl `0..100` | Obere FU-Grenze fuer Inbetriebnahme/Leistungsschutz |
| `heizung/regler/brunnen_kp_pct_pro_bar/set` | Zahl `0..200` | Proportionalverstaerkung in Prozent je bar Druckabweichung |
| `heizung/regler/brunnen_fu_ramp_up_pct_s/set` | Zahl `1..500` | Maximale Erhoehung des FU-Sollwerts pro Sekunde |
| `heizung/regler/brunnen_fu_ramp_down_pct_s/set` | Zahl `1..1000` | Maximale Reduzierung des FU-Sollwerts pro Sekunde |
| `heizung/regler/brunnen_flow_min_l_min/set` | Zahl `0..20` | Darunter gilt der Flowmeter als kein echter Durchfluss |
| `heizung/regler/brunnen_flow_timeout_s/set` | Zahl `10..1800` | So lange kein Durchfluss -> Brunnenpumpe/FU stoppt |
| `heizung/regler/brunnen_flow_stop_tolerance_bar/set` | Zahl `0..2` | Flow-Stop-Timer erst ab Regeldruck minus Toleranz |
| `heizung/pv/ueberschuss/set` | `0` / `1` | HA setzt PV-Ueberschuss; kein physischer RevPi-DI |
| `heizung/pv/mangel/set` | `0` / `1` | HA setzt PV-Mangel; kein physischer RevPi-DI |
| `heizung/tor/oeffnen_ganz/cmd` | leer | Oeffnen beider Fluegel, wenn nicht beide Fluegel bereits nicht-geschlossen sind |
| `heizung/tor/oeffnen_halb/cmd` | leer | Oeffnen rechter Fluegel, wenn rechter Fluegel geschlossen ist |
| `heizung/tor/schliessen/cmd` | leer | Schliessen, wenn nicht beide Fluegel bereits geschlossen sind |
| `heizung/tor/ganz/cmd` | leer | Legacy-Alias fuer `oeffnen_ganz` |
| `heizung/tor/halb/cmd` | leer | Legacy-Alias fuer `oeffnen_halb` |
| `heizung/heizkurve/set` | JSON `{"stuetzpunkte":[{"aussen":-12,"vl":45}, ...]}` | Heizkurve aktualisieren |
| `heizung/failsafe/force` | `0`/`1` | Failsafe manuell forcieren (Test) |

Freigabe-Regel: Eine HA-Anforderung wird nur verarbeitet, wenn die zugehoerige
Senke freigegeben ist. Eine Waermequelle wird nur verwendet, wenn ihre Freigabe
gesetzt ist. Startdefaults: Oelbrenner und FBH-EG erlaubt, WP1/WP2/BWWP/Pool
gesperrt bis zum bewussten Haken in HA.

Brauchwasser-Regel: Die aktuelle Speicherladung ist keine HA-Anforderung,
sondern ein eigener Regler. Wenn `freigabe/senken/brauchwasser` und
`freigabe/quellen/oelbrenner` gesetzt sind, der obere Speicherfuehler plausibel
ist und unter `brauchwasser_soll_c - brauchwasser_hysterese_k` faellt, werden
`DO01` Brenner und `DO02` Ladepumpe Brauchwasser aktiviert. Die Ladung bleibt
bis `brauchwasser_soll_c` aktiv. Bei unplausiblem Fuehlerwert bleibt sie aus.

Brunnen-Konstantdruck: Die Brunnenpumpe sitzt im Keller und wird lokal ueber
FU geregelt. Ein 4-20-mA-Drucksensor 0-10 bar liefert `brunnen_druck`; der
FU bekommt `brunnen_fu_soll` als Analogausgang; der FU ist so skaliert, dass
`0 %` den FU stoppt. `brunnen_pumpe_freigabe` ist eine optionale zusaetzliche
Run-/Sicherheitsfreigabe. Sinkt der Druck unter
`brunnen_min_druck_bar`, startet die Pumpe. Im Betrieb regelt der FU-Sollwert
auf `brunnen_regeldruck_bar`. Steigt der Druck ueber
`brunnen_max_druck_bar`, wird abgeschaltet, weil kein Verbraucher mehr offen
ist und der 100-l-Druckspeicher gefuellt ist.
Zusaetzlich liest die Hauptsteuerung den ESPHome-Wasserzaehler lokal per
Modbus. Wenn der Momentandurchfluss laenger als
`brunnen_flow_timeout_s` unter `brunnen_flow_min_l_min` bleibt, wird mit
Regelgrund `kein_durchfluss_stop` abgeschaltet, auch wenn der Druck den
Maxdruck nicht erreicht.

Der RevPi publiziert die Direktzustande zurueck:

- `heizung/anforderung/<kreis>/aktiv/state`
- `heizung/anforderung/<kreis>/vl_soll/state`

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

## CPU-LEDs

Die RevPi-Connect-4-internen LEDs werden direkt ueber `RevPiLED`/`core.A1..A5`
gesetzt:

| CPU | LED | Bedeutung |
|---|---|---|
| Haupt + Keller | A1 | Heartbeat: wechselt pro Zyklus blau/gelb |
| Haupt + Keller | A2 | Verbindung zur anderen CPU: gruen ok, gelb Start/Warten, rot kein aktueller Modbus-Watchdog |
| Haupt | A3 | MQTT-Broker verbunden: gruen/rot |
| Haupt | A4 | Home-Assistant-Heartbeat: gruen ok, gelb optional/fehlt, rot wenn als Pflicht konfiguriert und fehlt |
| Haupt | A5 | Failsafe: gruen normal, rot aktiv |
| Keller | A3-A5 | aus |

Der Keller-RevPi publiziert keine eigenen MQTT-Regelwerte. Er laeuft als
Modbus-TCP-I/O-Slave; alle MQTT-Status-/Reglerwerte kommen von der
Hauptsteuerung.
