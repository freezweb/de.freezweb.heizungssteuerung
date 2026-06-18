# I/O-Belegung Hauptsteuerung Heizungsraum

Diese Datei ist eine **lesbare** Sicht auf `config/io_map.yaml.example`.
Bei Aenderungen IMMER zuerst die YAML anpassen, dann diese Tabelle nachziehen.

## RevPi-Modulregeln

Korrekte Kapazitaeten laut Revolution-Pi-Doku:

| Modul | Kanaele |
|---|---|
| DIO | 14 DI + 14 DO |
| DI | 16 DI |
| AIO | 4 AI (V/I) + 2 RTD (Pt100/Pt1000) + 2 AO (V/I) |
| RevPi Connect 4 | max. 10 Erweiterungsmodule, 5 links + 5 rechts |

Quellen:
- https://revolutionpi.com/en/docs/revpi-dio
- https://revolutionpi.com/en/docs/revpi-di
- https://revolutionpi.com/en/docs/revpi-aio
- https://revolutionpi.com/en/docs/revpi-connect-4

## Hardware-Layout Hauptsteuerung (links nach rechts)

| Adresse | Seite | Typ | HW-Version | Bemerkung |
|---|---|---|---|---|
| 27 | links | DIO | 1.5 | DO15-DO28, DI15-DI28 |
| 28 | links | DIO | 1.5 | DO01-DO14, DI01-DI14 |
| 29 | links | AIO | 1.4 | RTD01-02, AI01-04, AO01-02 |
| 30 | links | AIO | 1.4 | RTD03-04, AO03-04 |
| 31 | links | AIO | 1.4 | RTD05-06, AO05-06 |
| 0 | CPU | CPU | 1.0 | RevPi Connect 4 WLAN 32/4GB |
| 32 | rechts | AIO | 1.4 | RTD07-08, AO07-08 |
| 33 | rechts | AIO | 1.4 | RTD09-10, AO09-10 |
| 34 | rechts | AIO | 1.4 | RTD11-12 |
| 35 | rechts | AIO | 1.4 | RTD13-14 |
| 36 | rechts | AIO | 1.4 | RTD15-16 |

Damit sind die 10 Erweiterungsmodule des Connect 4 voll belegt.

## Kapazitaet Hauptsteuerung

| Typ | Bedarf geplant | Verfuegbar | Reserve |
|---|---:|---:|---:|
| DO | 21 | 28 | 7 |
| DI | 16 | 28 | 12 |
| RTD direkt | 16 | 16 | 0 |
| AI V/I | 4 optional + Reserve | 32 | 28 |
| AO V/I | 10 | 16 | 6 |

Hinweis: Direkte PT1000-Fuehler gehoeren auf RTD-Kanaele. Die AI-Kanaele sind
fuer 0-10V/4-20mA-Messumformer, nicht fuer direkte PT1000.

## Wichtige Punkte

- **DI01/DI02 Tor**: DI01 = linker Fluegel geschlossen, DI02 = rechter Fluegel geschlossen.
- **DI03 Lichtschranke Tor**: NC-Sicherheitskreis, elektrisch `1 = sicher/frei`, `0 = unterbrochen`. HA-Discovery invertiert die `safety`-Binary-Sensor-Anzeige, damit `1` als sicher angezeigt wird.
- **DO20/DO21 Tor**: Nur 1000 ms-Impulse (Taster-Simulation), keine Dauerstellung. HA sendet semantische Befehle `oeffnen_ganz`, `oeffnen_halb` und `schliessen`; die Steuerung sperrt unnoetige Befehle anhand der beiden Geschlossen-Endschalter.
- **Brauchwasser aktuell**: DO01 = Oelbrenner-Freigabe, DO02 = Brauchwasser-Ladepumpe. Die Speicherladung laeuft nur mit Freigabe `brauchwasser` und plausiblem oberen Speicherfuehler `RTD03/bw_oben`; BWWP bleibt separat auf DO05/AO03 fuer spaeter.
- **Mischer-Auf/Zu-Paare** (z.B. DO08/DO09): Software-seitig sicherstellen, dass nie beide Richtungen gleichzeitig aktiv sind.
- **WP1/WP2**: Beide WPs speisen den gemeinsamen Sammel-/Gesamtwaermekreis. DO08-DO11/AO06-AO07 sind keine Haus/Pool-Auswahl, sondern Quellen-Freigabe in diesen Kreis.
- **Pool**: Der Pool ist eine Senke am Gesamtwaermekreis. DO12/DO13/AO08 schalten den Pool-Kreis, DO19 die Pool-Kreis-Pumpe.
- **HK-Backup OG**: Der 3WV/Mischer gehoert in den Hauptkeller zum Slave-RevPi. DO16/DO17/AO05 der Hauptsteuerung sind Reserve.
- **PV-Signale**: PV-Ueberschuss und PV-Mangel liegen nicht auf RevPi-DI. Sie kommen direkt aus HA per MQTT (`heizung/pv/ueberschuss/set`, `heizung/pv/mangel/set`).
- **PiCtory-Namen**: Stand 2026-06-17 aus der gruenen Hauptsteuerung uebernommen. Doppelte Modultypen erhalten PiCtory-Suffixe wie `_i17` oder `_i14`.

## Slave-Steuerung Hauptkeller

Ist-Stand 2026-06-17:

- RevPi #2 ist unter `10.1.25.11` erreichbar.
- `heizung.service` ist dort bewusst `disabled/inactive`.
- Die aktuell aufgespielte `io_map.yaml` ist noch eine Kopie der Hauptsteuerung
  und **keine** gueltige Slave-Belegung.
- `piTest -d` meldet die konfigurierten Erweiterungsmodule als `NOT present`;
  die zweite Steuerung ist damit elektrisch/PiCtory-seitig noch nicht
  betriebsbereit.

Geplante Belegung:

| Modul | Zweck |
|---|---|
| DIO | 14 DI + 14 DO fuer Pumpen, Mischer AUF/ZU, lokale Kontakte |
| CPU | RevPi #2, 10.1.25.11 |
| AIO x3 | 6 RTD fuer Mischerkreise + 6 AO Reserve + 12 AI Reserve |

Vorgeschlagene lokale I/O-Zuordnung fuer den Slave:

| Kanal | Funktion |
|---|---|
| DO01/DO02 | Mischer FBH EG AUF/ZU |
| DO03 | Pumpe FBH EG |
| DO04/DO05 | Mischer Klima OG AUF/ZU |
| DO06 | Pumpe Klima OG |
| DO07/DO08 | Mischer HK-Backup OG AUF/ZU |
| DO09 | Pumpe HK-Backup OG |
| DO10-DO14 | Reserve |
| DI01-DI03 | Stoer-/Rueckmeldekontakte FBH/Klima/HK |
| DI04-DI14 | Reserve |
| RTD01/RTD02 | FBH EG VL/RL |
| RTD03/RTD04 | Klima OG VL/RL |
| RTD05/RTD06 | HK-Backup OG VL/RL |
| AO01-AO03 | optionale stetige Mischerstellungen FBH/Klima/HK |
| AO04-AO06 | Reserve |

Siehe [LASTENHEFT.md](../LASTENHEFT.md#43-slave-revpi-hauptkeller-spater).
