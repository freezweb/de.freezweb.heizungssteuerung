# AISLER Anfrage - Pumpengruppe RS485 RevA

Projekt: `pumpengruppe-rs485`

Ziel der Anfrage:
- Angebot fuer Leiterplatte und Bestueckung der aktuellen RevA einholen.
- Zunaechst Prototyp-/Kleinserie, Stueckzahl bitte im AISLER-Portal variieren.
- Bitte als Machbarkeits-/Kostenanfrage behandeln, nicht ohne Ruecksprache in Serienfertigung geben.

Empfohlener Upload:
1. `pumpengruppe-rs485-aisler-native-kicad.zip`
   - KiCad-10-Projekt mit lokalen Symbolen und Footprints.
   - AISLER unterstuetzt KiCad nativ; das ist fuer BOM/PnP-Erkennung meist am besten.
2. Falls noetig zusaetzlich `pumpengruppe-rs485-aisler-gerber-drill.zip`
   - Klassische Gerber-/Excellon-Fertigungsdaten.
3. Fuer Assembly die CSV-Dateien unter `assembly/` nutzen.
   - Wichtig: `pumpengruppe-rs485-aisler-mpn-bom.csv` ist die bevorzugte AISLER-BOM mit Hersteller- und MPN-Feldern.
   - `pumpengruppe-rs485-component-review.csv` enthaelt die wenigen Positionen, bei denen Footprint/Spannungsfestigkeit vor einer echten Bestellung noch bestaetigt werden muessen.

Varianten:
- `pumpengruppe-rs485-aisler-mpn-bom.csv` + `pumpengruppe-rs485-pick-place.csv`
  = volle Pumpengruppen-Variante mit 230V-/Relais-/Pumpen-/Mischerbereich.
- `pumpengruppe-rs485-bom-tempinput.csv` + `pumpengruppe-rs485-pick-place-tempinput.csv`
  = Bestueckungsvariante fuer reine Temperatur-/RS485-Eingangskarte, linker 230V-Teil nicht bestueckt.
- PSU1 ist auf Mean Well IRM-05-5 umgeplant und soll in der vollen Pumpengruppen-Variante von AISLER bestueckt werden. Bitte Footprint, Verfuegbarkeit und 230V-Abstaende vor Freigabe bestaetigen.

Wichtige Rueckfragen an AISLER:
- 230V-Bereich, Relais, Netzteil und Schraubklemmen bitte gegen VDE-/Kriechstreckenanforderungen pruefen.
- Bitte klaeren, welche THT-Teile automatisch/manuell bestueckbar sind.
- Bitte Ersatztypen fuer Relais, Klemmen, RJ45, USB-C und PSU1 / IRM-05-5 vor Freigabe bestaetigen.
- D50/D51/D52 sind optionale RS485-TVS-Reserveplaetze und in der Basisbestueckung DNP; bitte nicht bestuecken.
- X3 ist ein 4-poliger 7,62-mm-Netz-/Mischeranschluss. Bitte nicht durch eine 5,08-mm-Klemme ersetzen; MPN/Footprint muessen vor Fertigung mechanisch zusammenpassen.
- Relais K1/K2/K3 und RTD-ICs U2/U3 sind in der Review-Liste bewusst als Footprint-Pruefung markiert.
- R40/R41 sind 230V-LED-Vorwiderstaende; Spannungsfestigkeit, Verlustleistung und Kriechstrecke vor Freigabe pruefen.
- Bitte Positionen/Rotationen im Assembly-Viewer pruefen, insbesondere RJ45, USB-C, Relais, ESP32 und SK6812MINI.
- Die DRC-/ERC-Reports liegen bei. Aktueller Stand enthaelt noch Warnungen/Verstoesse und Schaltplan-/PCB-Paritaetsmeldungen; vor einer echten Produktionsfreigabe muessen diese gemeinsam bewertet bzw. bereinigt werden.

Board-Hinweise:
- 2-Lagen PCB.
- Mains/SELV-Trennung und Bruchkante/Bestueckungsvariante sind Bestandteil des aktuellen Layoutstands.
- RJ45 fuehrt RS485 sowie BUS_5V/BUS_COM fuer Daisy-Chain-Versorgung.
- RS485-Abschluss ueber 1x3-Jumper: 1-2 = Abschluss aktiv, 2-3 = Parkposition.
