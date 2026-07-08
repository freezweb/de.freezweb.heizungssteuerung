# Pumpengruppe RS485 KiCad-Projekt

RevA preliminary, Stand 2026-06-25.

Dieses Verzeichnis enthaelt den KiCad-Startentwurf fuer die dezentrale
Pumpengruppen-Platine:

- `pumpengruppe-rs485.kicad_pro`: KiCad-Projekt
- `pumpengruppe-rs485.kicad_sch`: Schaltplan mit lokalen Symbolen
- `pumpengruppe-rs485.kicad_pcb`: PCB-Grundlayout 160 x 110 mm
- `lib/`: lokale Symbole/Footprints
- `export-fab.ps1`: Gerber/Drill/BOM-Export per `kicad-cli`
- `fab/`: Zielordner fuer Fertigungsdaten

Aktueller Stand:

- Schaltplan/PCB laden in KiCad 10.0.4.
- Schaltplan enthaelt jetzt alle im PCB platzierten Hauptbauteile inklusive
  `F1`, `U5`, USB-C/USB-UART und schaltbarem RS485-Abschluss. Die lokalen
  Symbole haben benannte Pins; die Netznamen sind als sichtbare Texte an den
  Funktionspins gesetzt.
- Gerber/Drill/BOM lassen sich per `export-fab.ps1` erzeugen.
- USB-C-Serviceanschluss mit USB-UART-Funktion ist eingeplant.
- UART-Topologie im Schaltplan ist getrennt:
  `U6` USB-UART liegt nur auf ESP-UART0 (`ESP_U0RX`/`ESP_U0TX`) fuer
  Firmware/Debug. `U4` MAX3485 liegt separat auf dem RS485-UART
  (`RS485_UART_RX` = ESP GPIO16, `RS485_UART_TX` = ESP GPIO17,
  `RS485_DE` = ESP GPIO4). Nach dieser Korrektur muss die PCB-Datei in KiCad
  aus dem Schaltplan aktualisiert und das Routing fuer diese Netze neu gezogen
  werden; alte `UART_RX`/`UART_TX`-Routen im PCB duerfen nicht als
  Fertigungsstand gelten.
- ESP32 ist als WROOM-32D mit PCB-Antenne vorgesehen; Antennenseite am
  Platinenrand platzieren und Keepout freihalten.
- Relais werden nicht direkt vom ESP geschaltet: pro Relais sind 100R
  Gatewiderstand, 100k Pulldown, AO3400A-kompatibler NMOS, SS14-Freilaufdiode
  und Status-LED vorgesehen.
- Mischer ist als Hardware-Interlock geplant: `K2` schaltet nur die
  Mischerfreigabe, `K3` ist ein SPDT-Umschaltrelais fuer die Richtung
  `NC=ZU` / `NO=AUF`. Damit koennen AUF und ZU elektrisch nicht gleichzeitig
  gespeist werden.
- Kontrollanzeigen: 230 V diskret auf der Netzseite mit `R40/R41/D40/D41`,
  5 V, 3V3 sowie RS485 TX/RX und die drei Relaisansteuerungen.
- Adressierbare RGB-Anzeige: `D60-D83` sind einheitliche SK6812MINI/3535-5-V-RGB-LEDs
  an `RGB_DATA`/ESP32 GPIO21. `D60-D63` bleiben allgemeine Status-LEDs,
  `D64-D83` bilden den senkrechten Ventilstand-Balken mit 5-%-Schritten;
  die 20er-Leiste ist im 4,8-mm-Raster gesetzt, damit Courtyards nicht kollidieren.
- RTD/ESP-Hinweis: Die beiden MAX31865 haben getrennte Chip-Select-Leitungen
  (`RTD_VL_CS` = GPIO5, `RTD_RL_CS` = GPIO22). Der ESP32-EN-Pin ist ueber
  `R33` als 10-kOhm-Pullup an `+3V3` angebunden.
- Netzteil ist auf ein guenstiges KiCad-Standardfootprint fuer
  `HLK-5M05`/`HLK-5Mxx` umgestellt.
- RS485 ist auf eine guenstige Standardtransceiver-Schaltung umgestellt:
  `U4` = MAX3485/SP3485-Klasse im SOIC-8 mit getrennten UART-Netzen zum ESP,
  `RS485_DE` vom ESP fuer DE/RE.
- Ueberspannungsschutz auf der Netzseite ist diskret vorgesehen:
  `RV1` als 275-VAC-MOV zwischen L und N.
- RJ45 Pin 1/2 fuehren `BUS_5V`, Pin 7/8 `COM`; `F2` schuetzt die 5V-Kopplung
  mit PTC, `R32` koppelt COM auf lokale 0V fuer RJ45-Power-Sharing.
- Es gibt zwei Bestueckungsvarianten fuer dieselbe Leiterplatte:
  - Vollausbau Pumpengruppe: `pumpengruppe-rs485-bom.csv` und
    `pumpengruppe-rs485-pick-place.csv`.
  - Temperatur-/RS485-Variante: `pumpengruppe-rs485-bom-tempinput.csv` und
    `pumpengruppe-rs485-pick-place-tempinput.csv`; dabei bleibt der linke
    230-V-/Relaisbereich unbestueckt und die Versorgung erfolgt ueber
    `BUS_5V`/RJ45.
- Die Breakaway-Variante ist im Board sichtbar umgesetzt: `MB1` setzt
  0,7-mm-NPTH-Mousebites in die oberen und unteren Materialstege des
  vorhandenen Isolationsschlitzes. Zusaetzlich bleibt die
  `Dwgs.User`-/Silkscreen-Markierung fuer die Bestueckungsvariante erhalten.
- Netzteil und Relais sind so platziert, dass die Bauteile den
  MAINS/SELV-Spalt ueberbruecken: Netz-/Kontaktpins links, SELV-/Spulenpins
  rechts.
- RS485-Abschluss ist schaltbar: `R3 = 120R` in Serie mit `JP1`. `JP1` ist
  ein 1x3-Header, damit der Jumper am Geraet bleiben kann:
  `1-2 = Abschluss aktiv`, `2-3 = Parkposition/Aus`.
- RJ45-Buchsen und USB-C-Serviceport sind an die Unterkante gesetzt und zeigen
  zur Kante, damit Stecker/Kabel nutzbar sind. RS485-Schraubklemmen bleiben an
  der rechten Anschlusskante. J3/J4 sind auf dem Silkscreen mit A/B/GND
  beschriftet; am unteren Rand steht das RJ45-Pinout
  `1/2=5V 3/6=NC 4=A 5=B 7/8=GND`.
- KiCad-Netclasses sind in `pumpengruppe-rs485.kicad_pro` gesetzt:
  `230V` routet L/N/geschaltete 230-V-Lastnetze und PE mit 1,5 mm und
  0,8 mm Clearance innerhalb der 230-V-Netze. Fuer die 5-A-Sicherung sollte die
  Bestellung mit mindestens 70 um / 2 oz Kupfer angefragt werden oder die
  tatsaechliche Last/Sicherung entsprechend reduziert werden. Die 8-mm-Trennung
  zwischen 230 V und SELV bleibt als physische Keepout-/Fraesnut-Regel beim
  Layout zwingend einzuhalten.
- Die Netclasses fuer weitere Power-Routings sind gesetzt:
  `SELV_POWER_0V8` fuer `+5V`, `BUS_5V`, `USB_VBUS`, `GND` und `RS485_GND`;
  `Doppelte Dicke` mit 0,4 mm fuer `+3V3`. Auf der RGB-/Temp-Input-Seite sind
  erste vorhandene 5-V-/GND-Segmente real auf 0,8 mm und 3V3-Segmente auf
  0,4 mm verbreitert. Einige Engstellen an USB/RJ45 bleiben bewusst 0,2 mm,
  weil breitere Leiterbahnen dort DRC-Kurzschluesse erzeugen wuerden. Fuer die
  finale Serienplatine sollten diese Netze weiter gezielt als breite
  Versorgungsstaemme bzw. Kupferflaechen nachgezogen werden.

Wichtig: RevA ist elektrisch geroutet und hat keine offenen Netze im KiCad-DRC.
Vor einer Netzspannungs-Freigabe bleiben trotzdem Relais-/Sicherungsrating,
PE-Fuehrung, Gehaeuseintegration, Beruehrschutz, EMV-Schutz und die
Herstellerfreigabe fuer 230-V-Abstaende zu pruefen. Wenn die RJ45-5V-Weitergabe
bestueckt/genutzt wird, ist die RS485-/SELV-Masse gemeinsam; das
Isolationskonzept muss dann als gemeinsamer SELV-Bus bewertet werden.

## Export

Nach Installation von KiCad:

```powershell
cd hardware\pumpengruppe-rs485
.\export-fab.ps1
```

Das Skript erzeugt Gerber, Excellon-Drill, beide BOM-Varianten, beide
Pick-and-Place/XY-Dateien und eine ZIP-Datei in `fab/`.
