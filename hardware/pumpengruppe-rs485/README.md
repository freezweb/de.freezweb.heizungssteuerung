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
- Gerber/Drill/BOM lassen sich per `export-fab.ps1` erzeugen.
- USB-C-Serviceanschluss mit USB-UART-Funktion ist eingeplant.
- ESP32 ist als WROOM-32U/externe Antenne vorgesehen; Antenne sitzt nicht als
  PCB-Antenne auf der Platine.
- Netzteil und Relais sind so platziert, dass die Bauteile den
  MAINS/SELV-Spalt ueberbruecken: Netz-/Kontaktpins links, SELV-/Spulenpins
  rechts.
- RS485-Abschluss ist schaltbar: `R3 = 120R` in Serie mit `JP1`.
- RJ45-Buchsen, RS485-Schraubklemmen und USB-C-Serviceport sind an
  Anschlusskanten mit mehr Abstand platziert, damit Stecker/Kabel nutzbar sind.

Wichtig: RevA ist eine Routing-/Review-Grundlage, noch keine freigegebene
Fertigungsrevision. Vor Fertigung muessen Routing, 230-V-Abstaende,
Relais-/Sicherungsrating, PE-Fuehrung, Leiterbahnbreiten, EMV-Schutz,
Gehaeuseintegration und DRC vollstaendig geprueft werden.

## Export

Nach Installation von KiCad:

```powershell
cd hardware\pumpengruppe-rs485
.\export-fab.ps1
```

Das Skript erzeugt Gerber, Excellon-Drill, BOM und eine ZIP-Datei in `fab/`.
