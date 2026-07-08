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
- **Oelbrenner Rueckmeldungen**: DI12 = Wasserdruckwachter (NC/24V), DI13 = Oelbrenner Stoermeldung, DI14 = Oelbrenner Betriebsmeldung, DI15 = Sicherheitstemperaturbegrenzer/STB (NC/24V). Bei Stoerung und bei Rueckkehr auf OK sendet Home Assistant eine Telegram-Nachricht. DI13 meldet nur den Feuerungsautomaten; DO01 bleibt bei normaler Anforderung an, damit die Entstoertaste am Brenner jederzeit wirkt.
- **Wassermangel / DI12**: Bei geoeffnetem Wasserdruckwachter werden Brennerfreigabe und alle Heizungs-Hauptkreis-Pumpen hart abgeschaltet, auch wenn ein Handwert aktiv ist. Betroffen sind DO02, DO18, DO19 sowie K-DO01 bis K-DO03; Brunnenpumpe/FU ist davon nicht betroffen.
- **Klima-OG Kuehlmodus**: Wenn `klima_og.kuehlung_enabled` aktiv ist und Klima OG einen niedrigen VL-Sollwert anfordert, schliesst die Steuerung den Heizmischer (`K-AO03 = 0 %`), nimmt Klima OG aus dem Heizrouting und schaltet den Brunnen-/Waermetauscherweg: DO06 `brunnen_mv`, K-DO02 `pumpe_klima_og`, K-DO04 `brunnen_pumpe_freigabe` und mindestens den Startwert auf K-AO01 `brunnen_fu_soll`. Default bleibt aus, bis Hydraulik/Ventil fertig sind.
- **Keller-Uebergangsaufbau R421B16**: Wenn `keller_relais.enabled` aktiv ist, ersetzt das Waveshare/R421B16-Modul die physische Ausgabe fuer die drei Heizkreis-Pumpengruppen. Relais 1/2/3 = FBH EG (Pumpe/Fahrt/Richtung), Relais 4/5/6 = HK-Backup OG, Relais 7/8/9 = Klima OG. Routing und Automatik nutzen weiter die normalen Pumpen-/Mischer-Komponenten; die neun Handkanaele liegen separat auf `KR-DO01..KR-DO09`. Die Temperaturen kommen weiterhin als lokale PT1000 auf die Hauptsteuerung. Das Modul wird zyklisch per Modbus-FC03 gepollt; Ausfall setzt A3 rot und triggert die HA/Telegram-Stoermeldung.
- **Mischer-Auf/Zu-Paare** (z.B. DO08/DO09): Software-seitig sicherstellen, dass nie beide Richtungen gleichzeitig aktiv sind.
- **WP1/WP2**: Beide WPs speisen den gemeinsamen Sammel-/Gesamtwaermekreis. DO08-DO11/AO06-AO07 sind keine Haus/Pool-Auswahl, sondern Quellen-Freigabe in diesen Kreis.
- **Pool**: Der Pool ist eine Senke am Gesamtwaermekreis. DO12/DO13/AO08 schalten den Pool-Kreis, DO19 die Pool-Kreis-Pumpe.
- **HK-Backup OG**: Der 3WV/Mischer gehoert in den Hauptkeller zum Slave-RevPi. DO16/DO17/AO05 der Hauptsteuerung sind Reserve.
- **PV-Signale**: PV-Ueberschuss und PV-Mangel liegen nicht auf RevPi-DI. Sie kommen direkt aus HA per MQTT (`heizung/pv/ueberschuss/set`, `heizung/pv/mangel/set`).
- **PiCtory-Namen**: Stand 2026-06-17 aus der gruenen Hauptsteuerung uebernommen. Doppelte Modultypen erhalten PiCtory-Suffixe wie `_i17` oder `_i14`.

## Slave-Steuerung Hauptkeller

Ist-Stand 2026-06-18:

- RevPi #2 ist unter `10.1.25.11` erreichbar.
- Auf dem Keller-RevPi laeuft **keine eigene Heizungsregelung**.
- `heizung.service` ist dort `disabled/inactive`.
- `heizung-keller-slave.service` ist der aktive Autostart-Service.
- Der Keller-RevPi stellt seine I/O nur per Modbus TCP auf Port `502` bereit.
- Die Hauptsteuerung `10.1.25.10` liest Keller-Sensoren per Modbus, berechnet
  die Regelung zentral und schreibt die gewuenschten Keller-Ausgaenge zurueck.
- `piTest -d` meldet die Keller-Erweiterungsmodule bis zur Spannungsversorgung
  als `NOT present`.

Planungsstand 2026-06-25: Die drei Mischerkreise sollen bevorzugt ueber
dezentrale RS485-Pumpengruppen-Platinen laufen. Diese Boards schalten lokal
Pumpe, 3WV AUF/ZU, messen VL/RL und setzen die vom Master vorgegebene
Zielposition per Laufzeitlogik um. Der direkte RevPi-I/O-Plan unten bleibt als
Reserve-/Rueckfallvariante. Hardwareentwurf:
[pumpengruppe-rs485-platine.md](pumpengruppe-rs485-platine.md).

Optional ist ein vierter Niedertemperaturkreis fuer das Gewaechshaus geplant:
Lufterhitzer mit ca. 35 Grad Vorlauf. Dieser Kreis soll als weitere RS485-
Pumpengruppen-Platine laufen.

Ist-Stand 2026-07-08: Am Keller-RevPi sind nur zwei AIO-Karten vorhanden.
Die vier lokalen RTD-Kanaele sind fuer HK-Backup und FBH belegt. Klima OG
kommt spaeter ueber die eigene Pumpengruppen-Platine und liegt nicht mehr auf
lokalen Keller-RTD-Kanaelen.

Belegung:

| Modul | Zweck |
|---|---|
| DIO | 14 DI + 14 DO fuer Pumpen, FU-Freigabe, lokale Kontakte |
| CPU | RevPi #2, 10.1.25.11 |
| AIO x2 | 4 RTD fuer HK-Backup/FBH + AO fuer FU/interne Mischer-Sollwerte + AI fuer Drucksensor/Reserve |

Vorgeschlagene lokale I/O-Zuordnung fuer den Slave:

| Kanal | Funktion |
|---|---|
| DO01 | Pumpe FBH EG |
| DO02 | Pumpe Klima OG |
| DO03 | Pumpe HK-Backup OG |
| DO04 | FU Brunnenpumpe Freigabe / Run |
| DO05-DO14 | Reserve |
| DI01-DI03 | Stoer-/Rueckmeldekontakte FBH/Klima/HK |
| DI04-DI14 | Reserve |
| RTD01/RTD02 | HK-Backup OG VL/RL auf K-RTD2.1/K-RTD2.2 |
| RTD03/RTD04 | FBH EG RL/VL auf K-RTD3.1/K-RTD3.2 |
| AI01 | PT-506 Brunnen-Drucksensor 4-20 mA, 0-10 bar |
| AI02-AI08 | Reserve 0-10V/4-20mA |
| AO01 | FU Brunnenpumpe Drehzahlsollwert 4-20 mA |
| AO02-AO04 | interne Mischer-Sollwerte FBH/Klima/HK; aktuell ueber R421B16-Laufzeitrelais bzw. spaeter dezentrale Platine |

RS485-Pumpengruppen am Bus 4:

| Slave | Kreis |
|---|---|
| 30 | FBH EG |
| 31 | Klima OG |
| 32 | HK-Backup OG |

Modbus-TCP-Test Nebengebaeude:

| Kreis | Ziel | Register/Transport |
|---|---|---|
| Nebengebaeude | ESP-Pumpengruppe `10.1.20.189:502`, Unit-ID `30` | Holding 0..3: Sequenz, Pumpe, Mischerposition x10, Mode; Input 0..5: Status, Position, VL/RL, Sequenz, Fehler |

In `settings.yaml` wird dafuer `pumpengruppen.nebengeb` aktiviert. Die
berechneten lokalen Ausgaenge `pumpe_nebengeb` und `sv_nebengeb_pct` bleiben
als logische/HA-Werte erhalten, werden bei `disable_local_outputs: true` aber
nicht mehr physisch auf DO18/AO04 geschrieben. DO14/DO15 werden im Testmodus
ebenfalls nicht lokal geschaltet.
| 33 | Gewaechshaus-Lufterhitzer, optional, VL-Soll ca. 35 Grad |

Brunnenregelung: Der Drucksensor und die FU-Ausgaenge sitzen am Keller-RevPi,
aber die Konstantdruckregelung laeuft zentral auf der Hauptsteuerung. Der
Keller-RevPi fuehrt nur die per Modbus TCP geschriebenen DO/AO-Sollwerte aus.

Wichtig fuer AI01: RevPi-AIO-Strommessung braucht die Bruecke `*` zu `+` am
jeweiligen Eingang. Bei K-AI01/AIO Input 1 muss bei 0 bar ca. 4 mA anliegen;
ein Wert nahe 0 mA setzt `InputStatus` auf Unterbereich und laesst die IN-LED
rot blinken.

Wichtig fuer die Keller-RTDs: In PiCtory muessen die AIO-Parameter auf
`RTDType = 1` und `RTD*Wiring = 2` stehen. Bei 2-Draht-PT1000-Fuehlern sind
zusaetzlich die Drahtbruecken am RTD-Eingang erforderlich; sonst liefert die
AIO `RTDStatus = 2` und `RTDValue = 8500` (wird in HA als nicht verfuegbar
ausgeblendet).

Siehe [LASTENHEFT.md](../LASTENHEFT.md#43-slave-revpi-hauptkeller-spater).
