# LASTENHEFT - Heizungssteuerung Freezweb (de.freezweb.heizungssteuerung)

Stand: 2026-06-16

Komplette Spezifikation des Projekts. Anderungen am Funktionsumfang erfordern
Update dieses Dokuments.

## 0. Zielsetzung (TL;DR)
Komplette Ablosung der bisherigen Heizungssteuerung durch eigene Python-Losung
auf 2x Revolution Pi Connect 4 (Hauptsteuerung Heizungsraum + Slave Hauptkeller).
Visualisierung und Verlaufsdaten komplett in Home Assistant via MQTT-Discovery.
Autarker Failsafe-Betrieb mit witterungsgefuhrter Heizkurve bei MQTT-/HA-Ausfall.
Jeder Ausgang Hand/Auto schaltbar mit pro Kanal konfigurierbarem Hand-Timeout.

Vorbereitet fur den Umbau auf 2x 16 kW Monoblock-Warmepumpe + separate
Brauchwasser-WP + Brunnenkuhlung + Pool ganzjahrig 35 Grad + Klima-OG +
Nebengebaude + Hoftor.

## 1. Raumliche Aufteilung & Komponenten

| Standort | Inhalt | Anbindung |
|---|---|---|
| Heizungsraum (separat) | Hauptsteuerung RevPi #1, Olbrenner (uebergangsweise), Warmwasserspeicher; spater 2x Monoblock-WP, Brauchwasser-WP, Pool-Hydraulik, Brunnenkuhlung-WT, Nebengebaude-Strang | direkte I/O |
| Hauptkeller (~12 m entfernt) | Slave-RevPi #2 (spater), 2x 3-Wege-Mischer + Umwalzpumpen, 3 Strange: FBH-EG, Klimakreis-OG, Heizkorper-Backup OG | LAN/VLAN 25, Modbus-TCP |
| EG | Heizkreisverteiler FBH + Shelly-Funkventile (von HA gesteuert) | nur HA |
| OG | Aktuell 6 Heizkorper mit Shelly-TRV -> spater 5 Klima-Innengerate (Kind, Buro, Schlaf, Bad, Flur) + Heizkorper-Backup | Modbus RTU |
| Hoftor | 2 Antriebsausgange (ganz/halb) + 2 Endschalter + 1 Lichtschranke | Haupt-CPU |

## 2. Wohnflachen & Heizlast

### 2.1 Raume Hauptgebaude

**Erdgeschoss - Gesamt 122,31 m^2, beheizt ~105,5 m^2**

| Raum | Masse | Flache | Beheizt? |
|---|---|---|---|
| Kueche | 5,20 x 3,55 | 18,46 | ja |
| Wohnen | 11,50 x 5,00 | 57,50 | ja |
| Bad | 3,30 x 2,75 | 9,08 | ja |
| Flur | 8,00 x 1,60 | 12,80 | ja |
| HWR | 3,35 x 2,15 | 7,20 | nein (kalt) |
| Wintergarten | 5,10 x 3,75 | 19,13 | nein (komplett unbeheizt) |
| Treppenflur | 3,85 x 2,00 | 7,70 | ja |

**Obergeschoss - Gesamt 111,07 m^2, beheizt ~99,2 m^2**

| Raum | Masse | Flache | Beheizt? | Klima-IG |
|---|---|---|---|---|
| Flur 1 | 2,85 x 2,70 | 7,70 | ja | - |
| Flur 2 | 5,85 x 2,75 | 16,09 | ja | ja (Flur-IG) |
| Flur 3 | 3,45 x 2,25 | 7,76 | ja | - |
| Saunaraum (Lager) | 6,90 x 3,55 | 24,50 | nein (Frostschutz) | - |
| Kind | 5,00 x 3,55 | 17,75 | ja | ja |
| Buero | 6,95 x 3,55 | 24,67 | ja | ja |
| Schlafen | 3,55 x 3,55 | 12,60 | ja | ja |
| Bad mit Whirlpool | 3,55 x 3,55 | 12,60 | ja | ja |

### 2.2 Weitere beheizte Flachen
- **Nebengebaude**: ~140 m^2 (2x Buero + 1x Konferenz/Aufenthalt/Kueche/Multifunktion)
- **Pool**: < 30 m^3 outdoor mit Rollabdeckung, **ganzjahrig 35 Grad**

### 2.3 Heizlast-Uberschlag
Annahmen: Massivziegel mit beidseitiger Daemmung 10-14 cm, 2-Scheiben-Iso-Verglasung,
oberste Geschossdecke gedaemmt, Keller ungedaemmt aber Heizungsverteilung
durchlaeuft (kein Frost), Kernsanierung 2000-2003 -> Heizlastniveau ca. 55-70 W/m^2.

| Bereich | Flache | Spez. Heizlast | Heizlast |
|---|---|---|---|
| Hauptgebaude (EG+OG) | ~205 m^2 | 65 W/m^2 | ~13 kW |
| Nebengebaude | 140 m^2 | 70 W/m^2 (Burobetrieb tagsueber) | ~10 kW |
| Pool 35 Grad outdoor, abgedeckt, -10 Grad Aussentemp | 25 m^2 Becken | 250 W/m^2 | ~6-8 kW dauerhaft |
| **Spitzenlast (gleichzeitig)** | | | **~28-30 kW** |

### 2.4 WP-Dimensionierungs-Empfehlung
- 2x 11 kW war urspruenglich zu knapp gerechnet.
- **Empfehlung: 2x 16 kW Monoblock** (gesamt 32 kW, Modulationsbereich typ. 5-16 kW/Stueck)
  - Damit immer mind. eine WP im Optimalbereich (5-8 kW) fuer Teillast
  - Bei Volllast beide parallel
  - Bei Abtauen einer WP uebernimmt die andere
- **Pool-Waerme aus PV-Ueberschuss** (30 kWp + 100 kWh Speicher) -> realistisch
- **Brauchwasser-WP** bleibt separat (200 L, eigener Steuerkreis)

### 2.5 WP-Modell-Favorit Monoblock

**Favorit Stand 2026-06-23: Sunex NEXUS M18 EVI 18 kW Monoblock-Waermepumpe (R32)**

- Link: https://www.thermona-shop.de/sunex-nexus-m18-evi-18-kw-monoblock-waermepumpe-fuer-groessere-gebaeude-r32-47395
- Preis bei Pruefung: 2.262,99 EUR inkl. MwSt., zzgl. Versand
- Auslegung: 2 Stueck = 36 kW nominal; alternativ 3 kleinere Geraete nur bei deutlich besserem Preis/Modbus-Konzept.
- Passt zur Anlage, weil das Haus bereits auf Niedertemperatur bis ca. 55 Grad ausgelegt ist.
- Wichtige Daten laut Shop: 18 kW, max. VL 55 Grad, SCOP W35 4,58, SCOP W55 3,47, 400 V / 3~, R32, Betrieb -25 bis +45 Grad, empfohlener Heizwasserdurchfluss 3,1 m3/h.
- Achtung: Umwaelzpumpe ist laut Shop nicht integriert; Hydraulikpumpe, Sicherheitsgruppe, Magnetfilter und Frostschutzkonzept separat planen.
- Vor Bestellung zwingend klaeren: Modbus/Steuerungsdoku, externe Freigabe ueber Linkage Switch, Sollwertvorgabe, Fehler-/Statusregister, Gewaehrleistungsbedingungen bei Eigenintegration.

Weitere marktuebliche Kandidaten als Vergleich:
Heiko Thermal Plus 16 kW, Midea V8 16 kW, HeyHeat, Solar2Heat.

Pflichtkriterien:
- Monoblock (kein Innengeraet)
- Modbus RTU mindestens: Freigabe, VL-Soll, Heiz/Kuehl-Umschaltung, Status, Fehler
- Modulierend (Inverter)
- COP > 4 bei A7/W35
- VL bis 55 Grad
- 230 V oder 400 V Anschluss klaeren

## 3. Bestandshardware & Anpassung

### 3.1 Vorhanden (Heizungsraum, Stand 2026-06-16)
- 4x **RevPi Connect 4 WLAN 32/4GB** (eine CPU fuer Hauptsteuerung aktiv, weitere als Slave/Reserve; Hostname Hauptsteuerung `RevPi107273`)
- 3x **DIO V1.5** - je 14 DI + 14 DO (Eingaenge und Ausgaenge separat vorhanden, nicht 14 universelle Kanaele)
- 17x **DI V1.5** - je 16 DI = 272 DI Reservebestand
- 11x **AIO V1.4** - je 4 AI (V/I) + 2 RTD (Pt100/Pt1000) + 2 AO (V/I)

Wichtige Korrektur: DIO-Kanaele sind nicht "entweder DI oder DO". Ein DIO stellt
parallel 14 Eingange und 14 Ausgaenge bereit. AIO stellt direkte PT1000-Fuehler
nur an den 2 RTD-Kanaelen pro Modul bereit; die 4 AI sind Spannungs-/Stromeingaenge.

### 3.2 Geplante Modulkonfiguration (Endausbau)

**Hauptsteuerung Heizungsraum** (von links nach rechts):
> **DIO, DIO, AIO, AIO, AIO, CPU, AIO, AIO, AIO, AIO, AIO**

-> 2x DIO = 28 DI + 28 DO (21 DO geplant, 7 DO Reserve; 16 DI geplant, 12 DI Reserve)
-> 8x AIO = 32 AI (V/I) + 16 RTD + 16 AO
-> RevPi Connect 4 Limit eingehalten: 5 Module links + 5 Module rechts

**Slave-Steuerung Hauptkeller** (neu aufzubauen, spater):
> **DIO, CPU, AIO, AIO, AIO**

-> 1x DIO = 14 DI + 14 DO
-> 3x AIO = 12 AI (V/I) + 6 RTD + 6 AO
-> Damit sind alle 3 vorhandenen DIO und alle 11 vorhandenen AIO sinnvoll verteilt.
-> Die 17 DI-Module bleiben Reserve oder fuer spaetere dezentrale reine Eingangsstationen.

### 3.3 Zusatzhardware (zu beschaffen)

| Komponente | Zweck | Stueck | grob |
|---|---|---|---|
| Waveshare RS485-to-ETH | Modbus-Gateway WP-Bus | 1 | 50 EUR |
| Waveshare RS485-to-ETH | Modbus-Gateway Klima-OG-Bus | 1 | 50 EUR |
| Waveshare RS485-to-ETH | Modbus-Gateway BW-WP/Pool-/Filterperipherie | 1 | 50 EUR |
| Dezentrale RS485-Pumpengruppen-Platine | je Mischerkreis: 3WV Auf/Zu, Pumpe, VL/RL-RTD, ESP32 OTA | 3+ | Eigenentwicklung |
| Koppelrelais 24V -> 230V/16A | Pumpen, WP-Freigaben, Brunnen, Tor | ~20 | je 8-12 EUR |
| Hutschienen-Netzteil 24V/5A | I/O-Versorgung Slave-Schrank | 1 | 40 EUR |
| PT1000 Anlegefuehler | neue Sensoren erganzend | ~6 | je 15 EUR |
| Schaltschrank Slave | Hauptkeller | 1 | 200 EUR |
| Endschalter Hoftor (mechanisch, NO) | Tor zu-Position | 2 | 30 EUR |
| Lichtschranke Tor (Reflex, 24V) | Sicherheit Tor | 1 | 80 EUR |
| 3WV-Stellantriebe spater optional 0-10V | wenn 230V-Antriebe ersetzt werden | 5 (sukzessive) | je 100-150 EUR |

### 3.4 Netzwerk (festgelegt)
- VLAN: **25 / heizung_25 / 10.1.25.0/24** (pfSense + UniFi)
- **RevPi #1 (Heizungsraum)**: 10.1.25.10/24 statisch
- **RevPi #2 (Hauptkeller)**: 10.1.25.11/24 statisch (spaeter)
- Gateway: 10.1.25.1 (pfSense)
- MQTT-Broker: mqtt.esrv.center (User vbnet/vbnet)
- HA: 10.1.20.2 (eigenes VLAN, ueber pfSense erreichbar)
- SSH-Key vom Daniel-Laptop: `~/.ssh/id_ed25519_heizung` (eingerichtet 2026-06-16)

## 4. I/O-Belegungsplan

### 4.1 Haupt-RevPi Digital

Physische Klemmenlogik fuer die Hauptsteuerung:

- Karte 1 von links = DIO Adresse 27 / PiCtory `DIO2`: `DO1.1-DO1.14`, `DI1.1-DI1.14` = Software `DO15-DO28`, `DI15-DI28`
- Karte 2 von links = DIO Adresse 28 / PiCtory `DIO1`: `DO2.1-DO2.14`, `DI2.1-DI2.14` = Software `DO01-DO14`, `DI01-DI14`

**Digitale Ausgaenge (DO):**

| # | Physisch | Beschreibung | Phase |
|---|---|---|---|
| DO01 | DO2.1 | Olbrenner Freigabe (uebergangsweise) | A -> entfaellt B |
| DO02 | DO2.2 | Ladepumpe Brauchwasserspeicher (uebergangsweise) | A -> entfaellt B |
| DO03 | DO2.3 | WP1 Freigabe (potentialfrei) | B |
| DO04 | DO2.4 | WP2 Freigabe (potentialfrei) | B |
| DO05 | DO2.5 | Brauchwasser-WP Freigabe | B |
| DO06 | DO2.6 | Brunnenpumpe Magnetventil | C |
| DO07 | DO2.7 | Pool-Filterpumpe Freigabe | E |
| DO08 | DO2.8 | WP1 in Sammel-/Gesamtwaermekreis AUF | B |
| DO09 | DO2.9 | WP1 in Sammel-/Gesamtwaermekreis ZU | B |
| DO10 | DO2.10 | WP2 in Sammel-/Gesamtwaermekreis AUF | B |
| DO11 | DO2.11 | WP2 in Sammel-/Gesamtwaermekreis ZU | B |
| DO12 | DO2.12 | 3WV Pool-Heizkreis AUF | E |
| DO13 | DO2.13 | 3WV Pool-Heizkreis ZU | E |
| DO14 | DO2.14 | 3WV Nebengebaude AUF | B |
| DO15 | DO1.1 | 3WV Nebengebaude ZU | B |
| DO16 | DO1.2 | Reserve (HK-Backup-Mischer sitzt am Keller-Slave) | - |
| DO17 | DO1.3 | Reserve (HK-Backup-Mischer sitzt am Keller-Slave) | - |
| DO18 | DO1.4 | Pumpe Nebengebaude | B |
| DO19 | DO1.5 | Pumpe Pool-Heizkreis | E |
| DO20 | DO1.6 | Tor "ganz" Impuls (1000 ms via Koppelrelais) | A |
| DO21 | DO1.7 | Tor "halb" Impuls (1000 ms via Koppelrelais) | A |
| DO22 | DO1.8 | Reserve | - |
| DO23 | DO1.9 | Reserve | - |
| DO24 | DO1.10 | Reserve | - |
| DO25 | DO1.11 | Reserve | - |
| DO26 | DO1.12 | Reserve | - |
| DO27 | DO1.13 | Reserve | - |
| DO28 | DO1.14 | Reserve | - |

Klima-OG Kuehlmodus: Wenn die Klima-OG-Senke eine niedrigere Temperatur
fordert, aber der Heizungsmischer bereits geschlossen bleiben muss, kann die
Steuerung in den Brunnen-/Waermetauscherbetrieb wechseln. Dann wird DO06
`Brunnenpumpe Magnetventil` zusammen mit K-DO02 `Pumpe Klimakreis-OG`,
K-DO04 `FU Brunnenpumpe Freigabe` und K-AO01 `FU-Sollwert` aktiviert; K-AO03
`Mischer Klima-OG` wird auf `0 %` gesetzt. Die Funktion bleibt per Default
deaktiviert (`klima_og.kuehlung_enabled: false`), bis Magnetventil bzw.
spaeter ein regelbares Ventil hydraulisch sicher eingebaut sind.

**Digitale Eingange (DI):**

| # | Physisch | Beschreibung | Phase |
|---|---|---|---|
| DI01 | DI2.1 | Endschalter linker Torfluegel geschlossen | A |
| DI02 | DI2.2 | Endschalter rechter Torfluegel geschlossen | A |
| DI03 | DI2.3 | Lichtschranke Tor (Sicherheit, NC: 1=sicher/frei, 0=unterbrochen) | A |
| DI04 | DI2.4 | SG-Ready 1 (EVU, reserviert) | - |
| DI05 | DI2.5 | SG-Ready 2 (EVU, reserviert) | - |
| DI06 | DI2.6 | Reserve (PV-Ueberschuss kommt direkt per HA/MQTT) | - |
| DI07 | DI2.7 | Reserve (PV-Mangel kommt direkt per HA/MQTT) | - |
| DI08 | DI2.8 | Sammelstoerung WP1 | B |
| DI09 | DI2.9 | Sammelstoerung WP2 | B |
| DI10 | DI2.10 | Sammelstoerung BW-WP | B |
| DI11 | DI2.11 | Stromungswachter Brunnen | C |
| DI12 | DI2.12 | Oelbrenner Wasserdruckwachter (NC: 1=OK, 0=Stoerung) | A |
| DI13 | DI2.13 | Oelbrenner Stoermeldung | A |
| DI14 | DI2.14 | Oelbrenner Betriebsmeldung | A |
| DI15 | DI1.1 | Oelbrenner Sicherheitstemperaturbegrenzer STB (NC: 1=OK, 0=Stoerung) | A |
| DI16 | DI1.2 | Reserve | - |

Sicherheitswirkung Oelbrenner Bestand:

- DI12 Wasserdruckwachter offen / Wassermangel sperrt DO01 Brennerfreigabe und
  schaltet alle Heizungs-Hauptkreis-Pumpen ab, auch im Handbetrieb:
  DO02, DO18, DO19 sowie K-DO01 bis K-DO03.
- DI15 STB offen sperrt DO01 Brennerfreigabe hart, auch im Handbetrieb.
- DI13 Brenner-Stoermeldung wird gemeldet und per Telegram eskaliert, sperrt
  DO01 aber nicht. So bleibt die normale Anforderung am Feuerungsautomaten an,
  damit der Brenner direkt an seiner Taste entstoert werden kann.

### 4.2 Haupt-RevPi Analog (AIO #1-8)

Physische AIO-Karten der Hauptsteuerung:

- Karte 3 von links = AIO Adresse 29 / PiCtory `AIO1`
- Karte 4 von links = AIO Adresse 30 / PiCtory `AIO2`
- Karte 5 von links = AIO Adresse 31 / PiCtory `AIO3`
- Karte 6 von links = AIO Adresse 32 / PiCtory `AIO4`
- Karte 7 von links = AIO Adresse 33 / PiCtory `AIO5`
- Karte 8 von links = AIO Adresse 34 / PiCtory `AIO6`
- Karte 9 von links = AIO Adresse 35 / PiCtory `AIO7`
- Karte 10 von links = AIO Adresse 36 / PiCtory `AIO8`

**RTD (16 direkte Pt1000-Kanaele auf 8 AIO):**

| # | Physisch | AIO | Kanal | Beschreibung |
|---|---|---|---|---|
| RTD01 | RTD3.1 | 1 | RTD1 | Vorlauf Kessel/WP-Sammelvorlauf |
| RTD02 | RTD3.2 | 1 | RTD2 | Ruecklauf Kessel/WP-Sammelruecklauf |
| RTD03 | RTD4.1 | 2 | RTD1 | Brauchwasser oben |
| RTD04 | RTD4.2 | 2 | RTD2 | Brauchwasser unten / Ladetemperatur |
| RTD05 | RTD5.1 | 3 | RTD1 | Aussentemperatur (Nordwand, beschattet) |
| RTD06 | RTD5.2 | 3 | RTD2 | Brunnenwasser-Eintritt WT |
| RTD07 | RTD6.1 | 4 | RTD1 | Brunnenwasser-Austritt WT |
| RTD08 | RTD6.2 | 4 | RTD2 | Kuehlkreis-Vorlauf (kalte Seite WT zum OG) |
| RTD09 | RTD7.1 | 5 | RTD1 | Kuehlkreis-Ruecklauf vom OG |
| RTD10 | RTD7.2 | 5 | RTD2 | Pool-Wassertemperatur |
| RTD11 | RTD8.1 | 6 | RTD1 | Pool-WT Vorlauf |
| RTD12 | RTD8.2 | 6 | RTD2 | Pool-WT Ruecklauf |
| RTD13 | RTD9.1 | 7 | RTD1 | Vorlauf Nebengebaude |
| RTD14 | RTD9.2 | 7 | RTD2 | Ruecklauf Nebengebaude |
| RTD15 | RTD10.1 | 8 | RTD1 | WP1 Verdampfertemperatur / Reserve je nach WP-Modbus |
| RTD16 | RTD10.2 | 8 | RTD2 | BW-WP Vorlauf / Reserve je nach BW-WP-Modbus |

**AI (32 Kanaele V/I - fuer 0-10V/4-20mA, nicht direkte PT1000):**

| # | Physisch | AIO | Kanal | Beschreibung |
|---|---|---|---|---|
| AI01 | AI3.1 | 1 | AI1 | WP1 Vorlauf analoger Messumformer (optional; primaer Modbus) |
| AI02 | AI3.2 | 1 | AI2 | WP1 Ruecklauf analoger Messumformer (optional; primaer Modbus) |
| AI03 | AI3.3 | 1 | AI3 | WP2 Vorlauf analoger Messumformer (optional; primaer Modbus) |
| AI04 | AI3.4 | 1 | AI4 | WP2 Ruecklauf analoger Messumformer (optional; primaer Modbus) |
| AI05 | AI4.1 | 2 | AI1 | Reserve fuer 0-10V/4-20mA |
| AI06 | AI4.2 | 2 | AI2 | Reserve fuer 0-10V/4-20mA |
| AI07 | AI4.3 | 2 | AI3 | Reserve fuer 0-10V/4-20mA |
| AI08 | AI4.4 | 2 | AI4 | Reserve fuer 0-10V/4-20mA |
| AI09 | AI5.1 | 3 | AI1 | Reserve fuer 0-10V/4-20mA |
| AI10 | AI5.2 | 3 | AI2 | Reserve fuer 0-10V/4-20mA |
| AI11 | AI5.3 | 3 | AI3 | Reserve fuer 0-10V/4-20mA |
| AI12 | AI5.4 | 3 | AI4 | Reserve fuer 0-10V/4-20mA |
| AI13 | AI6.1 | 4 | AI1 | Reserve fuer 0-10V/4-20mA |
| AI14 | AI6.2 | 4 | AI2 | Reserve fuer 0-10V/4-20mA |
| AI15 | AI6.3 | 4 | AI3 | Reserve fuer 0-10V/4-20mA |
| AI16 | AI6.4 | 4 | AI4 | Reserve fuer 0-10V/4-20mA |
| AI17 | AI7.1 | 5 | AI1 | Reserve fuer 0-10V/4-20mA |
| AI18 | AI7.2 | 5 | AI2 | Reserve fuer 0-10V/4-20mA |
| AI19 | AI7.3 | 5 | AI3 | Reserve fuer 0-10V/4-20mA |
| AI20 | AI7.4 | 5 | AI4 | Reserve fuer 0-10V/4-20mA |
| AI21 | AI8.1 | 6 | AI1 | Reserve fuer 0-10V/4-20mA |
| AI22 | AI8.2 | 6 | AI2 | Reserve fuer 0-10V/4-20mA |
| AI23 | AI8.3 | 6 | AI3 | Reserve fuer 0-10V/4-20mA |
| AI24 | AI8.4 | 6 | AI4 | Reserve fuer 0-10V/4-20mA |
| AI25 | AI9.1 | 7 | AI1 | Reserve fuer 0-10V/4-20mA |
| AI26 | AI9.2 | 7 | AI2 | Reserve fuer 0-10V/4-20mA |
| AI27 | AI9.3 | 7 | AI3 | Reserve fuer 0-10V/4-20mA |
| AI28 | AI9.4 | 7 | AI4 | Reserve fuer 0-10V/4-20mA |
| AI29 | AI10.1 | 8 | AI1 | Reserve fuer 0-10V/4-20mA |
| AI30 | AI10.2 | 8 | AI2 | Reserve fuer 0-10V/4-20mA |
| AI31 | AI10.3 | 8 | AI3 | Reserve fuer 0-10V/4-20mA |
| AI32 | AI10.4 | 8 | AI4 | Reserve fuer 0-10V/4-20mA |

**AO (10 Kanaele 0-10V):**

| # | Physisch | AIO | Kanal | Beschreibung |
|---|---|---|---|---|
| AO01 | AO3.1 | 1 | AO1 | WP1 VL-Sollwert |
| AO02 | AO3.2 | 1 | AO2 | WP2 VL-Sollwert |
| AO03 | AO4.1 | 2 | AO1 | BW-WP VL-Sollwert |
| AO04 | AO4.2 | 2 | AO2 | 3WV Nebengebaude (zukuenftig 0-10V) |
| AO05 | AO5.1 | 3 | AO1 | Reserve (HK-Backup-Mischer sitzt am Keller-Slave) |
| AO06 | AO5.2 | 3 | AO2 | WP1 in Sammel-/Gesamtwaermekreis (zukuenftig 0-10V) |
| AO07 | AO6.1 | 4 | AO1 | WP2 in Sammel-/Gesamtwaermekreis (zukuenftig 0-10V) |
| AO08 | AO6.2 | 4 | AO2 | Pool-Senke am Gesamtwaermekreis (zukuenftig 0-10V) |
| AO09 | AO7.1 | 5 | AO1 | Filterpumpe Pool Drehzahl |
| AO10 | AO7.2 | 5 | AO2 | Reserve |
| AO11 | AO8.1 | 6 | AO1 | Reserve |
| AO12 | AO8.2 | 6 | AO2 | Reserve |
| AO13 | AO9.1 | 7 | AO1 | Reserve |
| AO14 | AO9.2 | 7 | AO2 | Reserve |
| AO15 | AO10.1 | 8 | AO1 | Reserve |
| AO16 | AO10.2 | 8 | AO2 | Reserve |

### 4.3 Slave-RevPi Hauptkeller / dezentrale Pumpengruppen (spater)

Designentscheidung Stand 2026-06-25: Die Mischerkreise im Hauptkeller sollen
bevorzugt ueber dezentrale RS485-Pumpengruppen-Platinen laufen, nicht mehr
zwingend ueber direkte DIO/AIO-Kanaele des Keller-RevPi. Jede Platine schaltet
lokal Pumpe, 3WV AUF und 3WV ZU, misst VL/RL per RTD und berechnet die
Mischer-Laufzeit aus der per Modbus vorgegebenen Zielposition selbst. Details:
[docs/pumpengruppe-rs485-platine.md](docs/pumpengruppe-rs485-platine.md).

Die folgende RevPi-I/O-Planung bleibt als Rueckfall-/Reservevariante bestehen,
falls einzelne Kreise direkt auf den Keller-RevPi gelegt werden.

Geplante physische Klemmenlogik fuer den Keller-Slave:

- Keller-Karte 1 = DIO links der CPU: `K-DO1.1-K-DO1.14`, `K-DI1.1-K-DI1.14`
- Keller-Karte 2 = erste AIO rechts der CPU: `K-RTD2.1-K-RTD2.2`, `K-AI2.1-K-AI2.4`, `K-AO2.1-K-AO2.2`
- Keller-Karte 3 = zweite AIO rechts der CPU: `K-RTD3.1-K-RTD3.2`, `K-AI3.1-K-AI3.4`, `K-AO3.1-K-AO3.2`
- Keller-Karte 4 = dritte AIO rechts der CPU: `K-RTD4.1-K-RTD4.2`, `K-AI4.1-K-AI4.4`, `K-AO4.1-K-AO4.2`

**DIO (14 DI + 14 DO):**

| # | Physisch | Beschreibung |
|---|---|---|
| K-DO01 | K-DO1.1 | Pumpe Mischer FBH-EG |
| K-DO02 | K-DO1.2 | Pumpe Mischer Klimakreis-OG |
| K-DO03 | K-DO1.3 | Pumpe Heizkorper-Backup OG |
| K-DO04 | K-DO1.4 | FU Brunnenpumpe Freigabe / Run |
| K-DO05 | K-DO1.5 | Reserve |
| K-DO06 | K-DO1.6 | Reserve |
| K-DO07 | K-DO1.7 | Reserve |
| K-DO08 | K-DO1.8 | Reserve |
| K-DO09 | K-DO1.9 | Reserve |
| K-DO10 | K-DO1.10 | Reserve |
| K-DO11 | K-DO1.11 | Reserve |
| K-DO12 | K-DO1.12 | Reserve |
| K-DO13 | K-DO1.13 | Reserve |
| K-DO14 | K-DO1.14 | Reserve |
| K-DI01 | K-DI1.1 | Druckwachter Heizkreis (optional) |
| K-DI02 | K-DI1.2 | Stromungswachter Mischerkreis (optional) |
| K-DI03 | K-DI1.3 | Reserve |
| K-DI04 | K-DI1.4 | Reserve |
| K-DI05 | K-DI1.5 | Reserve |
| K-DI06 | K-DI1.6 | Reserve |
| K-DI07 | K-DI1.7 | Reserve |
| K-DI08 | K-DI1.8 | Reserve |
| K-DI09 | K-DI1.9 | Reserve |
| K-DI10 | K-DI1.10 | Reserve |
| K-DI11 | K-DI1.11 | Reserve |
| K-DI12 | K-DI1.12 | Reserve |
| K-DI13 | K-DI1.13 | Reserve |
| K-DI14 | K-DI1.14 | Reserve |

**AIO (3x AIO = 12 AI + 6 RTD + 6 AO):**

| # | Physisch | Beschreibung |
|---|---|---|
| K-RTD01 | K-RTD2.1 | Vorlauf FBH-EG nach Mischer |
| K-RTD02 | K-RTD2.2 | Ruecklauf FBH-EG |
| K-RTD03 | K-RTD3.1 | Vorlauf Klimakreis-OG nach Mischer |
| K-RTD04 | K-RTD3.2 | Ruecklauf Klimakreis-OG |
| K-RTD05 | K-RTD4.1 | Vorlauf Heizkorper-Backup OG |
| K-RTD06 | K-RTD4.2 | Ruecklauf Heizkorper-Backup OG |
| K-AI01 | K-AI2.1 | Brunnen-Drucksensor 4-20mA, 0-10 bar |
| K-AI02 | K-AI2.2 | Reserve fuer 0-10V/4-20mA |
| K-AI03 | K-AI2.3 | Reserve fuer 0-10V/4-20mA |
| K-AI04 | K-AI2.4 | Reserve fuer 0-10V/4-20mA |
| K-AI05 | K-AI3.1 | Reserve fuer 0-10V/4-20mA |
| K-AI06 | K-AI3.2 | Reserve fuer 0-10V/4-20mA |
| K-AI07 | K-AI3.3 | Reserve fuer 0-10V/4-20mA |
| K-AI08 | K-AI3.4 | Reserve fuer 0-10V/4-20mA |
| K-AI09 | K-AI4.1 | Reserve fuer 0-10V/4-20mA |
| K-AI10 | K-AI4.2 | Reserve fuer 0-10V/4-20mA |
| K-AI11 | K-AI4.3 | Reserve fuer 0-10V/4-20mA |
| K-AI12 | K-AI4.4 | Reserve fuer 0-10V/4-20mA |
| K-AO01 | K-AO2.1 | FU Brunnenpumpe Drehzahlsollwert 4-20mA |
| K-AO02 | K-AO2.2 | Stellsignal Mischer FBH 0-10V |
| K-AO03 | K-AO3.1 | Stellsignal Mischer Klima-OG 0-10V |
| K-AO04 | K-AO3.2 | Stellsignal Mischer Heizkorper-Backup OG 0-10V |
| K-AO05 | K-AO4.1 | Reserve |
| K-AO06 | K-AO4.2 | Reserve |

### 4.4 Modbus-Geraete (separate RS485-Busse ueber Waveshare-Gateways)

**Bus 1 (Heizungsraum, RTU 9600 8N1):** Warmepumpen
- Slave 1: WP1
- Slave 2: WP2

**Bus 2 (Heizungsraum):** BW-WP + Pool-/Filterperipherie
- Slave 10: Brauchwasser-WP
- Slave 11: Pool-/Filtersteuerung (optional; keine eigene Pool-WP)

**Bus 3 (Slave-Steuerung Hauptkeller, RS485-ETH ins VLAN):** Klima-OG
- Slave 20-24: 5x Klima-Innengerate OG

**Bus 4 (Hauptkeller, RTU, Pumpengruppen):** dezentrale Mischerkreis-Platinen
- Slave 30: Pumpengruppe FBH-EG
- Slave 31: Pumpengruppe Klimakreis-OG
- Slave 32: Pumpengruppe Heizkoerper-Backup OG
- Registerentwurf siehe `docs/pumpengruppe-rs485-platine.md`

**Inter-CPU-Kommunikation:**
- Slave-RevPi exponiert seine Werte als Modbus-TCP Server (Port 502)
- Haupt-RevPi pollt periodisch (1 Hz)

## 5. Hydraulik-Schema (vereinfacht, Endausbau)

Siehe [docs/hydraulik.md](docs/hydraulik.md).

## 6. Software-Architektur

### 6.1 Stack-Entscheidung: Python statt OpenPLC
- Heizungsregelung nicht zeitkritisch (Zykluszeit 1-2 s reicht)
- Visu komplett in HA -> keine Web-UI auf RevPi notig
- Einheitliche Code-Basis, leicht zu maintainen, git-versionierbar
- Bibliotheken: `revpimodio2`, `paho-mqtt`, `pymodbus`, `pydantic`

### 6.2 Verzeichnisstruktur
```
/opt/heizung/
├── heizung.py              # Hauptprogramm (asyncio Event-Loop)
├── config/
│   ├── io_map.yaml         # I/O-Kanalbelegung (Single Source of Truth)
│   ├── modbus_map.yaml     # Modbus-Register-Definitionen WP/Klima
│   ├── settings.yaml       # Sollwerte, Heizkurve, Hand-Timeouts
│   └── mqtt.yaml           # MQTT-Topics, HA-Discovery
├── lib/
│   ├── iohw.py             # RevPi-I/O-Wrapper
│   ├── modbus_master.py    # Modbus-RTU/TCP-Master mit Reconnect
│   ├── regler.py           # PI-Regler, Heizkurve, Sequenzlogik
│   ├── mqtt_bridge.py      # MQTT-Client + HA-Discovery + State-Sync
│   ├── failsafe.py         # Watchdog + Fallback-Logik
│   ├── hand_auto.py        # Hand/Auto-Override pro Kanal mit Timeout
│   └── state.py            # Persistierter State (JSON, atomic-write)
├── state/
│   └── state.json
└── deploy/
    └── heizung.service     # systemd-Unit
```

### 6.3 Regelungs-Logik (Hauptregelkreis, 1 Hz)
1. **I/O lesen**: Alle DI/AI von RevPi, alle Modbus-Werte
2. **HA-Anforderungen abrufen** (per MQTT-Subscribe, gecached)
3. **Anforderungsberechnung**:
   - Hoechster geforderter VL aller aktiven Senken am Gesamtwaermekreis + Aufschlag (Mischer-Reserve) = WP-VL-Soll
   - Anforderungen werden nur verarbeitet, wenn die jeweilige Senke in HA/State freigegeben ist
4. **WP-Steuerung** (Sequenz):
   - WP1 und WP2 speisen beide denselben Gesamtwaermekreis; keine feste Zuordnung WP/Haus/Pool
   - Jede Waermequelle hat eine Freigabe: Oelbrenner, WP1, WP2, BWWP
   - Bei kleiner Anforderung: eine WP
   - Bei mehreren aktiven Senken oder hoher Last: beide WPs parallel
   - Wechselrhythmus (alle 24 h) damit Laufzeit gleich verteilt
   - Bei PV-Ueberschuss aus HA/MQTT + Pool unter Maxtemp: Pool vorrangig laden
5. **Mischer-Regelung** (an Slave-CPU):
   - PI-Regler auf Mischer-Vorlauf zu Soll
   - Soll vom Master per Modbus-TCP uebergeben
6. **Hand-Override**: Pro Kanal vor Schreib-Aktion pruefen
7. **MQTT-Publish**: State raus
8. **Failsafe-Watchdog**: HA-Last-Seen Timestamp pruefen

### 6.4 Hand/Auto-Logik
- Pro Kanal in `settings.yaml`: `hand_timeout_min: 240` (oder `null` = nie)
- Hand-Modus: Wert (DO bool, AO 0-100%) wird festgehalten
- Bei Timeout: automatischer Rueckfall auf Auto
- Persistierung: Hand-Stati ueberleben Neustart
- In HA sichtbar: pro Kanal eine Switch-Entitat "Hand-Modus" + Number/Switch fur den Wert

### 6.4.1 Quellen-/Senkenfreigaben

- Jede Waermequelle ist per HA-Schalter freigebbar/sperrbar:
  `oelbrenner`, `wp1`, `wp2`, `bwwp`.
- Jeder Heizkreis bzw. jede Senke ist per HA-Schalter freigebbar/sperrbar:
  `fbh_eg`, `klima_og`, `nebengeb`, `hk_backup`, `pool`.
- Freigaben werden lokal auf dem RevPi in `state/freigaben.json` persistiert.
- Startzustand: Oelbrenner und FBH-EG freigegeben; WP1/WP2/BWWP/Pool/etc.
  gesperrt, bis sie nach Einbau bewusst in HA aktiviert werden.
- So kann der Oelbrenner parallel im System bleiben, bis das Oel leer ist.

### 6.4.2 Brunnenpumpe Konstantdruck (Keller)

- Die Brunnenpumpe sitzt im Keller und bekommt einen Frequenzumrichter.
- Druckmessung: PT-506 Drucksensor, 4-20 mA, 0-10 bar, in der Brunnenleitung.
- Anschluss Drucksensor an Keller-AIO1 / K-AI01:
  - RevPi AIO Input 1 ist in PiCtory auf 4-20 mA parametriert.
  - Fuer Strommessung muss am AIO Input 1 die Bruecke `*` zu `+` gesetzt sein.
  - 2-Leiter-Sensor: +24 V -> Sensor +, Sensor -/Signal -> AIO Input 1 `+`,
    AIO Input 1 `-` -> 0 V.
  - Unter 4 mA meldet die AIO-Karte Range-Fehler; rot blinkende IN-LED ist
    dann erwartbar. Aktuell muss bei 0 bar ca. 4 mA bzw. 4000 uA im Prozessbild
    anliegen.
- Ausgaenge am Keller-RevPi:
  - `brunnen_fu_soll`: Analogausgang 4-20 mA als Drehzahlsollwert zum FU.
    In der Handbedienung entspricht 0 % = 4 mA, 50 % = 12 mA, 100 % = 20 mA.
    Der FU ist am AVI-Eingang so skaliert, dass 0 % Ausgang den FU stoppt.
  - `brunnen_pumpe_freigabe`: optionaler DO als zusaetzliche FU-Run/Freigabe;
    der normale Regel-Stopp erfolgt ueber `brunnen_fu_soll = 0 %`.
- Der vorhandene 100-l-Druckspeicher bleibt im System.
- Durchflusserkennung:
  - Der vorhandene ESPHome-Zaehler `wasserverbrauch-pumpe` misst den aktuellen
    Verbrauch als `Wasserdurchfluss` in L/min und den Gesamtzaehler in Liter.
  - Die Steuerung nutzt fuer die Pumpenabschaltung den Momentanwert, nicht den
    Gesamtzaehler. Der Gesamtzaehler bleibt nur fuer Verbrauchsstatistik.
  - Ziel-Schnittstelle ist lokales Modbus vom ESP32 zur Hauptsteuerung; die
    aktuelle ESPHome-Basiskonfig liegt unter `docs/esphome/wasserverbrauch-pumpe.yaml`.
  - Geplantes Register: Input-Register 0 = `Wasserdurchfluss L/min * 100`,
    z.B. 125 = 1,25 L/min.
- Regelstrategie:
  - Wenn kein Abnehmer offen ist, steigt der Druck bis `brunnen_max_druck_bar`; dann wird abgeschaltet.
  - Falls der Druck diesen Abschaltpunkt wegen Pumpenkennlinie/Bypass nicht erreicht:
    Der Kein-Durchfluss-Timer wird erst aktiv, wenn der Druck im Bereich des
    Regeldrucks liegt (`brunnen_regeldruck_bar` minus Toleranz). Bleibt der
    Flowmeter dann laenger als `brunnen_flow_timeout_s` unter
    `brunnen_flow_min_l_min`, wird ebenfalls abgeschaltet.
  - Bei zu niedrigem Druck laeuft der Kein-Durchfluss-Timer nicht, damit die
    Pumpe trotz Tropfschlauch/kleiner Abnahme Druck aufbauen kann.
  - Im Normalbetrieb wird erst bei Unterschreiten von `brunnen_min_druck_bar`
    gestartet.
  - Wenn ein Abnehmer offen ist, regelt der FU-Sollwert auf `brunnen_regeldruck_bar`.
- In HA einstellbar:
  - `brunnen_min_druck_bar`
  - `brunnen_max_druck_bar`
  - `brunnen_regeldruck_bar`
  - `brunnen_fu_start_pct`
  - `brunnen_fu_max_pct`
  - `brunnen_kp_pct_pro_bar`
  - `brunnen_fu_ramp_up_pct_s`
  - `brunnen_fu_ramp_down_pct_s`
  - `brunnen_flow_min_l_min`
  - `brunnen_flow_timeout_s`
  - `brunnen_flow_stop_tolerance_bar`
  - Startwerte fuer die schnelle mehrstufige Kreiselpumpe: Start 20 %, FU Max
    zunaechst testweise 60-100 %, Kp 25 %/bar, Rampe hoch 25 %/s, Rampe runter 500 %/s. Die Pumpe regelt damit bewusst
    langsam hoch, nimmt aber bei schliessendem Hahn bzw. schlagartigem Druckanstieg
    sehr schnell Leistung weg. Bei Ueberschwingen zuerst Kp senken oder Maxdruck
    knapper setzen; bei zu traegem Druckaufbau Rampe hoch schrittweise erhoehen.
- In HA sichtbar:
  - aktueller Druck
  - FU-Sollwert in %
  - Durchfluss in L/min
  - Zeit ohne Durchfluss in s
  - Restzeit bis zur Flow-Abschaltung in s
  - aktiv/inaktiv
  - Regelgrund (`bereit`, `minderdruck_start`, `regelt`, `maxdruck_erreicht`,
    `kein_durchfluss_stop`, `sensor_unplausibel`)

### 6.5 Failsafe-Verhalten
- **Trigger**: MQTT-Verbindung > 60 s verloren ODER HA-Heartbeat-Topic > 5 min nicht aktualisiert
- **Modus**: Witterungsgefuhrte Heizkurve
  - Default-Kurve: A-12/W45, A0/W38, A+15/W25
  - Bei Sensor-Ausfall: Festwert 50 Grad
- Alle Heizpumpen: AN
- Mischer: Position halten (oder bei 0-10V auf 70%)
- WPs: weiterlaufen mit Failsafe-VL-Soll

### 6.6 Heizkurve & dynamische Kesseltemperatur
- Heizkurve parametrierbar in HA (Number-Entitaten fur Stuetzpunkte)
- Normalbetrieb: WP-VL = max(geforderte_VL_aller_aktiven_Senken_am_Gesamtwaermekreis) + 5 K Mischer-Reserve
- Failsafe: WP-VL = Heizkurve(Aussentemp)
- HA sieht **immer** die aktuelle Ziel-VL

### 6.7 PV-Integration (Phase F)
- PV-Signale kommen direkt aus Home Assistant per MQTT, nicht ueber RevPi-DI:
  - `heizung/pv/ueberschuss/set`: WPs duerfen Pool aufladen ueber Soll, max. 40 Grad
  - `heizung/pv/mangel/set`: WPs auf Sparmodus drosseln (z.B. nur WP1, max. 50% Leistung)
- Logik: Pool wird als thermischer Puffer genutzt
- Der Pool ist dabei eine Senke am gemeinsamen Gesamtwaermekreis, nicht fest einer bestimmten WP zugeordnet.

## 7. MQTT-Topic-Struktur (HA-Discovery)

Broker: `mqtt.esrv.center` mit User `vbnet`/`vbnet` (bereits in HA eingerichtet).

Siehe [docs/mqtt-topics.md](docs/mqtt-topics.md).

## 8. Visualisierung in HA

Eigenes Dashboard `Heizung` mit:
- **Ubersichts-Karte** (Picture-Elements mit Status-Overlays)
- **WP-Karten** je WP: Soll/Ist-VL, Leistung, COP, Laufzeit, Fehler
- **Mischer-Karten** mit Slider + Hand/Auto + Ist-Position
- **Anforderungs-Karte** spiegelt die HA-Heizungsanforderung
- **Pool-Karte** Soll/Ist + PV-Modus
- **Tor-Karte** 4 Buttons + Status + Lichtschranke
- **Heizkurve-Karte** 3 Stuetzpunkt-Slider + Plot
- **Failsafe-Karte** Status + manueller Force-Failsafe-Schalter
- **Freigabe-Karten** fuer Quellen und Senken; nur gesetzte Haken werden durch die Regelung verwendet

Verlaufskurven & History: nativ ueber HA-Recorder + InfluxDB-Add-on.

## 9. Sicherheits- & Hardware-Konzept

- 230 V Lastschalten ausschliesslich ueber Koppelrelais
- WP-Freigaben potentialfrei (Reed-Relais)
- Tor-Steuereingange potentialfrei (Koppelrelais simuliert Taster)
- Lichtschranke hardwareseitig auch direkt an Torantrieb-Sicherheitseingang
- Sensor-Plausibilitat (-20..+95 Grad, Pool +5..+45) -> Out-of-Range = fault
- 2 DI fuer SG-Ready reserviert, Logik aber **inaktiv** (lohnt bei 30 kWp + 100 kWh kaum)

## 10. Phasen-Plan (Reihenfolge)

| Phase | Inhalt | Vorbedingung |
|---|---|---|
| **0 - Vorbereitung** | VLAN 25 + pfSense + UniFi, RevPi #1 ans Netz, PW & SSH-Key, Repo, PiCtory-Config, systemd-Service-Geruest, MQTT-Smoke | RevPi physisch da |
| **A - Ist-Migration Brenner** | Brenner+BW-Pumpe+Tor 1:1 auf RevPi, HA-Anforderung als Auto-Trigger | Phase 0 |
| **B - Slave-Steuerung Keller** | RevPi #2 in Hauptkeller, Mischer FBH/OG-Klima, Modbus-TCP | A stabil |
| **C - Brunnen-Kuhlung** | Brunnenpumpe + WT-Sensoren, Sommerkuhlung freigegeben | B |
| **D - WP-Umbau (Hardware-Tag)** | Brenner raus, 2x 16 kW WP rein, BW-WP rein, alle 3WV-Selektoren, Modbus-RTU zu WPs | WPs beschafft + Heizungsbauer |
| **E - Klima-OG + Pool** | Klima-Innengerate + Pool-Hydraulik + WT + Filter | D, Klima-Modelle beschafft |
| **F - PV-Integration** | HA/MQTT-Signale, PV-Uberschuss-Logik | PV in Betrieb |
| **G - Tuning** | Heizkurve fein, COP-Monitoring, Hand-Timeouts final | im Betrieb |

## 11. Offene Punkte / Risiken

| # | Thema | Entscheidung benoetigt bis |
|---|---|---|
| O1 | WP-Favorit Sunex NEXUS M18 EVI 18 kW pruefen: Modbus-/Linkage-Doku, Lieferumfang, Gewaehrleistung | Vor Phase D |
| O2 | Konkretes Klima-Innengerat-Modell + Modbus-Doku | Vor Phase E |
| O3 | Brauchwasser-WP-Modell | Vor Phase D |
| O4 | 3WV-Stellantriebe: 230V/Auf-Zu mit dezentraler RS485-Pumpengruppen-Platine finalisieren | Vor KiCad/Fertigung |
| O5 | Schaltschrank Slave-Steuerung Hauptkeller Groesse + Lieferant | Vor Phase B |
| O6 | Modbus-Register-Listen sammeln + dokumentieren | je nach Geraet |
| O7 | HK-Backup OG: Eigener Strang oder ueber Klimakreis-OG? | Vor Phase E |
| O8 | Pool-Filterpumpen-Modell (Inverter oder klassisch)? | Vor Phase E |
| O9 | Lichtschranke Modell + Spannung (24V DC bevorzugt) | Vor Phase A |

## 12. Verifikation pro Phase

**Phase 0:**
- `ssh -i ~/.ssh/id_ed25519_heizung pi@10.1.25.10` funktioniert
- Ping aus Standard-LAN klappt nicht (VLAN-Trennung), aus HA-VLAN via FW-Regel ja
- MQTT-Test: `mosquitto_pub -h mqtt.esrv.center ... -t heizung/test -m hallo` -> HA empfaengt

**Phase A:**
- HA-Heizungsanforderung schaltet Brenner ein -> DO01 = HIGH
- Brenner im Failsafe (HA aus): bleibt an wenn AI Aussen < 5 Grad
- Tor "ganz auf" via HA -> Impuls 1000 ms am DO20
- Endschalter "zu" -> DI01 aendert in HA sichtbar
- Lichtschranke NC: DI03=1 zeigt in HA sicher/frei, Unterbrechung DI03=0 zeigt unsicher; Unterbrechung waehrend Tor schliesst: sofortiger Stopp-Impuls

**Phase B:**
- Slave-CPU ping ueber VLAN 25
- Modbus-TCP-Request vom Master liest Mischer-Status
- RS485-Pumpengruppen antworten auf Modbus, schalten Pumpe und fahren Zielposition per Laufzeitlogik an
- Bei Slave-CPU-Crash: Master loggt Verbindungsverlust, faellt auf Failsafe

**Phase D:**
- WP1+WP2 reagieren auf Modbus-Sollwert (mbpoll-Test)
- Sammelstoerung-DI triggert HA-Notification
- Bei manueller WP1-Abschaltung uebernimmt WP2 die Anforderung

**Phase E:**
- Klima-Innengerate schaltbar von HA, Ist-Ventilstellung lesbar
- Sommerkuhlung: Brunnenpumpe + Mischer Klima-OG foerdert kaltes Wasser
- Pool: 3WV schaltet, WP faehrt max. 40 Grad VL, Pool-Ist steigt

**Phase F:**
- PV-Uberschuss-Signal -> Pool-Aufladelogik aktiv (in HA sichtbar)
- PV-Mangel: WP2 gesperrt, WP1 max. 50%

## 13. Bewusst NICHT im Scope
- Eigene Web-Visu auf dem RevPi (HA uebernimmt das)
- OpenPLC / IEC 61131 (Python-Stack stattdessen)
- Pufferspeicher (kein Puffer geplant, Pool ist Pseudo-Puffer)
- Warmemengenzahler/Strommessung (macht HA per Shellys)
- Brauchwasser-Solar / WP-Solar-Kombi (BWWP autark)
- Saunabetrieb (Saunaraum bleibt Lager/unbeheizt)
