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

- **DO20/DO21 Tor**: Nur 250 ms-Impulse (Taster-Simulation), keine Dauerstellung.
- **Mischer-Auf/Zu-Paare** (z.B. DO08/DO09): Software-seitig sicherstellen, dass nie beide Richtungen gleichzeitig aktiv sind.
- **PiCtory-Namen**: Stand 2026-06-17 aus der gruenen Hauptsteuerung uebernommen. Doppelte Modultypen erhalten PiCtory-Suffixe wie `_i17` oder `_i14`.

## Slave-Steuerung Hauptkeller

Empfohlen:

| Modul | Zweck |
|---|---|
| DIO | 14 DI + 14 DO fuer Pumpen, Mischer AUF/ZU, lokale Kontakte |
| CPU | RevPi #2, 10.1.25.11 |
| AIO x3 | 6 RTD fuer Mischerkreise + 6 AO Reserve + 12 AI Reserve |

Siehe [LASTENHEFT.md](../LASTENHEFT.md#43-slave-revpi-hauptkeller-spater).
