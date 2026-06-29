# PV- und Waermepumpen-Kalkulation

Stand: 2026-06-29

Diese Datei fasst die von dir als Screenshot gelieferte Grobkalkulation
zusammen und markiert die Punkte, die fuer eine belastbare Planung noch fehlen.
Das Angebot des Elektrikers enthaelt laut aktuellem Stand die PV-Module und das
Untergestell fuer 65x 455 Wp, also 29,575 kWp, plus einen Zaehlerschrank.

Quelle der Kostenpositionen: Screenshot der bisherigen Kalkulation vom
2026-06-27. Die folgenden Tabellen sind aus diesem Bild uebernommen und nur
formal bereinigt.

Link-Regel fuer diese Datei: Jede Kaufposition bekommt einen konkreten
Artikel-, Hersteller- oder Angebotslink mit Preisstand. Reine Suchlinks werden
nicht als Position gefuehrt. Wenn eine Position noch nicht konkret genug ist,
wird sie in kleinere, bestellbare Einzelartikel aufgeloest.

## Zielbild

- PV-Anlage: 29,575 kWp aus dem GSB-Angebot, optional erweiterbar ueber
  PV-Zaun und weitere Flaechen.
- Batteriespeicher: Grundausstattung 8x 16s, ca. 128,6 kWh LiFePO4,
  Erweiterung mechanisch und elektrisch vorbereitet bis 16x 16s,
  ca. 257,2 kWh nominal.
- Wechselrichter-/ESS-Konzept: Victron-basiert mit 6x MultiPlus-II 48/8000,
  3-phasig, je Phase 2 Geraete parallel.
- Waermeerzeugung: 2 Waermepumpen mit je ca. 18 kW plus separate
  Warmwasser-Waermepumpe.
- Steuerung: PV-Ueberschuss und PV-Mangel werden in Home Assistant gebildet und
  per MQTT an die Heizungssteuerung uebergeben.

## Kostenuebersicht

### PV, Speicher und Elektro

| Position | Link / Quelle | Anschluesse / Bemerkung | Anzahl | Einzelpreis | Gesamt |
|---|---|---:|---:|---:|---:|
| Victron VM-3P75CT optionaler Kontroll-/Unterzaehler | https://www.victronenergy.com/meters-and-sensors/energy-meter | Nicht fuer ESS-Regelung noetig, wenn wirklich alle Lasten und AC-PV auf AC-out liegen | 0 | 120,59 EUR | 0,00 EUR |
| Lynx Distributor | https://www.victronenergy.com/dc-distribution-systems/lynx-distributor | 4 | 3 | 141,95 EUR | 425,85 EUR |
| MPPT RS 450/200 MC4 | https://www.victronenergy.com/solar-charge-controllers/smartsolar-mppt-rs-450-tr | 4 | 3 | 1.365,95 EUR | 4.097,85 EUR |
| MultiPlus-II 48/6k5/100-50 | https://www.victronenergy.com/inverters-chargers/multiplus-ii | 2 | 3 | 649,00 EUR | 1.947,00 EUR |
| Ekrano GX | https://www.victronenergy.com/communication-centres/ekrano-gx | 1 | 1 | 397,95 EUR | 397,95 EUR |
| Victron MEGA-fuse 300A/58V, Set 5 Stk. | https://www.offgridtec.com/en/victron-300a-80v-mega-fuse-fuse-set-of-5.html | 5 Stk./Pack, 48-V-tauglicher Ersatz fuer alte 500-A-Position | 3 | 38,44 EUR | 115,32 EUR |
| Batteriespeichergehaeuse | siehe Einkaufskandidaten unten, Startlink: https://www.alibaba.com/product-detail/PL-Stock-DIY-15kWh-Solar-Storage_1601636254158.html | 16 | 6 | 86,91 EUR | 521,46 EUR |
| EVE MB31 Batteriezelle 314 Ah | https://www.alibaba.com/product-detail/8000-Cycles-V3-EU-Stock-3_1601244515922.html | 1 | 99 | 48,28 EUR | 4.779,72 EUR |
| Kleinmaterial DC-Verkabelung | Detailpositionen siehe DC-Verteilung/Kleinmaterial: H07V-K, Rohrkabelschuhe, Schrumpfschlauch, Beschriftung, Potentialausgleich | pauschal | 1 | 500,00 EUR | 500,00 EUR |
| Kleinmaterial AC-Verkabelung | Startpaket aus Artikelregister: NYM-J/NYY-J 5x10/5x16, Hager SLS/RCD, Verteilerzubehoer; Mengen nach AC-Schema | pauschal | 1 | 1.000,00 EUR | 1.000,00 EUR |
| Angebot GSB ANG-2026-19, PV-Material + Zaehlerschrank | lokale Quelle: `C:/Users/Danie/Downloads/Angebot-GSB-ANG-2026-19-Eschenlohre-28-03-2026.pdf` | 29,575 kWp + Schrank | 1 | 14.202,94 EUR | 14.202,94 EUR |
| **Zwischensumme PV/Speicher/Elektro** |  |  |  |  | **27.988,09 EUR** |

### Waermepumpen und Heizung

| Position | Link / Quelle | Anzahl | Einzelpreis | Gesamt |
|---|---|---:|---:|---:|
| Sunex NEXUS M18 EVI 18 kW Monoblock | https://preisvergleich.heise.de/sunex-nexus-m18-evi-420-000-518-a3338154.html | 2 | 2.599,99 EUR | 5.199,98 EUR |
| Warmwasser-Waermepumpe AEG WPT 300 EL, 300 l | https://www.hornbach.de/p/warmwasser-waermepumpe-aeg-300-l-wpt-300-el/6668689/ | 1 | 2.099,00 EUR | 2.099,00 EUR |
| Kleinmaterial Heizung | Startpaket aus Artikelregister/Heizungsplanung: Pumpengruppen, Mischer, Rohr/Fittinge, Sicherheitsgruppe, Magnetitabscheider, Daemmung | 1 | 1.500,00 EUR | 1.500,00 EUR |
| **Zwischensumme Waerme/Heizung** |  |  |  | **8.798,98 EUR** |

**Grobe Gesamtsumme bisher:** 36.787,07 EUR

## Elektrikerangebot GSB ANG-2026-19

Quelle: Angebot `GSB ANG-2026-19` vom 2026-03-28 fuer BV Parkstrasse 5,
19309 Lanz. Das Angebot erklaert die Position aus der Ursprungskalkulation
ueber 14.202,94 EUR.

| Pos. | Inhalt | Betrag |
|---|---|---:|
| 001 | PV-Anlage 29,575 kWp: Module mit Schienensystem, Stringverkabelung, PV-Stecker und Kupplungen liefern; 65x PV-Modul 455 Wp; Schienensysteme fuer 5 Daecher: Sueddach Scheune, 2x Gaube Sued, Ostdach Wohnhaus, Westdach Wohnhaus; Befestigung mit Dachhaken, Schienensystem 1-lagig | 12.764,11 EUR |
| 002 | Wandschrank 7-reihig 800x1100 BxH, SKII IP44, Zaehlerschrank; 3-feldrig mit einem Zaehlplatz, APZ/Verteilerfelder, SLS 63 A 3-polig, SPD Typ 1+2+3, Hauptschalter 63 A | 1.209,10 EUR netto / 1.438,83 EUR brutto |
| Summe | Nettobetrag 13.973,21 EUR, 0 % MwSt. auf PV-Anteil, 19 % MwSt. 229,73 EUR auf steuerpflichtigen Anteil | 14.202,94 EUR |

Rechenwerte:

- 65 x 455 Wp = 29,575 kWp.
- PV-Materialposition: ca. 431,58 EUR/kWp.
- Gesamtangebot inkl. Zaehlerschrank: ca. 480,23 EUR/kWp.
- Anzahlung laut Angebot: 2.840,59 EUR.

Abgrenzung / offene Punkte:

- Der Wortlaut nennt bei der PV-Position ausdruecklich "liefern". Montage,
  Geruest/Steiger, AC-Anschluss, Anmeldung, Inbetriebnahme, Pruefprotokoll und
  finaler Stringplan sind im Angebot nicht eindeutig als enthalten erkennbar.
- Das Angebot enthaelt keine Wechselrichter, keinen Speicher, keine MPPTs,
  keine Victron-Komponenten und keine Notstrom-/AC-out-Rueckleitung.
- Die angebotenen Dachflaechen sind: Scheune Sued, zwei Sued-Gauben,
  Wohnhaus Ost und Wohnhaus West.

## Recherche und Annahmen 2026-06-27

Fuer USD-Positionen wurde der EZB-Referenzkurs vom 2026-06-26 verwendet:
1 EUR = 1,1401 USD. USD-Preise sind damit nur Planwerte, weil Alibaba-Preise
fuer Versand, DDP, Zoll, Umsatzsteuer, Zertifikate und Mengenstaffeln final
immer angefragt werden muessen.

Wichtige Quellen:

- Victron MultiPlus-II technische Daten:
  https://www.victronenergy.com/media/pg/MultiPlus-II_230V/en/technical-specifications-mp-ii-230v.html
- Victron MultiPlus-II Installationshandbuch, DC-Sicherungen und Kabel:
  https://www.victronenergy.com/upload/documents/MultiPlus-II_230V/32424-MultiPlus-II___Quattro-II-pdf-en.pdf
- Victron MPPT RS 450/200 technische Daten:
  https://www.victronenergy.com/media/pg/SmartSolar_MPPT_RS/en/technical-specifications.html
- Victron ESS Konfiguration / Grid Setpoint:
  https://www.victronenergy.com/media/pg/Energy_Storage_System/en/configuration.html
- EZB USD/EUR Referenzkurs:
  https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-usd.en.html
- Polestar 4 AC-Laden bis 22 kW mit passender Option:
  https://www.polestar.com/en-ae/polestar-4/range-and-charging/

### Artikelregister / Wiederfinde-Links

Diese Liste ist bewusst praktisch gehalten: exakte Artikel mit Preisstand.
Preisstand: 2026-06-29, sofern nicht anders vermerkt. Versand, DDP/Zoll und
Mengenstaffeln muessen vor Bestellung final bestaetigt werden.

| Bereich | Artikel / Position | Preisstand | Link |
|---|---|---:|---|
| Messung optional | Victron VM-3P75CT Kontroll-/Unterzaehler | 120,59 EUR Planpreis, nicht in Basissumme | https://www.victronenergy.com/meters-and-sensors/energy-meter |
| DC-Verteilung | Victron Lynx Distributor M10 LYN060102010 | 193,24 EUR netto bei SVB | https://www.svb24.com/en/p/victron-lynx-distributor-m10.html |
| PV-Laderegler | Victron SmartSolar MPPT RS 450/200 MC4 | 1.365,95 EUR Planpreis | https://www.victronenergy.com/solar-charge-controllers/smartsolar-mppt-rs-450-tr |
| PV-Restmodule | Victron SmartSolar MPPT 250/60-MC4, SCC125060321 | 442,73 EUR bei Reichelt IE | https://www.reichelt.com/ie/en/shop/product/smartsolar_mppt_250_60-mc4_solar_charge_controller-377566 |
| Wechselrichter | Victron MultiPlus-II Serie, Ziel 48/8000/110-100 | 6x 8000 zusammen ca. 6.563 EUR Planpreis | https://www.victronenergy.com/inverters-chargers/multiplus-ii |
| Steuerung | Victron Ekrano GX | 397,95 EUR Planpreis | https://www.victronenergy.com/communication-centres/ekrano-gx |
| ESS-Konfiguration | Victron ESS / Grid Setpoint | Dokumentation | https://www.victronenergy.com/media/pg/Energy_Storage_System/en/configuration.html |
| Batterie-Zellen | Heymy/E-V-E MB31 314Ah | 45 USD/Zelle bei 4-299 Stk. | https://www.alibaba.com/product-detail/8000-Cycles-V3-EU-Stock-3_1601244515922.html |
| Batterie-Gehaeuse billigstes Listing | Senloong 16s/314Ah, angeblich JK-BMS | 98 USD/Stk., MOQ widerspruechlich | https://www.alibaba.com/product-detail/DIY-JK-200A-BMS-Kit-LifePo4_1601407114794.html |
| Batterie-Gehaeuse leer | ASGOFT 16S DIY Box | 154,85 USD/Stk. bei 1-19 Sets | https://www.alibaba.com/product-detail/PL-Stock-DIY-15kWh-Solar-Storage_1601636254158.html |
| Batterie-Gehaeuse mit BMS | BetterESS 16S V19 JK 200A | 350 USD/Stk. bei 1-9 Stk. | https://www.alibaba.com/product-detail/BetterESS-DIY-51-2V-16S-280_1601804474500.html |
| Batterie-Gehaeuse mit BMS | EEL 16S JK V19 / Fuse Varianten | 119 bis 389 USD/Stk. | https://www.alibaba.com/product-detail/eel-lifepo4-48v-16s-diy-lifepo4_1601189967394.html |
| Batterie-Gehaeuse mit BMS | Fench/Fengchi JK V19 PB2A16S20P | 432,25 USD/Stk. bei 1-49 Sets | https://www.alibaba.com/product-detail/DIY-Battery-Box-with-JK-V19_1601430152850.html |
| Batterie-Gehaeuse leer | Yixiang 16S Box ohne BMS/Zubehoer | 99 USD/Stk. bei 1-49 Stk. | https://www.alibaba.com/product-detail/YIXIANG-48V-Diy-Kit-Battery-Box_1601109499628.html |
| PV-Module 500 W | JA Solar 500 W bifazial Glas-Glas Full Black JAM60D41 LB | 74,90 EUR/Stk. Palettenpreis | https://solarhandel24.de/products/ja-solar-500w-bifazial-glas-glas-full-black-jam60d41-lb-staffelpreis |
| PV-Module 450/460 W | JA Solar 460 W bifazial Glas-Glas Black Frame | 64,90 EUR/Stk. Palettenpreis | https://solarhandel24.de/collections/ja-solar |
| Elektrikerangebot | GSB ANG-2026-19 lokale PDF | 14.202,94 EUR | `C:/Users/Danie/Downloads/Angebot-GSB-ANG-2026-19-Eschenlohre-28-03-2026.pdf` |
| Waermepumpe | Sunex NEXUS M18 EVI 18 kW Monoblock | 2.599,99 EUR ab Heise/Preisvergleich | https://preisvergleich.heise.de/sunex-nexus-m18-evi-420-000-518-a3338154.html |
| Warmwasser-WP | AEG WPT 300 EL, 300 l | 2.099,00 EUR bei Hornbach | https://www.hornbach.de/p/warmwasser-waermepumpe-aeg-300-l-wpt-300-el/6668689/ |
| Warmwasser-WP Alternative | Environ AquaBoost A+ 300 L R290 | 2.199,99 EUR bei Waermeheld | https://waerme-held.de/products/aquaboost-a-brauchwasserwarmepumpe-300-l-bodenstehende-warmepumpe-mit-r290 |
| Manueller Wartungs-Bypass | Hager SF463 Changeover Switch 4P 63A I-0-II | 80,57 EUR bei Gabby Electric | https://gabbyelectric.com/products/sf463-hager-changeover-switch-4p-63a-i-0-ii |
| AC-Kabel | NYM-J 5x16 mm2, 50 m Ring | 754,13 EUR bei Ekabel24 | https://www.ekabel24.de/en/nym-j-5x16-mm2-sheathed-cable-50m-rm/nymj05160-50 |
| AC-Kabel Alternative | NYM-J 5x10 mm2, 50 m Ring | 351,59 EUR bei Ekabel24 | https://www.ekabel24.de/en/nym-j-5x10-mm2-sheathed-cable-50m/nymj05100-50 |
| AC-SLS | Hager HTS363E SLS-Schalter 63A 3-polig | 79,77 EUR bei Idealo-Preisstand | https://www.idealo.de/preisvergleich/OffersOfProduct/3353346_-hts363e-hager.html |
| AC-RCD | Hager CDS463D FI-Schalter 4-polig 63A 30mA Typ A | 79,50 EUR bei Idealo-Preisstand | https://www.idealo.de/preisvergleich/OffersOfProduct/1191287_-fi-schutzschalter-4p-63a-30ma-cds463d-hager.html |
| DC-Sicherungen | Victron MEGA-fuse 300A/58V, Set 5 Stk. | 38,44 EUR bei Offgridtec | https://www.offgridtec.com/en/victron-300a-80v-mega-fuse-fuse-set-of-5.html |
| DC-Kabel | H07V-K 95mm2 schwarz Meterware | 17,59 EUR/m bei Elanto24 | https://www.elanto24.de/H07V-K-95mm2-PVC-Verdrahtungsleitung-feindraehtig-schwarz-Meterware |
| Rohrkabelschuhe | Kalitec HR95-10 Rohrkabelschuh 95mm2 M10 | 3,32 EUR/Stk. | https://www.kabelschuhe-shop.de/Kalitec-HR95-10-Commercial-tubular-cable-lug-95mmA-M10 |
| Schrumpfschlauch | 142-teilig 3:1 mit Kleber, schwarz/rot | 7,99 EUR bei ERH-Shop | https://erh-shop.de/Schrumpfschlauch-Sortiment-142-teiligPlastikbox-klebend-Ratio-3-1-schw-rot/4250416329264 |
| Potentialausgleich | OBO Bettermann 1809 Potentialausgleichsschiene | 7,14 EUR bei Hornbach | https://www.hornbach.de/p/obo-bettermann-1809-potentialausgleichsschiene-grau-188-mm/5007388/ |

## Speicher-Topologie

Die bisherige Kalkulation mit 99 EVE-Zellen zu 314 Ah passt elektrisch nicht zu
6 gleichen 16s-Packs, weil 6 Packs exakt 96 Zellen benoetigen.

- 1 Pack: 16s LiFePO4, 51,2 V nominal, 314 Ah, ca. 16,1 kWh nominal.
- 6 Packs: 96 Zellen, ca. 96,5 kWh nominal.
- 99 Zellen: ca. 99,5 kWh nominal, davon 3 Zellen als Reserve sinnvoll.
- Realistisch nutzbar: ca. 75 bis 85 kWh, wenn SoC-Fenster, Reserve,
  Alterung und Wechselrichterverluste beruecksichtigt werden.

Empfohlen wird nicht ein grosses gemeinsames BMS, sondern eigenstaendige
16s-Packs mit je eigenem BMS. Die Grundausstattung wird mit 8 Packs geplant.
Mechanisch, elektrisch und in der Victron/Lynx-DC-Verteilung soll die Anlage
aber auf 16 Packs vorbereitet werden. Die Packs werden als Batteriegruppen
parallel auf einen gemeinsamen 48-V-DC-Bus gefuehrt. Dadurch bleibt jeder Block
wartbar und bei einem Packfehler kann der Rest der Anlage kontrolliert
weiterlaufen.

### Speicher-Einkaufskandidaten

| Position | Kandidat / Link | Preis Recherche | Ansatz EUR | Bewertung |
|---|---|---:|---:|---|
| EVE MB31 314 Ah Zellen | Alibaba Suche / EVE MB31, z.B. https://www.alibaba.com/product-detail/EVE-MB31-314ah-3-2V-lifepo4_1601092451357.html | ca. 58,80 bis 76,66 USD/Zelle | 96 Stk. ab ca. 4.951 EUR, 99 Stk. ab ca. 5.106 EUR | Alter Screenshotpreis 48,28 EUR/Zelle ist sehr sportlich, aber nicht voellig unmoeglich bei Sammel-/DDP-Deal. |
| Gewaehlte Zelloption 2026-06-29 | https://www.alibaba.com/product-detail/8000-Cycles-V3-EU-Stock-3_1601244515922.html | 45 USD/Zelle bei 4-299 Stk., 43 USD ab 300 Stk. | 128 Stk. ca. 5.052 EUR vor Versand/Zoll/DDP | E-V-E/MB31 314 Ah, CE/UN38.3/MSDS, laut Listing Busbars/Bolzen enthalten. Sehr guter Preis, aber Grade-A, QR-Codes, Testprotokolle und DDP schriftlich bestaetigen. |
| Billigstes gefundenes Gehaeuse-Listing | https://www.alibaba.com/product-detail/DIY-JK-200A-BMS-Kit-LifePo4_1601407114794.html | 98 USD/Stk. | 8 Stk. ca. 688 EUR vor Versand/Zoll/DDP | Senloong 16s/314Ah, laut Listing JK-BMS und `Battery Management System: Y`. Aber: oben MOQ 50, weiter unten MOQ 5. Nur als Anfragekandidat, nicht blind bestellen. |
| Billigste leere Box / bisherige Favoritin | https://www.alibaba.com/product-detail/PL-Stock-DIY-15kWh-Solar-Storage_1601636254158.html | 154,85 USD/Set bei 1-19 Stk. | 8 Stk. ca. 1.087 EUR vor Versand/Zoll/DDP | ASGOFT 16S DIY-Box, Polen-Stock/5-day laut Listing, 704x408x232 mm, fuer 16 Zellen 208x174x72 mm. Achtung: Listing widerspruechlich beim BMS, deshalb als ohne BMS planen. |
| Billigste Box mit klarerem JK-BMS ab MOQ 1 | https://www.alibaba.com/product-detail/BetterESS-DIY-51-2V-16S-280_1601804474500.html | 350 USD/Stk. bei 1-9 Stk. | 8 Stk. ca. 2.456 EUR vor Versand/Zoll/DDP | BetterESS 16s fuer 280-314Ah, V19 JK 200A BMS laut Titel/Variante. Preislich aktuell der beste brauchbare BMS-Kandidat, wenn Lieferumfang schriftlich passt. |
| EEL 16s DIY Box mit JK BMS | https://www.alibaba.com/product-detail/eel-lifepo4-48v-16s-diy-lifepo4_1601189967394.html | 119 bis 389 USD/Stk. | 8 Stk. bei 389 USD ca. 2.729 EUR | Gute Standardoption: 16 Zellen, JK PB2A16S20P, 200 A, V6 pro JK V19+Fuse-Variante pruefen. |
| Fench/Fengchi 16s Box mit JK V19 | https://www.alibaba.com/product-detail/DIY-Battery-Box-with-JK-V19_1601430152850.html | 432,25 USD/Stk. bei 1-49 Stk. | 8 Stk. ca. 3.033 EUR | Teurer, aber sehr klarer Lieferumfang: JK V19 PB2A16S20P, CAN/RS485/RS232, 250-A-Breaker, Display, Fireproof Device. |
| Yixiang 16s Box, extrem billig aber leer | https://www.alibaba.com/product-detail/YIXIANG-48V-Diy-Kit-Battery-Box_1601109499628.html | 99 USD/Stk. bei 1-49 Stk. | 8 Stk. ca. 695 EUR | Auf den ersten Blick billig, aber ausgewaehlte Variante im Listing lautet `without BMS and accessories`. Nur relevant, wenn wir BMS, Display, Sicherung, Kabelsatz separat wirklich billiger bekommen. |
| Seplos / Mason 16s DIY Kit | Alibaba/Seplos Recherche, z.B. https://www.seplos.com/optimizing-solar-energy-discover-the-seplos-mason-48v-314ah-battery-for-home-energy-storage.html | Anbieterabhaengig | offen | Oft bessere Victron-Kompatibilitaet als No-Name-BMS, Preis anfragen. |
| Komplettakku 51,2 V / 314 Ah | Alibaba Benchmark, z.B. GTK 51,2 V 314 Ah 200 A Pack | ca. 1.149 USD/Pack | 6 Stk. ca. 6.047 EUR | Klingt guenstig, aber Qualitaet, Zelltyp, DDP, Garantie und Zertifikate besonders genau pruefen. |
| AliExpress | Suche nach MB31/JK/Seplos | keine belastbar bessere Quelle gefunden | offen | Fuer Einzelteile okay, fuer 96 bis 99 Zellen eher Alibaba/Hersteller direkt anfragen. |

### Batteriegehaeuse-Empfehlung nach Billig-Suche

Stand 2026-06-29: Das billigste gefundene Alibaba-Listing ist Senloong mit
98 USD pro 16s-Gehaeuse und angeblichem JK-BMS. Das ist rechnerisch brutal gut,
aber wegen widerspruechlicher Mindestmenge und sehr niedrigem Preis nur als
Anfragekandidat zu behandeln. Wenn Senloong schriftlich bestaetigt, dass 8
Stueck lieferbar sind und wirklich JK-BMS, Display, Sicherung/Breaker,
Busbars/Kabelsatz, CAN/RS485 und DDP-Versand enthalten sind, waere das die
billigste Variante.

Wenn Senloong nicht sauber bestaetigt, ist die billigste sinnvolle Planung:

1. **ASGOFT leer + separates JK-BMS**, wenn wir selbst mehr verdrahten und
   Sicherung/Breaker/Kommunikation separat kontrollieren wollen.
2. **BetterESS V19 JK 200A**, wenn wir die billigste klarere Box mit BMS ab
   MOQ 1 wollen.
3. **EEL V6 pro JK V19+Fuse**, wenn der Lieferant die Victron-Kommunikation,
   Sicherung und den Lieferumfang besser bestaetigt als BetterESS.

Anfrage an alle Kandidaten muss exakt lauten:

- 8x 51,2-V-16s-DIY-Box fuer EVE/MB31 314Ah Zellen, Zellmass ca.
  72 x 173 x 203 mm.
- JK PB2A16S20P oder gleichwertig, 200 A Dauerstrom, aktiver Balancer.
- CAN und RS485, Victron-Kompatibilitaet, Protokoll/Dokumentation.
- Display, Temperatursensoren, Hauptsicherung oder DC-Breaker, Precharge,
  Busbars, Kabelsatz, Schrauben, Isolierungen.
- DDP nach Deutschland, EU-Lager falls moeglich, Lieferzeit, Garantie,
  CE/UN38.3/MSDS fuer relevante Teile.
- Schriftlich klaeren, ob der angezeigte Preis fuer genau diese Variante gilt
  oder nur fuer leeres Gehaeuse/Pallet/Zubehoer.

### Konkrete Batterieplanung mit Heymy-Zellen und ASGOFT-Gehaeuse

Die aktuelle Planung basiert auf 16s-Packs mit EVE/MB31 314-Ah-Zellen. Ein
Pack besteht aus 16 Zellen:

- 16 x 3,2 V = 51,2 V nominal.
- 16 x 3,2 V x 314 Ah = ca. 16,08 kWh nominal.
- 8 Packs = 128 Zellen = ca. 128,6 kWh nominal.
- 16 Packs = 256 Zellen = ca. 257,2 kWh nominal.
- Nutzbar geplant: ca. 103 bis 109 kWh bei schonendem SoC-Fenster.

Preisrechnung mit 1 EUR = 1,1401 USD, ohne finalen Versand/DDP/Zoll:

| Ausbau | Zellen | Packs | Nominal | Zellenpreis | Gehaeusepreis | Summe wenn BMS enthalten | Summe mit separatem JK-BMS |
|---|---:|---:|---:|---:|---:|---:|---:|
| Minimum | 96 | 6 | ca. 96,5 kWh | ca. 3.789 EUR | ca. 815 EUR | ca. 4.604 EUR | ca. 5.166 EUR |
| Zielgroesse | 128 | 8 | ca. 128,6 kWh | ca. 5.052 EUR | ca. 1.087 EUR | ca. 6.139 EUR | ca. 6.888 EUR |
| Ausbau vorbereitet | 160 | 10 | ca. 160,8 kWh | ca. 6.315 EUR | ca. 1.358 EUR | ca. 7.673 EUR | ca. 8.610 EUR |
| Maximal vorbereitet | 256 | 16 | ca. 257,2 kWh | ca. 10.104 EUR | ca. 2.174 EUR | ca. 12.278 EUR | ca. 13.776 EUR |

Wichtig zum ASGOFT-Gehaeuse:

- Der Titel nennt "JK BMS".
- Die Attribute nennen `Battery Management System: Y`.
- Die Detailzeile nennt aber `Can Suit for Most Brand BMS (Without BMS)`.

Bis zur schriftlichen Bestaetigung durch den Lieferanten wird das Gehaeuse
deshalb als **ohne BMS** geplant. Wenn ein BMS enthalten ist, muss der Lieferant
exakt bestaetigen:

- BMS-Hersteller und Modell, bevorzugt JK PB2A16S20P oder vergleichbar.
- Dauerstrom mindestens 200 A pro Pack.
- CAN und RS485 vorhanden.
- Victron-Kompatibilitaet oder dokumentiertes Protokoll.
- Aktiver Balancer, bevorzugt 2 A.
- Temperaturfuehler, Lade-/Entladefreigaben und Abschaltlogik.
- Ob Sicherung, DC-Trenner, Precharge und Kommunikationskabel enthalten sind.

Bewertung fuer 6x MultiPlus-II 48/8000:

- Mit 6 Packs liegt der rechnerische Packstrom bei voller 38,4-kW-AC-Leistung
  und 48 V Batteriespannung bei ca. 142 A pro Pack. Das ist fuer 200-A-BMS
  moeglich, aber als Grundausstattung nicht mehr der Zielpunkt.
- Mit 8 Packs sinkt der Packstrom auf ca. 106 A pro Pack. Das ist die
  sinnvolle Grundausstattung.
- Mit 16 Packs sinkt der Packstrom auf ca. 53 A pro Pack und schont BMS,
  Zellen, Kabel und Sicherungen deutlich.

**Empfehlung:** 8 Packs als Grundausstattung bestellen. DC-Verteilung,
Aufstellflaeche, Kabelwege und Kommunikation direkt auf 16 Packs vorbereiten,
damit spaeter ohne Umbau der Hauptverteilung erweitert werden kann.

## DC-Verteilung, Busbars und DC-Kleinmaterial

Die Victron/Lynx-Komponenten werden als eigentliche DC-Verteilung geplant.
Das passt besser als frei aufgebaute Einzel-Busbars, weil die Sicherungen und
Abgaenge sauber im System sitzen. Die alte Pauschale von 500 EUR
DC-Kleinmaterial bleibt nur fuer Kabel, Kabelschuhe, Isolierung und
Beschriftung gedacht.

Wichtig: Separate DC-Schalter und separate Pack-Sicherungen werden **nicht**
noch einmal eingeplant, wenn das gewaehlte Batteriegehaeuse je Pack bereits ein
BMS mit Lasttrennschalter/Breaker und Sicherung mit geeignetem DC-
Abschaltvermoegen enthaelt. Das muss im Angebot schriftlich bestaetigt werden.

Planstruktur fuer den Speicher:

- Grundausstattung: 8 Packs als zwei Batteriegruppen mit je 4 Packs.
- Vorbereitung: bis 16 Packs als vier Batteriegruppen mit je 4 Packs.
- Victron/Lynx-Busbars fuer die Gruppen, MultiPlus-Abgaenge, MPPT-Abgaenge und
  Mess-/Verteilpunkte.
- Keine zusaetzlichen Pack-DC-Schalter, wenn die Boxen den Lasttrenner bereits
  integriert haben.

| Position | Link / Quelle | Menge / Ansatz | Planpreis |
|---|---|---:|---:|
| Victron/Lynx DC-Verteilung mit Sicherungsplaetzen | https://www.victronenergy.com/dc-distribution-systems/lynx-distributor | Grundausbau 8 Packs, vorbereitet auf 16 Packs | separat in Victron-/DC-Verteilung kalkulieren |
| Victron MEGA-fuse 300A/58V, Set 5 Stk. | https://www.offgridtec.com/en/victron-300a-80v-mega-fuse-fuse-set-of-5.html | nach finalem Abgangsplan, 38,44 EUR je 5er-Set | separat in Victron-/DC-Verteilung kalkulieren |
| H07V-K 95mm2 schwarz Meterware | https://www.elanto24.de/H07V-K-95mm2-PVC-Verdrahtungsleitung-feindraehtig-schwarz-Meterware | 17,59 EUR/m, Laenge nach Aufstellplan | 500 bis 1.500 EUR |
| Kalitec HR95-10 Rohrkabelschuh 95mm2 M10 | https://www.kabelschuhe-shop.de/Kalitec-HR95-10-Commercial-tubular-cable-lug-95mmA-M10 | 3,32 EUR/Stk., Menge nach Kabelplan | in Kabelansatz enthalten |
| Victron VE.Can RJ45 Terminator, 2er-Set | https://www.solartopstore.com/products/victron-ve-can-rj45-terminator-bag-of-2 | 9,00 EUR je 2er-Set | 100 bis 300 EUR mit Patchkabeln/Beschriftung |
| Schrumpfschlauch-Sortiment 142-teilig 3:1 mit Kleber | https://erh-shop.de/Schrumpfschlauch-Sortiment-142-teiligPlastikbox-klebend-Ratio-3-1-schw-rot/4250416329264 | 7,99 EUR je Set | 50 bis 150 EUR |
| OBO Bettermann 1809 Potentialausgleichsschiene | https://www.hornbach.de/p/obo-bettermann-1809-potentialausgleichsschiene-grau-188-mm/5007388/ | 7,14 EUR/Stk. | 100 bis 300 EUR mit Erdungsmaterial |

**Planansatz DC-Kleinmaterial Speicher:** 900 bis 2.600 EUR, ohne
Victron/Lynx-Busbars und ohne Sicherungen. Die Lynx-Verteilung und die
Sicherungen werden getrennt kalkuliert, weil sie zur DC-Hauptverteilung
gehoeren.

## PV und MPPT

Die 3x Victron SmartSolar MPPT RS 450/200 MC4 sind fuer 30 kWp grundsaetzlich
plausibel. Laut Victron hat der 450/200 vier MPP-Tracker, 450 V max.
PV-Spannung, 16 A Betriebsstrom je Tracker und 11,52 kW maximale DC-Ladeleistung
pro Geraet. Bei 3 Geraeten sind das rechnerisch 12 Tracker und 34,56 kW
maximale DC-Ladeleistung auf 48 V.

Noch zwingend nachzutragen:

| Thema | Warum wichtig |
|---|---|
| Exakte Modulanzahl, Modultyp, Voc, Isc, Temperaturkoeffizient | Kaltspannung darf 450 V je Tracker nicht ueberschreiten. |
| Stringplan je Dachflaeche und MPPT | 12 Tracker sind komfortabel, aber nur mit sauberem Stringplan. |
| DC-Trennstellen, String-Sicherungen, SPD Typ 1/2 | Haengt von Blitzschutz, Leitungswegen und Modulverschaltung ab. |
| Kabelwege Dach zu Technikraum | Querschnitt, Laenge, Brandschottung und Potentialausgleich fehlen noch. |
| Elektrikerangebot GSB 14.202,94 EUR | Enthalten sind 65x 455 Wp, Schienensystem, Stringverkabelung, Stecker/Kupplungen und Zaehlerschrank. Montage, Anmeldung, AC-Anschluss und Geruest sind laut Wortlaut noch zu klaeren. |

## AC-Topologie Haupthaus und Heizungsraum

Gewuenschtes Ziel: Zaehler im Haupthaus, Victron/Verteilung im Heizungsraum,
komplette Hauslast immer ueber Victron AC-out, 0-Einspeisung und moeglichst
0 Netzbezug im Normalbetrieb. Der Netzanschluss bleibt als Reserve,
Sicherheitsnetz und fuer die Netzparallelitaet vorhanden, soll aber im
Regelbetrieb nicht aktiv Leistung liefern.

Planlogik:

1. Netz / Zaehlerplatz Haupthaus.
2. Kein separater Victron-Grid-Meter in der Grundausstattung: ESS laeuft mit
   Grid metering = `Inverter/Charger`, weil wirklich alle Lasten und alle
   AC-gekoppelten Erzeuger auf AC-out liegen.
3. Zuleitung in den Heizungsraum auf neue Unterverteilung.
4. Dort AC-in Schutz fuer Victron: Hauptschalter, Vorsicherung, RCD-Konzept,
   SPD, eindeutige N/PE-Fuehrung.
5. Victron MultiPlus dreiphasig.
6. Von Victron AC-out wieder zur Hausverteilung im Haupthaus, damit die
   komplette Hauslast im Normalbetrieb und im Ersatzstromfall auf AC-out liegt.
7. Mechanisch/elektrisch verriegelter Wartungs-Bypass, damit das Haus auch bei
   Victron-Service sicher versorgt werden kann.
8. Lastmanagement fuer Wallbox, Waermepumpen und optionale abwerfbare Lasten,
   damit der Victron im Normalbetrieb nicht in Netzbezug gedrueckt wird.

Vorhandenes Balkonkraftwerk: Die bereits vorhandenen 5x 500-W-Module und
2x 450-W-Module mit Mikro-Wechselrichtern haengen ebenfalls auf AC-out. Sie
werden damit wie AC-gekoppelte PV hinter dem Victron behandelt. Bei vollem
Speicher kann der Victron die AC-gekoppelte PV ueber Frequenzanhebung
abregeln, sofern die Mikro-Wechselrichter normgerecht auf Frequenz-Wirkleistung
reagieren. Mit 3,4 kWp Modulleistung ist die AC-gekoppelte Bestands-PV im
Verhaeltnis zu 6x MultiPlus-II 48/8000 unkritisch; die Victron-Factor-1.0-
Regel fuer PV-Wechselrichter auf AC-out bleibt trotzdem zu pruefen.

Hinweis zur 0-Einspeisung: Victron ESS kann den Grid Setpoint leicht oberhalb
0 W setzen, um Rueckspeisung zu vermeiden. Bei schnellen Lastwechseln kann es
trotzdem kurze Ueberschwinger geben. Fuer eine harte 0-Einspeisung sollte der
Grid Setpoint eher auf +100 bis +300 W Bezug stehen, nicht exakt auf 0 W.
Fuer echte Autarkie ist aber nicht nur die Einspeisung relevant, sondern auch
die AC-out-Leistungsgrenze: jede Last, die nicht gerade aus PV/Batterie gedeckt
werden kann, erzeugt Netzbezug oder muss per Lastmanagement reduziert werden.

### Bewertung 0-kWh-Einspeisung

Mit der geplanten Topologie ist 0-kWh-Einspeisung gut erreichbar, weil die PV
ueber Victron-MPPTs DC-gekoppelt in den Speicher laedt und das Haus dauerhaft
am Victron AC-out haengt. Dadurch kann die Steuerung PV-Leistung,
Batterieladung und Verbraucherfreigaben zentral begrenzen.

Ein externer Victron-Grid-Meter ist dafuer nicht zwingend erforderlich, solange
die Topologie konsequent eingehalten wird: Netz nur an AC-in, komplette
Hauslast auf AC-out, vorhandene Mikro-Wechselrichter/Balkonkraftwerk ebenfalls
auf AC-out. Die MultiPlus messen dann den Energiefluss ueber AC-in/AC-out
selbst. Ein VM-3P75CT bleibt optional sinnvoll fuer unabhaengiges Monitoring,
Abgleich mit dem Hauptzaehler oder spaetere Unterzaehlerfunktionen.

Wichtig ist die Unterscheidung:

- **0 kWh Einspeisung ueber den Zaehlerzeitraum** ist realistisch.
- **Exakt 0 W in jedem Moment** ist praktisch nicht garantierbar, weil
  Lastspruenge, Regelzeiten und Messintervalle kurze Ueberschwinger erzeugen
  koennen.

Empfohlene Regelstrategie:

1. Victron ESS/Grid Setpoint leicht positiv einstellen, z.B. +100 bis +300 W
   Netzbezug, damit keine echte Rueckspeisung entsteht.
2. PV zuerst Hauslast und Batterie bedienen lassen.
3. Bei vollem oder fast vollem Speicher Verbraucher freigeben:
   Warmwasser-WP, Heizpuffer, Polestar, ggf. Komfortanhebung.
4. Wenn Speicher voll und keine Verbraucher frei sind, PV-Leistung abregeln.
   Das kostet Sommerertrag, ist aber genau der Preis fuer echte
   Nulleinspeisung.
5. Home Assistant/Victron muss Wallbox, Waermepumpen und Warmwasser aktiv
   begrenzen, damit nicht gleichzeitig Netzbezug entsteht.

Mit ca. 100 kWh nutzbarem Speicher ist diese Strategie im Sommer und in der
Uebergangszeit sehr stark. Der Speicher ist gross genug, um fast jeden normalen
Tagesueberschuss in Abend/Nacht zu verschieben. Im Sommer wird er bei 44,5 kWp
Dach + Zaun trotzdem oft voll sein; dann muss die Anlage entweder Auto/Waerme
laden oder PV abregeln. Im Winter ist nicht Einspeisung das Problem, sondern zu
wenig PV-Ertrag.

## Wechselrichter-Dimensionierung inkl. Polestar 4

Der Polestar 4 muss mit eingeplant werden. Home Assistant zeigt aktuell
waehrend des Ladens ca. 10,34 kW Polestar/Wallbox-Leistung bei 15 A und
ca. 12,68 kW Netzbezug. Die sonstige Momentanlast liegt damit grob bei
2,3 kW. Bei freigegebener 22-kW-Wallbox waere dieselbe Situation eher:

- 22 kW Polestar 4 Laden.
- ca. 2 bis 4 kW normale Hauslast als Momentaufnahme.
- zusaetzlich Waermepumpen, Warmwasser-WP, Pumpen, Kompressoranlauf,
  Abtauphasen und Haushaltsgrossverbraucher.

Damit ist klar: **3x MultiPlus-II 48/6k5 sind fuer echtes ganzes Haus ueber
AC-out plus 22-kW-Auto plus Waermepumpen zu klein**, wenn das Ziel nicht nur
Ersatzstrom, sondern im Alltag moeglichst 0 Netzbezug ist.

| Variante | Link / Quelle | Offizielle/angesetzte Dauerleistung | Grobe Kosten WR | Bewertung |
|---|---|---:|---:|---|
| 3x MultiPlus-II 48/6k5 | https://www.victronenergy.com/inverters-chargers/multiplus-ii | ca. 18 kW Systemannahme | ca. 1.877 bis 1.947 EUR | Nur sinnvoll, wenn Wallbox auch im Normalbetrieb hart begrenzt/abgeworfen wird und Waermepumpen gestaffelt laufen. |
| 3x MultiPlus-II 48/8000 | https://www.victronenergy.com/inverters-chargers/multiplus-ii | 3x 6,4 kW = 19,2 kW bei 25 C, 16,5 kW bei 40 C | ca. 3.281 EUR | Kaum echter Gewinn gegenueber 6k5 fuer dein Lastbild. |
| 3x MultiPlus-II 48/10000 | https://www.victronenergy.com/inverters-chargers/multiplus-ii | 3x 8 kW = 24 kW bei 25 C, 21 kW bei 40 C | ca. 3.387 EUR | Sinnvoller Mindestvorschlag, aber 22-kW-Auto plus Waermepumpen geht nur mit Lastmanagement. |
| 3x MultiPlus-II 48/15000 | https://www.victronenergy.com/inverters-chargers/multiplus-ii | 3x 12 kW = 36 kW bei 25 C, 30 kW bei 40 C | ca. 6.576 EUR | Technisch deutlich passender fuer grosses Haus, aber DC-Stroeme, Kosten, Platz und Waerme steigen stark. |
| 6x MultiPlus-II 48/8000, je 2 parallel pro Phase | https://www.victronenergy.com/inverters-chargers/multiplus-ii | 48 kVA, real 6x 6,4 kW = 38,4 kW bei 25 C, 33 kW bei 40 C | ca. 6.563 EUR | Sehr interessante Komfortvariante: aehnliche Kosten wie 3x 15k, aber modularer. Haus haengt dauerhaft auf AC-out; nur manueller Wartungs-Bypass fuer Arbeiten an der Anlage noetig. |
| 6x 6k5, je 2 parallel pro Phase | https://www.victronenergy.com/inverters-chargers/multiplus-ii | ca. 36 kW Systemannahme | ca. 3.755 bis 3.894 EUR | Guenstig pro kW, aber VE.Bus-Parallelbetrieb, Absicherung, Phasenaufbau und Freigabe sauber mit Victron/Eli klaeren. |

Empfehlung:

- Wenn der Fokus auf guenstig und robust liegt: 3x MultiPlus-II 48/10000 und
  konsequentes Lastmanagement.
- Im Autarkiebetrieb: Wallbox zuerst abwerfen oder auf 6 bis 11 kW begrenzen,
  Waermepumpen nicht gleichzeitig starten, Warmwasser-WP nachrangig.
- Wenn 22-kW-Laden auch ohne Netzbezug parallel zu Waermepumpen laufen soll:
  3x 15k, 6x 8000 oder 6x 6k5/parallel planen. Das ist dann aber ein anderes
  DC-Busbar-, Sicherungs- und Waermeabfuhr-Niveau.

### Einordnung 6x MultiPlus-II 48/8000

6x 8000 klingt zuerst nach 48 kW. Korrekt ist aber: 48 kVA
Wechselrichtergroesse, real laut Victron 6x 6,4 kW = 38,4 kW Dauerleistung bei
25 C und 6x 5,5 kW = 33 kW bei 40 C. Pro Phase waeren es bei 2 Geraeten je
Phase ca. 16 kVA, 12,8 kW bei 25 C und 11 kW bei 40 C.

Das passt deutlich besser zu deinem Ziel als 3x 10k:

- Polestar 4 mit 22 kW blockiert dann nicht mehr praktisch die komplette
  Wechselrichterleistung.
- Fuer Hauslast und eine Waermepumpe bleibt noch Reserve.
- Zwei Waermepumpen plus 22-kW-Laden koennen trotzdem je nach elektrischer
  WP-Leistungsaufnahme noch Lastmanagement brauchen.
- Der DC-Bus muss auf grob 800 bis 900 A Dauerstrom plus Reserven ausgelegt
  werden.
- Da das Haus dauerhaft am AC-out haengt, wird kein automatischer Transfer-
  Switch als Regelumschaltung geplant. Benoetigt wird nur ein mechanisch
  eindeutiger manueller Wartungs-Bypass, damit das Haus bei Arbeiten oder
  Defekt der Victron-Anlage direkt auf Netz gelegt werden kann.

## Feinplanung Zielvariante: 6x MultiPlus-II 48/8000

Diese Variante wird als neue Zielvariante geplant:

- 6x MultiPlus-II 48/8000/110-100.
- 3-phasig, je Phase 2 MultiPlus parallel.
- 48 kVA Wechselrichtergroesse.
- 38,4 kW Dauerleistung bei 25 C.
- 33,0 kW Dauerleistung bei 40 C.
- 22-kW-Wallbox bleibt moeglich, aber weiterhin lastmanagementpflichtig, wenn
  beide Waermepumpen oder andere grosse Verbraucher gleichzeitig laufen.

### Akkugroesse

Fuer 6x 8000 ist die Strombelastung wichtiger als die reine kWh-Zahl.
Grundausstattung sind 8 Packs. Die Anlage soll mechanisch und elektrisch auf
16 Packs vorbereitet werden, auch wenn nicht sofort alle Packs bestueckt
werden.

| Variante | Zellen | Packs | Nominal | Nutzbar geplant | Gesamt-Ah bei 51,2 V | Strom pro Pack bei 38,4 kW und 48 V |
|---|---:|---:|---:|---:|---:|---:|
| Kleiner Startausbau | 96 | 6x 16s | ca. 96,5 kWh | ca. 77 bis 82 kWh | 1.884 Ah | ca. 142 A |
| Grundausstattung | 128 | 8x 16s | ca. 128,6 kWh | ca. 103 bis 109 kWh | 2.512 Ah | ca. 106 A |
| Zwischenstufe | 160 | 10x 16s | ca. 160,8 kWh | ca. 129 bis 137 kWh | 3.140 Ah | ca. 85 A |
| Voll vorbereitet | 256 | 16x 16s | ca. 257,2 kWh | ca. 206 bis 219 kWh | 5.024 Ah | ca. 53 A |

Bewertung:

- 6 Packs funktionieren rechnerisch, sind aber nur ein kleiner Startausbau und
  passen nicht mehr zum Ziel "alles ueber Victron".
- 8 Packs sind die Grundausstattung: Strom je Pack, nutzbare Energie und
  Kosten bleiben in einem sinnvollen Verhaeltnis.
- 16 Packs sind fuer Winterreserve und Schonbetrieb attraktiv und reduzieren
  den Strom je Pack stark. Der Platzbedarf, die Zellkosten und die
  Kommunikations-/Gruppenstruktur muessen dafuer von Anfang an vorgesehen
  werden.

**Empfehlung Akkugroesse:** 8x 16s mit EVE MB31 314 Ah als Grundausstattung
planen, aber Stellflaeche, Lynx-/Busbar-Struktur, Kabelwege und Kommunikation
direkt fuer 16x 16s vorbereiten.

### DC-Leistungsrechnung

Rechnung mit ca. 94 % Wirkungsgrad. Als unterer Planwert wird 48 V verwendet;
44 V wird nicht mehr als normaler Betriebs-/Auslegungswert angesetzt, weil die
Packs dann bereits ausserhalb des gewuenschten Nutzfensters waeren.

| Zustand | AC-Leistung | DC-Strom bei 52 V | DC-Strom bei 51,2 V nominal | DC-Strom bei 48 V |
|---|---:|---:|---:|---:|
| 6x 8000 bei 25 C | 38,4 kW | ca. 787 A | ca. 798 A | ca. 851 A |
| 6x 8000 bei 40 C | 33,0 kW | ca. 675 A | ca. 686 A | ca. 731 A |
| Polestar 4 22 kW | 22,0 kW | ca. 450 A | ca. 457 A | ca. 488 A |

Planungsfolgen:

- Haupt-DC-Bus nicht auf 600 A auslegen, sondern mindestens auf 1.000 A.
  Mit Vorbereitung auf 16 Packs wird die Lynx-/Busbar-Struktur von Anfang an
  gruppenweise geplant.
- Batterieboxen und BMS nicht nur nach kWh kaufen, sondern nach realem
  Dauerstrom, CAN/RS485-Kompatibilitaet und Abschaltverhalten.
- DVCC/BMS-Limits muessen die Summe aus MPPT-Ladung und moeglicher
  AC-Ladung begrenzen.

### Ladeleistung und BMS-Limits

Die 3x MPPT RS 450/200 koennen zusammen theoretisch bis zu 600 A in den
48-V-Speicher laden. Die 6 MultiPlus-II 48/8000 haben zusaetzlich je 110 A
Ladegeraet, also theoretisch weitere 660 A AC-Ladung. Beides gleichzeitig darf
nicht unkontrolliert auf die Batterie losgelassen werden.

| Akkuausbau | Schonender Ladezielwert ca. 0,3 C | Oberer Planwert ca. 0,5 C | Empfehlung DVCC |
|---|---:|---:|---|
| 6 Packs / 1.884 Ah | ca. 565 A | ca. 942 A | 500 bis 600 A, AC-Ladung nachrangig |
| 8 Packs / 2.512 Ah | ca. 754 A | ca. 1.256 A | 700 bis 800 A, PV bevorzugt |
| 10 Packs / 3.140 Ah | ca. 942 A | ca. 1.570 A | 900 bis 1.000 A, nur wenn BMS/Busbar passt |
| 16 Packs / 5.024 Ah | ca. 1.507 A | ca. 2.512 A | 1.000 bis 1.200 A reichen fuer die geplanten Victron-Leistungen meist aus, BMS-Limits gruppenweise sauber setzen |

### DC-Aufbau

| Teil | Planansatz fuer 6x 8000 |
|---|---|
| MultiPlus DC-Kabel | Laut Victron pro 48/8000: 2x 50 mm2 plus und 2x 50 mm2 minus bis 5 m, 2x 70 mm2 je Pol bei 5 bis 10 m. |
| MultiPlus DC-Sicherung | Laut Victron 300 A je MultiPlus 48/8000. |
| Batterie-Pack-Kabel | Je Pack eigener Abgang zur Batteriegruppe/Lynx-Struktur, Querschnitt nach BMS-Strom, Laenge und Verlegeart. |
| Pack-Sicherung / Pack-Trennung | Nicht doppelt einplanen, wenn im Gehaeuse ein geeigneter Lasttrennschalter/Breaker und eine DC-Sicherung enthalten sind. Lieferumfang und Abschaltvermoegen schriftlich bestaetigen. |
| Hauptbusbar / DC-Verteilung | Victron/Lynx-Busbars verwenden. Grundausstattung 8 Packs als zwei Gruppen, vorbereitet auf 16 Packs als vier Gruppen. |
| Haupttrennung | Kein separater pauschaler DC-Schalter eingeplant. Wartung/Trennung ueber BMS-/Box-Lasttrenner und gruppenweise Lynx-/Sicherungsstruktur klaeren. |
| Vorladung | Precharge nur separat einplanen, wenn nicht durch BMS/Box oder Wechselrichter-Zuschaltkonzept geloest. |
| Schutzkonzept | Schutzorgane in den Boxen plus Lynx-Sicherungen fuer Gruppen, MultiPlus- und MPPT-Abgaenge. Keine Billigsicherung ohne DC-Abschaltvermoegen bei 100+ kWh. |

### AC-Aufbau

| Teil | Planansatz |
|---|---|
| Phasenaufteilung | L1: 2x MultiPlus parallel, L2: 2x MultiPlus parallel, L3: 2x MultiPlus parallel. |
| AC-out Dauerstrom | Ca. 55,7 A je Phase bei 25 C, ca. 47,8 A je Phase bei 40 C. |
| Wallbox 22 kW | 32 A je Phase, damit bleiben bei 25 C ca. 23 A je Phase fuer Haus/WP, bei 40 C ca. 16 A je Phase. |
| AC-out Verteilung | Auf 63 A dreiphasig planen, Selektivitaet und Gleichzeitigkeiten mit Elektriker pruefen. |
| Manueller Wartungs-Bypass | Hager SF463 4P 63A I-0-II oder gleichwertig. Normal: Haus an Victron AC-out. Wartung: manuell auf Netz. Keine automatische Regelumschaltung. |
| Lastmanagement | Wallbox stufenlos oder in Stufen 0/6/11/22 kW; Waermepumpenfreigabe gestaffelt; Warmwasser-WP nachrangig. |

### Zielverhalten fuer Autarkie

Prioritaeten im Betrieb:

1. Haus-Grundlast immer ueber PV/Batterie.
2. Waermepumpen bevorzugt bei PV-Ueberschuss oder ausreichend SoC.
3. Polestar 4 nur mit PV-Ueberschuss oder ausreichendem Speicherfenster auf
   22 kW, sonst 6 bis 11 kW oder Pause.
4. Warmwasser-WP nur bei Ueberschuss oder definiertem Komfortbedarf.
5. Netzbezug vermeiden: Wenn AC-out-Leistung oder Batterie-SoC nicht reicht,
   Lasten reduzieren statt still Netzleistung zu ziehen.

### Reicht die Akkugroesse im Winter?

Kurzantwort: **fuer Tagesverschiebung ja, fuer echte 100-%-Winterautarkie
nein, zumindest nicht verlaesslich.** Der Akku ist ein Tages- bis
Kurzzeitpuffer, kein saisonaler Speicher.

PVGIS wurde fuer den Standort mit 30 kWp, 35 Grad Neigung, Sued-Ausrichtung und
14 % Systemverlusten als grobe Referenz gerechnet. Die echten Werte haengen
spaeter vom Dach, Stringplan, Verschattung und Ausrichtung ab.

| Monat | PVGIS-Ertrag 30 kWp | Durchschnitt pro Tag |
|---|---:|---:|
| November | ca. 1.055 kWh/Monat | ca. 35 kWh/Tag |
| Dezember | ca. 718 kWh/Monat | ca. 23 kWh/Tag |
| Januar | ca. 852 kWh/Monat | ca. 28 kWh/Tag |
| Februar | ca. 1.511 kWh/Monat | ca. 54 kWh/Tag |

### Erwarteter PV-Ertrag mit 500-W-Modulen

Die weitere Planung rechnet nicht mehr mit den 455-W-Modulen aus dem Angebot,
sondern mit 500-W-Modulen und gleicher Modulanzahl. Fuer die Dachflaechen wird
gerechnet mit:

- Dach: 65 Module x 500 W = 32,5 kWp.
- Verteilung Dach fuer die Grobrechnung: 20,5 kWp Sued, 8,0 kWp Ost,
  4,0 kWp West.
- PV-Zaun optional: 16 Module Sued + 8 Module West = 12,0 kWp.
- Schuppen-Nord optional: sauber 24 Module = 12,0 kWp; mit Restflaeche bis
  28 Module = 14,0 kWp.

PVGIS-Grobrechnung, Standort 53.07014237022626 / 11.602326145864437,
14 % Systemverluste:

| Variante | Generator | Winter Nov-Feb | Uebergangszeit Mar-Apr/Sep-Oct | Sommer Mai-Aug |
|---|---:|---:|---:|---:|
| Dach 500 W | 32,5 kWp | ca. 31 kWh/Tag | ca. 91 kWh/Tag | ca. 130 kWh/Tag |
| Dach + PV-Zaun | 44,5 kWp | ca. 43 kWh/Tag | ca. 116 kWh/Tag | ca. 157 kWh/Tag |
| Dach + PV-Zaun + Nord sauber | 56,5 kWp | ca. 47 kWh/Tag | ca. 131 kWh/Tag | ca. 195 kWh/Tag |
| Dach + PV-Zaun + Nord maximal | 58,5 kWp | ca. 48 kWh/Tag | ca. 134 kWh/Tag | ca. 201 kWh/Tag |

Monatswerte fuer die wichtigste Zielvariante ohne Nordseite:

| Monat | Dach 32,5 kWp | Dach + Zaun 44,5 kWp |
|---|---:|---:|
| Januar | ca. 24,5 kWh/Tag | ca. 33,9 kWh/Tag |
| Februar | ca. 49,6 kWh/Tag | ca. 66,8 kWh/Tag |
| Maerz | ca. 79,1 kWh/Tag | ca. 102,4 kWh/Tag |
| April | ca. 124,7 kWh/Tag | ca. 156,0 kWh/Tag |
| Mai | ca. 133,0 kWh/Tag | ca. 161,6 kWh/Tag |
| Juni | ca. 139,0 kWh/Tag | ca. 167,0 kWh/Tag |
| Juli | ca. 129,8 kWh/Tag | ca. 157,1 kWh/Tag |
| August | ca. 116,5 kWh/Tag | ca. 143,8 kWh/Tag |
| September | ca. 98,6 kWh/Tag | ca. 126,1 kWh/Tag |
| Oktober | ca. 61,0 kWh/Tag | ca. 81,3 kWh/Tag |
| November | ca. 31,9 kWh/Tag | ca. 44,1 kWh/Tag |
| Dezember | ca. 20,7 kWh/Tag | ca. 29,2 kWh/Tag |

Bewertung:

- Der PV-Zaun bringt im Winter deutlich mehr als die Nordseite pro kWp.
- Die Nordseite ist fuer Sommer/Autoladung stark, verbessert Dezember/Januar
  aber nur um wenige kWh pro Tag.
- Fuer den Winter ist der Sprung von Dach allein auf Dach + Zaun wichtiger als
  der Sprung von Dach + Zaun auf Dach + Zaun + Nord.

### Bewertung 8-Pack-Speicher / ca. 100 kWh nutzbar

Die 8 Packs mit EVE/MB31 314 Ah haben ca. 128,6 kWh nominal. Realistisch
nutzbar geplant sind ca. 103 bis 109 kWh. Fuer die folgenden Ueberschlaege wird
mit rund 105 kWh nutzbarem Speicher gerechnet.

Mit der Zielvariante **Dach + PV-Zaun = 44,5 kWp** ergeben sich als
Ertragsreferenz:

- Dezember: ca. 29 kWh/Tag.
- Januar: ca. 34 kWh/Tag.
- Wintermittel November bis Februar: ca. 43 kWh/Tag.
- Uebergangszeit: ca. 116 kWh/Tag.
- Sommer: ca. 157 kWh/Tag.

| Situation | Tagesverbrauch grob | PV-Ertrag grob | Tagesbilanz | 105-kWh-Speicher reicht grob |
|---|---:|---:|---:|---:|
| Sommer ohne grosse Autoladung | 35 bis 50 kWh | 140 bis 170 kWh | klarer Ueberschuss | Speicher wird fast taeglich voll, Kapazitaet reicht locker fuer Nacht/Schlechtwetter |
| Sommer mit Polestar-Ladung | 70 bis 130 kWh | 140 bis 170 kWh | meist Ueberschuss | sehr gut, 22-kW-Laden muss nur bei schlechtem Wetter begrenzt werden |
| Uebergangszeit normal | 55 bis 100 kWh | 80 bis 156 kWh | oft Ueberschuss | sehr gut, meist 1 bis 3 schlechte Tage pufferbar |
| Uebergangszeit schlecht/wolkig | 60 bis 110 kWh | 20 bis 60 kWh | -40 bis -90 kWh | 1 bis 2 Tage, danach Netzladung/Lastmanagement sinnvoll |
| Dezember/Januar mild ohne Auto | 70 bis 85 kWh | 29 bis 34 kWh | -36 bis -56 kWh | ca. 2 Tage |
| Dezember/Januar normal | 95 bis 140 kWh | 29 bis 34 kWh | -61 bis -111 kWh | ca. 1 Tag |
| Kalter Wintertag mit Auto | 180 bis 280 kWh | 0 bis 34 kWh | -150 bis -280 kWh | deutlich unter 1 Tag |

Fazit zum 100-kWh-Speicher:

- Fuer Sommer und Uebergangszeit ist der Speicher sehr stark. Er verschiebt
  Tagesertrag sauber in Abend/Nacht und macht die Anlage im normalen Betrieb
  sehr autark.
- Fuer Dezember/Januar ist er ein guter Tagespuffer, aber kein
  Winterautarkie-Speicher. Mit Waermepumpen und Auto kann ein einziger kalter
  Tag den Speicher weitgehend leeren.
- Der Speicher passt sehr gut zu einem dynamischen Tarif: Im Winter kann er
  billige Preisfenster in teure Zeitfenster verschieben.
- Der naechstgroessere Ausbau auf 16 Packs verbessert vor allem die
  Mehrtagespufferung und reduziert Strom je Pack. Er ersetzt aber ebenfalls
  keinen saisonalen Speicher.

Die Home-Assistant-Auswertung der letzten 7 Tage zeigt ohne Wallbox grob:

- EG+OG gesamt: ca. 577 kWh in 7 Tagen.
- Davon Wallbox: ca. 274 kWh in 7 Tagen.
- Hauslast ohne Wallbox in diesem kurzen Sommerfenster: ca. 303 kWh in
  7 Tagen, also ca. 43 kWh/Tag.

Das ist noch ohne die geplanten Waermepumpen als Winter-Hauptlast zu werten.
Eine echte Winterrechnung muss daher mit mehreren Szenarien arbeiten:

| Szenario | Haus ohne Auto | Waermepumpen elektrisch | Polestar | PV Dezember | Tagesbilanz | 8-Pack-Akku ca. 105 kWh nutzbar |
|---|---:|---:|---:|---:|---:|---:|
| Milder Wintertag ohne Auto | 35 bis 45 kWh | 25 bis 40 kWh | 0 kWh | 23 kWh | -37 bis -62 kWh | ca. 1,7 bis 2,8 Tage |
| Normaler Wintertag | 40 bis 50 kWh | 50 bis 80 kWh | 0 bis 20 kWh | 23 kWh | -67 bis -127 kWh | ca. 0,8 bis 1,6 Tage |
| Kalter Tag mit Auto | 40 bis 60 kWh | 80 bis 140 kWh | 40 bis 80 kWh | 0 bis 23 kWh | -137 bis -280 kWh | deutlich unter 1 Tag |
| Mehrere Dunkelflauten-Tage | 40 bis 60 kWh | 80 bis 140 kWh | optional | 0 bis 10 kWh | -110 bis -190 kWh ohne Auto | 8 Packs nach ca. 0,5 bis 1 Tag leer |

Bewertung der Packgroessen:

| Ausbau | Nutzbar geplant | Winterbewertung |
|---|---:|---|
| 6 Packs / ca. 96,5 kWh nominal | ca. 77 bis 82 kWh | Zu klein fuer das Autarkieziel mit Waermepumpen; nur Start-/Uebergangsloesung. |
| 8 Packs / ca. 128,6 kWh nominal | ca. 103 bis 109 kWh | Sinnvolle Grundausstattung fuer Tagespuffer und hohe Leistung, aber keine sichere Winterautarkie. |
| 16 Packs / ca. 257,2 kWh nominal | ca. 206 bis 219 kWh | Deutlich entspannter fuer Wintertage und Akku-Schonung, aber immer noch kein saisonaler Speicher. |

Fazit fuer die Winterplanung:

- 8 Packs sind fuer 6x 8000 elektrisch sinnvoll und deutlich besser als
  6 Packs.
- Fuer 100 % Autarkie im Winter reicht auch 8x 16s nicht verlaesslich, weil im
  Dezember durchschnittlich nur ca. 23 kWh PV pro Tag nachkommen.
- Der Polestar kann eine komplette nutzbare Tagesreserve praktisch allein
  verbrauchen.
- Wenn Netzbezug wirklich vermieden werden soll, braucht es im Winter harte
  Regeln: Wallbox pausieren oder niedrig begrenzen, Waermepumpen priorisieren,
  Warmwasser nachrangig, Komforttemperaturen/Heizkurve bei niedrigem SoC
  automatisch reduzieren.
- Fuer echte mehrtaegige Winterautarkie braucht es entweder deutlich mehr
  Wintererzeugung, eine Reservequelle oder die Akzeptanz von Lastabwurf.

### Dynamischer Stromtarif als Winterstrategie

Ein dynamischer Tarif passt sehr gut zu dieser Anlage. Das Ziel verschiebt sich
dann von "im Winter niemals Netz beruehren" zu "Netz nur dann nutzen, wenn es
energetisch und preislich sinnvoll ist". Gerade bei 8 bis 16 Batterie-Packs,
22-kW-Wallbox und Waermepumpen kann das viel bringen.

Rahmenbedingungen:

- Seit 2025 muessen Stromlieferanten dynamische Tarife anbieten.
- Fuer einen echten dynamischen Tarif wird ein intelligentes Messsystem
  benoetigt.
- Anbieter wie Tibber, Octopus, Vattenfall und andere bieten Tarife an, die
  sich an Day-Ahead-/Spotmarktpreisen orientieren.
- Die Steuerung muss in Home Assistant/Victron automatisch laufen; manuell
  lohnt sich das bei dieser Anlagengroesse nicht.

Empfohlene Betriebslogik:

| Situation | Aktion |
|---|---|
| PV-Ueberschuss | Batterie laden, Waermepumpen/Warmwasser/Polestar freigeben. |
| Normaler Winterpreis | Batterie nicht aus dem Netz laden, nur notwendige Hauslast decken. |
| Sehr guenstiger Strompreis | Batterie auf Winterziel-SoC laden, Waermepumpen und Warmwasser vorziehen, Polestar laden. |
| Teurer Strompreis | Netzbezug vermeiden, Batterie entladen, Wallbox sperren/begrenzen, Warmwasser nachrangig. |
| Sehr niedriger SoC und kaltes Wetter | Notreserve halten, Waermepumpen priorisieren, Auto nicht aus Batterie laden. |

Preislogik fuer Netzladung:

| Schwelle | Bedeutung |
|---|---|
| Preis < 15 ct/kWh | Sehr attraktiv: Akku und Waerme aktiv laden, wenn genug freie Kapazitaet vorhanden ist. |
| 15 bis 22 ct/kWh | Situativ laden, vor allem wenn Wetterprognose schlecht und SoC niedrig ist. |
| 22 bis 28 ct/kWh | Eher nur direkte Verbraucher nutzen, Akku-Netzladung vermeiden. |
| > 28 ct/kWh | Nur Pflichtlasten, Batterie entladen, Wallbox/Warmwasser sperren oder stark begrenzen. |

Die Schwellen muessen spaeter mit deinem echten Arbeitspreis inklusive
Netzentgelten, Umlagen, Grundpreisanteil, Ladeverlusten und Akkuverschleiss
kalibriert werden. Als Faustregel: Netzladung in den Akku lohnt nur, wenn der
guenstige Strompreis gegenueber dem spaeter vermiedenen teuren Strom mindestens
ca. 8 bis 12 ct/kWh Abstand hat. Bei 100 kWh nutzbarer Verschiebung sind 10
ct/kWh Preisdifferenz grob 10 EUR pro voller Verschiebung, abzueglich Verluste.

Winter-Zielwerte fuer die Steuerung:

| Zeitraum / Zustand | Batterie-Ziel |
|---|---|
| Sommer | PV-gefuehrt, Netzladung aus, Reserve ca. 20 bis 30 %. |
| Uebergangszeit | Netzladung nur bei sehr guenstigem Preis und schlechter Prognose, Ziel ca. 50 bis 70 %. |
| Winter normal | Bei guenstigem Preis auf ca. 80 bis 90 % laden. |
| Winter kalt / Dunkelflaute erwartet | Bei guenstigem Preis auf ca. 90 bis 95 % laden, Wallbox nachrangig. |
| Notreserve | Unter ca. 25 bis 35 % SoC keine Autoladung aus Batterie, Waermepumpen priorisieren. |

Fuer dein System waere die richtige Regel also nicht "immer billig voll laden",
sondern:

1. Wetter- und PV-Prognose fuer die naechsten 24 bis 48 Stunden pruefen.
2. Day-Ahead-Preise laden.
3. Mindest-SoC fuer Waermepumpen und Haus berechnen.
4. Guenstige Preisfenster nutzen, um Batterie, Warmwasser und Auto gezielt zu
   fuellen.
5. Teure Fenster mit Batterie ueberbruecken.

Damit wird der grosse Speicher im Winter deutlich sinnvoller: Er schafft nicht
100 % physikalische Autarkie, aber er kann den Netzbezug in sehr guenstige
Zeitfenster verschieben und teure Spitzen vermeiden.

### Option: Nordseite Schuppen belegen, ca. 14 x 5 m

Die Nordseite des Schuppens hat mit ca. 14 m x 5 m etwa 70 m2 Bruttoflaeche.
Je nach Modulformat, Randabstaenden und Montagesystem sind grob 28 bis 32
Module realistisch. Bei heutigen Modulen entspricht das ca. 12,5 bis 15 kWp.
Fuer die Grobrechnung wird mit 14 kWp gerechnet.

PVGIS-Grobrechnung fuer 14 kWp Norddach, 14 % Systemverluste:

| Dachneigung | Jahresertrag | November | Dezember | Januar | Februar |
|---:|---:|---:|---:|---:|---:|
| 10 Grad Nord | ca. 10.651 kWh/Jahr | 5,5 kWh/Tag | 3,0 kWh/Tag | 4,2 kWh/Tag | 10,6 kWh/Tag |
| 20 Grad Nord | ca. 9.348 kWh/Jahr | 4,8 kWh/Tag | 3,1 kWh/Tag | 4,0 kWh/Tag | 7,6 kWh/Tag |
| 30 Grad Nord | ca. 8.046 kWh/Jahr | 4,6 kWh/Tag | 2,8 kWh/Tag | 3,8 kWh/Tag | 7,3 kWh/Tag |
| 35 Grad Nord | ca. 7.398 kWh/Jahr | 4,4 kWh/Tag | 2,7 kWh/Tag | 3,6 kWh/Tag | 7,0 kWh/Tag |
| 45 Grad Nord | ca. 6.171 kWh/Jahr | 3,9 kWh/Tag | 2,4 kWh/Tag | 3,2 kWh/Tag | 6,4 kWh/Tag |

Bewertung:

- Fuer Dezember/Januar loest die Nordseite das Winterproblem nicht. 14 kWp
  bringen bei echter Nordausrichtung im Dezember nur ca. 2,4 bis 3,1 kWh pro
  Tag.
- Fuer Jahresertrag und Uebergangszeit kann die Flaeche trotzdem interessant
  sein, besonders wenn sie flach ist und die Montage guenstig mitgemacht werden
  kann.
- Sehr flache Norddaecher sind deutlich besser als steile Norddaecher, weil sie
  mehr diffuses Licht und Sommerertrag mitnehmen.
- Wenn die 30-kWp-Anlage schon am Netzanschluss-/Anmeldekonzept kratzt, muss
  geprueft werden, ob die zusaetzlichen kWp als DC-gekoppelte Speicherladung
  oder als spaeterer Ausbau sinnvoller sind.

Empfehlung:

- Nordseite nur belegen, wenn der Mehrpreis pro kWp sehr niedrig ist oder die
  Montage ohnehin vorbereitet wird.
- Fuer Winterautarkie zuerst dynamischen Tarif, Lastmanagement, Heizstrategie
  und ggf. mehr sued-/ost-/westorientierte Winterflaeche priorisieren.
- Falls belegt wird: eher flach/parallel zur Dachflaeche, keine teure
  Aufstaenderung fuer Nord; eigene MPPT-Gruppe wegen anderer Kennlinie.

### Option: PV-Zaun, ca. 30 m hochkant, davon ca. 20 m Sued und 10 m West

Ein senkrechter PV-Zaun ist fuer den Winter deutlich interessanter als ein
Norddach. Bei senkrechten Modulen ist der Sommerertrag geringer, aber der
Winterertrag bei tiefem Sonnenstand deutlich besser. Das passt gut zum
Waermepumpenprofil.

Grobe Flaechenannahme:

- Hochkant-Module mit ca. 1,13 m Breite plus Klemmen-/Randabstand.
- 20 m Suedanteil: geometrisch ca. 17 bis 18 Module, stringtechnisch sauber
  geplant mit 16 Modulen = 2x 8er-String.
- 10 m Westanteil: geometrisch ca. 8 Module, geplant mit 8 Modulen =
  1x 8er-String.
- Mit 500-W-Modulen ergibt das ca. 8,0 kWp Sued und 4,0 kWp West,
  zusammen ca. 12,0 kWp.

PVGIS-Grobrechnung fuer senkrechte Module, 14 % Systemverluste:

| Szenario | kWp | Jahresertrag | November | Dezember | Januar | Februar | Maerz |
|---|---:|---:|---:|---:|---:|---:|---:|
| 16 Module Sued-Zaun | ca. 8,0 kWp | ca. 5.886 kWh/Jahr | 10,3 kWh/Tag | 7,3 kWh/Tag | 8,2 kWh/Tag | 14,4 kWh/Tag | 18,8 kWh/Tag |
| 8 Module West-Zaun | ca. 4,0 kWp | ca. 2.033 kWh/Jahr | 1,7 kWh/Tag | 1,0 kWh/Tag | 1,2 kWh/Tag | 2,9 kWh/Tag | 5,3 kWh/Tag |
| Zaun gesamt Sued + West | ca. 12,0 kWp | ca. 7.919 kWh/Jahr | 12,0 kWh/Tag | 8,3 kWh/Tag | 9,4 kWh/Tag | 17,3 kWh/Tag | 24,1 kWh/Tag |

Bewertung:

- Die 20 m Sued-Zaun bringen mit 16 Modulen im Dezember grob 7,3 kWh/Tag.
  Das ist fuer Winter
  deutlich wertvoller als die komplette 14-kWp-Nordseite vom Schuppen.
- Die 10 m West-Zaun bringen im Dezember nur ca. 1 kWh/Tag, helfen aber in
  Uebergangszeit und beim Nachmittags-/Abendprofil.
- Bifaziale Glas-Glas-Module koennen am Zaun sinnvoll sein, wenn Rueckseitenlicht
  nicht verschattet wird und der Untergrund hell/reflektierend ist.
- Schnee ist beim Zaun weniger problematisch als auf flachen Daechern.
- Zaun-PV braucht aber eine saubere mechanische Planung: Windlast, Fundament,
  Beruehrschutz, Kabelschutz, Potentialausgleich und Vandalismus-/Tierschutz.

Empfehlung:

- 20 m Sued-Zaun ernsthaft einplanen, wenn die Mechanik bezahlbar ist.
- Die restlichen 10 m West-Zaun mit 8 Modulen als eigenen 8er-String planen.
- Fuer Winterautarkie ist der Sued-Zaun deutlich hilfreicher als die
  Schuppen-Nordseite.
- Eigener MPPT/Stringplan fuer den Zaun, weil senkrechte Module ein anderes
  Ertragsprofil haben als die Dachflaechen.

### Gesamt-Modulplanung: Dach voll belegen, 450/455/460 W vs. 500 W

Diese Rechnung ist eine Grobplanung aus dem Satellitenbild. Als Massstab wurde
das rechte Nebengebaeude mit 15 m Laenge verwendet. Die echten Dachmasse,
Dachneigungen, Randabstaende, Brandschutzabstaende und Hindernisse muessen vor
Bestellung nachgemessen werden.

Wichtig: Ziel ist nicht, auf eine bestimmte kWp-Groesse zu kommen, sondern die
verfuegbaren Dach- und Zusatzflaechen voll zu belegen. Deshalb muss bei
gleicher Modulanzahl verglichen werden. Das bestehende Angebot zeigt 65
Modulplaetze auf den Daecherflaechen. Wenn auf diese 65 Plaetze statt 455-Wp-
Modulen 500-Wp-Module passen, steigt die Dachleistung von 29,575 kWp auf
32,5 kWp.

Preisstand Recherche 2026-06-28:

| Modulklasse | Guenstiger Kandidat | Preis | Preis pro kWp | Abmessung fuer Planung | Quelle |
|---|---|---:|---:|---|---|
| 450 W exakt | JA Solar 450 W bifazial Glas-Glas Full Black, Palettenpreis | 67,90 EUR/Stk. | ca. 151 EUR/kWp | ca. 1,76 x 1,13 m als 450-W-Klasse | https://solarhandel24.de/collections/ja-solar |
| 450-W-Klasse besserer €/Wp | JA Solar 460 W bifazial Glas-Glas Black Frame, Palettenpreis | 64,90 EUR/Stk. | ca. 141 EUR/kWp | ca. 1,76 x 1,13 m als 54-Zell-Klasse | https://solarhandel24.de/collections/ja-solar |
| 500 W | JA Solar 500 W bifazial Glas-Glas Full Black JAM60D41 LB, Palettenpreis | 74,90 EUR/Stk. | ca. 150 EUR/kWp | 1,953 x 1,134 m | https://solarhandel24.de/products/ja-solar-500w-bifazial-glas-glas-full-black-jam60d41-lb-staffelpreis |

Bewertung Modulpreis:

- Exakt 450 W und 500 W sind praktisch gleich teuer pro kWp.
- Bei gleicher Modulanzahl sind 500-W-Module deutlich attraktiver, weil sie
  mehr kWp auf derselben Flaeche liefern.
- Wenn Dachflaechen kurz/verwinkelt sind, kann die kuerzere 450-/460-W-Klasse
  mehr Module erlauben und dadurch trotz kleinerem Einzelmodul besser passen.
- Wenn es nicht exakt 450 W sein muss, ist die 460-W-Klasse aktuell der
  preislich beste Treffer.

#### Belegungsszenarien

Annahmen:

- Das bestehende Elektrikerangebot wird als 65x 455 Wp = 29,575 kWp Dach-PV
  gewertet.
- Schuppen-Nordseite: ca. 14 x 5 m, rechnerisch 28 Module ohne harte
  Rand-/Hindernisreserve.
- PV-Zaun: 30 m hochkant, davon 20 m Sued und 10 m West. Fuer saubere
  Victron-Strings werden 16 Module Sued und 8 Module West als erste
  Planungsvariante angesetzt.
| Szenario | Modulplaetze | 455 W Bestand | 500 W bei gleicher Plaetzezahl | Mehrleistung 500 W vs. 455 W | Mehrkosten Module | Grober Mehrertrag/Jahr | Amortisation Mehrkosten bei 25 ct/kWh |
|---|---:|---:|---:|---:|---:|---:|---:|
| Dach laut Angebot | 65 | 29,575 kWp | 32,50 kWp | +2,925 kWp | ca. +455 EUR | ca. +2.989 kWh/a | ca. 0,6 Jahre |
| Dach + 16 Module Sued-Zaun | 81 | 36,855 kWp | 40,50 kWp | +3,645 kWp | ca. +567 EUR | ca. +3.724 kWh/a | ca. 0,6 Jahre |
| Dach + 16 Module Sued-Zaun + Nordschuppen | 109 | 49,595 kWp | 54,50 kWp | +4,905 kWp | ca. +763 EUR | ca. +5.012 kWh/a | ca. 0,6 Jahre |
| Dach + 24 Module Zaun (16 Sued + 8 West) + Nordschuppen | 117 | 53,235 kWp | 58,50 kWp | +5,265 kWp | ca. +819 EUR | ca. +5.379 kWh/a | ca. 0,6 Jahre |

Die Mehrkosten von 455 W auf 500 W amortisieren sich rechnerisch extrem
schnell, weil die Modulpreis-Differenz klein ist. Entscheidend ist nicht der
Preis pro kWp, sondern ob das groessere 500-W-Modul mechanisch auf die gleichen
Plaetze passt. Wenn ja, sollte auf den Hauptflaechen sehr wahrscheinlich 500 W
verwendet werden.

#### Realistischere Amortisation

Fuer die Gesamtanlage zaehlen Unterkonstruktion, Kabel, DC-Verteilung,
MPPT-Eingang, Arbeitszeit, Geruest/Steiger, Anmeldung, Zaunmechanik und
Elektriker mit. Das bestehende GSB-Angebot enthaelt 29,575 kWp PV-Material
plus Zaehlerschrank. Die reine PV-Materialposition liegt bei 12.764,11 EUR,
also ca. 431,58 EUR/kWp. Das Gesamtangebot inklusive Zaehlerschrank liegt bei
14.202,94 EUR, also ca. 480,23 EUR/kWp.

| Bereich | Sinnvolle Annahme | Amortisation bei 25 ct/kWh und 70-90 % Nutzung |
|---|---:|---:|
| Bestehendes GSB-Angebot 29,575 kWp + Zaehlerschrank | 14.203 EUR | ca. 2,1 bis 2,6 Jahre |
| 20 m Sued-Zaun, Module + einfache Mechanik | grob 4.000 bis 7.500 EUR | ca. 2,7 bis 5,0 Jahre |
| Nordschuppen, wenn Montage guenstig mitlaeuft | grob 5.000 bis 8.000 EUR | ca. 3,0 bis 6,0 Jahre, aber wenig Winterwirkung |
| 30 m Zaun komplett, 20 m Sued + 10 m Ost/West | grob 6.000 bis 11.000 EUR | ca. 3,0 bis 6,5 Jahre |

Fazit aus Modulvergleich:

- Fuer die Hauptdachflaechen wuerde ich zuerst mit 500-W-Modulen planen, weil
  bei gleicher Modulanzahl rund 9,9 % mehr Leistung auf das Dach kommt.
- Fuer enge/verwinkelte Dachbereiche alternativ 450-/460-W-Module pruefen,
  wenn dadurch mehr Plaetze entstehen als mit den groesseren 500-W-Modulen.
- Den 20-m-Sued-Zaun priorisieren, weil er fuer Winter pro Modul am meisten
  bringt.
- Die Nordseite vom Schuppen nur mitnehmen, wenn der Montagepreis sehr niedrig
  ist oder die Flaeche fuer Jahresertrag/Autoladung bewusst gewollt ist.
- Vor Bestellung muss ein echter Belegungsplan in Meter gemacht werden:
  Dachkanten, First/Traufe, Hindernisse, Randabstaende, Modulorientierung,
  Wartungswege und Stringspannung.

### Vorlaeufige Stringplanung mit Victron MPPT RS

Ziel: Dach und sinnvolle Zusatzflaechen voll belegen, aber elektrisch sauber
auf Victron MPPT RS aufteilen. Grundlage ist das 500-W-JA-Solar-Modul aus der
Modulrecherche.

Als zusaetzliche Plausibilisierung wurden OpenStreetMap-Gebaeudeumrisse und
ein ArcGIS-World-Imagery-Luftbildausschnitt zur Koordinate geprueft. Die
oeffentlichen Bilder reichen fuer eine bessere Orientierung als der Screenshot,
aber nicht fuer einen finalen Modulrasterplan. Die finale Belegung muss deshalb
weiterhin mit echten Dachmassen, Dachneigung, Ortgang-/Traufabstaenden,
Hindernissen und Verschattung abgeglichen werden.

Moduldaten JA Solar 500 W JAM60D41 LB:

- Pmax: 500 W.
- Voc: 43,85 V.
- Vmp: 37,11 V.
- Isc: 14,42 A.
- Imp: 13,61 A.
- Voc-Temperaturkoeffizient: -0,250 %/K.

Victron MPPT RS Grenzen:

- MPPT RS 450/100: 2 Tracker, 100 A Ladestrom, 5,76 kW DC-Ladeleistung total.
- MPPT RS 450/200: 4 Tracker, 200 A Ladestrom, 11,52 kW DC-Ladeleistung total.
- Je Tracker: 450 V max. PV-Spannung, 16 A Betriebsstrom, 20 A max.
  Kurzschlussstrom, 4.000 W DC-Ausgangsleistung.
- Keine zwei Strings parallel auf einen Tracker, weil 2x Isc schon ca.
  28,8 A waeren und damit ueber dem Victron-Grenzwert liegen.

Empfohlene Standard-Stringlaenge:

| String | STC-Leistung | Vmp | Voc STC | Voc ca. -20 C | Bewertung |
|---|---:|---:|---:|---:|---|
| 8 Module | 4,0 kWp | ca. 297 V | ca. 351 V | ca. 390 V | Standard, sehr gut passend. |
| 9 Module | 4,5 kWp | ca. 334 V | ca. 395 V | ca. 439 V | Zu knapp, wegen Kaltspannung und Victron-Hinweis zu Batterie-Float nicht empfehlen. |
| 4 bis 7 Module | 2,0 bis 3,5 kWp | ca. 148 bis 260 V | ca. 175 bis 307 V | unkritisch | Nur fuer kleine Restflaechen, elektrisch ok aber weniger elegant. |

**Planregel:** Pro Tracker ein String, Standard 8 Module. Unterschiedliche
Ausrichtungen, Neigungen oder Verschattungssituationen nicht in einen String
und nicht auf denselben Tracker mischen, wenn es vermeidbar ist.

#### Flaechenannahme fuer die erste Stringplanung

Das Angebot nennt 65 Modulplaetze, aber keine Einzelverteilung je Dach. Fuer
eine saubere Erstplanung wird auf 64 aktive Dachmodule gerastert; ein Platz
bleibt Reserve oder wird nur genutzt, wenn sich daraus ein sinnvoller
Reststring ergibt.

| Flaeche | Vorlaeufige Modulzahl | Strings | Bemerkung |
|---|---:|---:|---|
| Grosses Sueddach Schuppen | 32 | 4x 8 | Haupt-Winter-/Mittagsflaeche. |
| Grosses Ostdach Wohnhaus | 16 | 2x 8 | Morgen-/Vormittagsertrag. |
| Kleineres Westdach Wohnhaus | 8 | 1x 8 | Nachmittag-/Abendertrag. |
| 2 kleine Suedflaechen/Gauben Haupthaus | 8 gesamt | 1x 8 | Nur zusammenfassen, wenn gleiche Neigung/Ausrichtung und aehnliche Verschattung. |
| Angebot-Reserve | 1 | offen | Nicht auf Krampf verbauen, wenn daraus kein sauberer String entsteht. |

Zaun und optionale Nordseite:

| Flaeche | Vorlaeufige Modulzahl | Strings | Bemerkung |
|---|---:|---:|---|
| PV-Zaun Sued, ca. 20 m | 16 | 2x 8 | Sehr sinnvoll fuer Winter, sauberer als 17/18 Module mit Rest. |
| PV-Zaun West, ca. 10 m | 8 | 1x 8 | Guter Nachmittags-/Abendertrag, eigener Tracker. |
| Schuppen Nordseite optional | 24 | 3x 8 | Nur wenn guenstig; 28 Module waeren geometrisch moeglich, aber 24 sind stringtechnisch sauberer. |
| Schuppen Nord Rest optional | 4 | 1x 4 | Nur nutzen, wenn ein Tracker frei bleibt; sonst eher weglassen. |

#### Empfohlene MPPT-Variante

Da die MPPTs noch nicht gekauft sind, ist die Reglerauswahl frei optimierbar.
Fuer diese Anlage ist trotzdem eine Standardisierung auf MPPT RS 450/200 am
sinnvollsten, weil die 8er-Strings sehr gut zum 450-V-Eingang passen, pro
Tracker exakt ein String laeuft und alle grossen Flaechen sauber getrennt
werden koennen.

**Empfehlung ohne Nordseite:** 3x MPPT RS 450/200.

| MPPT | Tracker 1 | Tracker 2 | Tracker 3 | Tracker 4 | Logik |
|---|---|---|---|---|---|
| MPPT RS 450/200 #1 | Schuppen Sued S1, 8 Module | Schuppen Sued S2, 8 Module | Wohnhaus Ost E1, 8 Module | Wohnhaus West W1, 8 Module | Mischt Ausrichtungen auf Geraeteebene, aber jeder Tracker bleibt separat. |
| MPPT RS 450/200 #2 | Schuppen Sued S3, 8 Module | Schuppen Sued S4, 8 Module | Wohnhaus Ost E2, 8 Module | Gauben Sued G1, 8 Module | Zweite Dachgruppe. |
| MPPT RS 450/200 #3 | Zaun Sued ZS1, 8 Module | Zaun Sued ZS2, 8 Module | Zaun West ZW1, 8 Module | Reserve / kleiner Reststring | Zaun getrennt nach Sued und West. |

Damit sind belegt:

- Dach: 64 Module x 500 W = 32,0 kWp.
- Zaun: 24 Module x 500 W = 12,0 kWp.
- Summe ohne Nordseite: 88 Module = 44,0 kWp.
- Genutzte Tracker: 11 von 12.

Diese Variante nutzt 3 zu kaufende MPPT RS 450/200 sehr gut aus und laesst
einen Tracker fuer einen kleinen Reststring, Tests oder spaetere Korrektur.

Warum nicht kleiner mischen?

- 2x MPPT RS 450/200 reichen fuer die 8 Dachstrings.
- Der Zaun braucht 3 Tracker: 2x Sued, 1x West.
- Ein MPPT RS 450/100 haette nur 2 Tracker; fuer den West-Zaun braeuchte man
  dann zusaetzlich einen kleineren SmartSolar. Das spart kaum Geld, macht aber
  mehr Geraete, mehr Klemmstellen und weniger Reserve.
- 3x MPPT RS 450/200 ist deshalb die sauberere Kaufempfehlung.

#### Variante mit Schuppen-Nordseite

Wenn die Nordseite zusaetzlich belegt wird, reicht 3x MPPT RS 450/200 nicht
mehr sauber aus. Dann ist die einfache und robuste Erweiterung ein vierter
MPPT RS 450/200.

| MPPT | Tracker 1 | Tracker 2 | Tracker 3 | Tracker 4 |
|---|---|---|---|---|
| MPPT RS 450/200 #4 | Schuppen Nord N1, 8 Module | Schuppen Nord N2, 8 Module | Schuppen Nord N3, 8 Module | optional Nord-Rest 4 Module oder Reserve |

Damit waeren moeglich:

- Dach + Zaun: 44,0 kWp.
- Nord sauber: +12,0 kWp.
- Nord-Rest optional: +2,0 kWp.
- Summe mit sauberer Nordbelegung: ca. 56,0 kWp.
- Summe mit Nord-Rest: ca. 58,0 kWp.

Bewertung MPPT-Auswahl:

- MPPT RS 450/200 ist fuer diese Anlage der Standardregler: 4 Tracker,
  VE.Can, 48-V-System, passend zu 8er-Strings.
- MPPT RS 450/100 lohnt nur fuer kleine, isolierte 1- bis 2-String-Flaechen.
  Fuer die Gesamtanlage ist es einfacher, mit 450/200 zu standardisieren.
- Kleine SmartSolar 250-V-Regler sind sinnvoll fuer echte Restgruppen, z.B.
  4 Module auf einer kleinen Gaube oder Restflaeche. Sie sind nicht erste Wahl
  fuer die grossen 8er-Strings, koennen aber einzelne Restmodule retten.
- SmartSolar 150-V-Regler sind fuer 4 Module in Serie zu knapp, weil die
  Kaltspannung an die 150-V-Grenze laufen kann. Fuer Reststrings deshalb eher
  250-V-Regler verwenden.
- Die 9. Modulposition in einem String nicht nutzen, solange der finale
  Kaltspannungsnachweis und die Victron-Float-Grenze nicht sicher passen.

#### Reststring-Strategie

| Restgruppe | Empfehlung | Grund |
|---|---|---|
| 1 bis 2 Module | Nicht an 48-V-MPPT sinnvoll nutzbar; nur AC-Mikrowechselrichter/Optimierer-Sonderloesung oder weglassen | Spannung zu niedrig bzw. wirtschaftlich unschoen. |
| 3 Module | Nur pruefen, wenn ein 250-V-Regler frei/guenstig ist; nicht als Standard planen | Spannung reicht meistens, aber wenig elegant. |
| 4 Module | Sehr gut als 4S-Reststring auf freiem RS-Tracker oder SmartSolar MPPT 250/60 | Ca. 2 kWp, Vmp ca. 148 V, Voc kalt unkritisch. |
| 2x 4 Module gleiche Ausrichtung | SmartSolar MPPT 250/70 oder 250/100, 2 parallele 4S-Strings | Nur wenn beide Teilflaechen wirklich gleich ausgerichtet und aehnlich verschattet sind. |
| 8 Module | Immer bevorzugt als 8S auf MPPT RS 450/200 | Elektrisch und organisatorisch sauber. |

Fuer die zwei kleinen Suedflaechen/Gauben gibt es damit zwei Varianten:

- Wenn sie gleich ausgerichtet und kaum unterschiedlich verschattet sind:
  1x 8S als `GH-G1` auf MPPT RS 450/200.
- Wenn sie unterschiedlich verschattet sind: lieber 2x 4S getrennt auf zwei
  Tracker oder ein eigener SmartSolar 250/60 je Gaube. Das kostet mehr, holt
  aber aus kleinen Problemflaechen mehr heraus.

#### Modul-ID-Plan

Die vollstaendige Modul-/Stringliste liegt als CSV vor:
[pv-modulplan-stringliste.csv](./pv-modulplan-stringliste.csv)

Kurzuebersicht:

| Flaeche | Modul-IDs | Anzahl | Regler/Tracker |
|---|---|---:|---|
| Schuppen Sued | `SD-S1-01` bis `SD-S4-08` | 32 | MPPT RS #1 T1/T2, MPPT RS #2 T1/T2 |
| Wohnhaus Ost | `WO-E1-01` bis `WO-E2-08` | 16 | MPPT RS #1 T3, MPPT RS #2 T3 |
| Wohnhaus West | `WW-W1-01` bis `WW-W1-08` | 8 | MPPT RS #1 T4 |
| Haupthaus Gauben Sued | `GH-G1-01` bis `GH-G1-08` | 8 | MPPT RS #2 T4, nur wenn Verschattung passt |
| PV-Zaun Sued | `ZS-S1-01` bis `ZS-S2-08` | 16 | MPPT RS #3 T1/T2 |
| PV-Zaun West | `ZW-W1-01` bis `ZW-W1-08` | 8 | MPPT RS #3 T3 |
| Dachreserve | `DACH-RES-01` | 1 | Nur nutzen, wenn daraus ein sinnvoller Reststring entsteht |
| Schuppen Nord optional | `SN-N1-01` bis `SN-N3-08` | 24 | MPPT RS #4 T1/T2/T3 |
| Schuppen Nord Rest optional | `SN-R1-01` bis `SN-R1-04` | 4 | MPPT RS #4 T4, falls Nord belegt wird |

Offene Punkte fuer die finale Stringplanung:

1. Echte Modulzahl je Dachflaeche ausmessen.
2. Pruefen, ob auf den zwei kleinen Suedflaechen zusammen wirklich ein sauberer
   8er-String ohne unterschiedliche Verschattung moeglich ist.
3. Falls Gauben getrennt/verschattet sind: je Gaube eigener kleiner String auf
   eigenem Tracker oder Optimierer-/Mikrowechselrichter-Konzept pruefen.
4. Zaun Sued auf 16 Module planen; Restmeter lieber mechanisch Reserve als
   elektrisch schlechter Rest.
5. Zaun West auf 8 Module planen.
6. Nordseite nur mit eigenem MPPT und nur bei guenstigem Mehrpreis.

## Home-Assistant-Verbrauchsauswertung

Aus Home Assistant wurden am 2026-06-27 Livewerte und Historie gelesen. Die
Historie reicht bei den relevanten Energiezaehlern aktuell nur bis etwa
2026-06-17 zurueck; die 30-/90-Tage-Abfragen sind deshalb keine echten 30 oder
90 Tage, sondern ein ca. 10,8-Tage-Fenster.

Wichtige Messhierarchie:

- EG- und OG-Zaehler haengen direkt hinter dem Hauptzaehler.
- Alles andere haengt dahinter und ist damit in EG/OG bereits enthalten.
- Wallbox, Scheunen-IT und weitere Einzelmessungen sind Unterverbraucher, keine
  zusaetzliche Last oberhalb von EG/OG.
- `Netz Bezug` ist der reale Import aus dem Netz. `EG + OG` ist die gemessene
  Hauslast hinter dem Hauptzaehler. Die Differenz entsteht durch lokale
  Erzeugung, Einspeisung, Messzeitpunkte und ggf. nicht exakt gleichzeitig
  aktualisierte Sensoren.

### Livewerte beim Polestar-Laden

| Sensor | Wert |
|---|---:|
| Netz Bezug Leistung | ca. 12,68 kW |
| Strom EG Leistung | ca. 11,94 kW |
| Strom OG Leistung | ca. 0,74 kW |
| EG + OG gesamt | ca. 12,68 kW |
| Scheunen-IT Leistung, in EG/OG enthalten | ca. 0,28 kW |
| go-e / Wallbox Leistung, in EG/OG enthalten | ca. 10,37 bis 10,39 kW |
| Polestar 4 Ladeleistung, in Wallbox/EG enthalten | ca. 10,34 kW |
| Polestar 4 Batteriestand | ca. 84,2 % |
| Polestar 4 Restzeit bis voll | ca. 108 min |

### Historie

| Zeitraum | Netzbezug | EG | OG | EG+OG Last | Davon Scheunen-IT | Davon Wallbox |
|---|---:|---:|---:|---:|---:|---:|
| Letzte 7 Tage | 503,9 kWh / 72,0 kWh pro Tag | 458,1 kWh | 119,2 kWh | 577,3 kWh / 82,5 kWh pro Tag | 44,9 kWh | 273,6 kWh / 39,1 kWh pro Tag |
| Seit ca. 2026-06-17 | 724,2 kWh | 638,8 kWh | 181,3 kWh | 820,1 kWh | 69,7 kWh | 365,2 kWh |

Bewertung:

- Die letzten 7 Tage waren stark vom Auto gepraegt: ca. 274 kWh Wallboxenergie.
  Das ist in EG/OG bereits enthalten und entspricht fast der Haelfte der
  gemessenen EG+OG-Last in diesem Zeitraum.
- Der geplante Speicher mit 75 bis 85 kWh nutzbar kann eine grosse
  Tagesverschiebung schaffen, aber eine fast leere Polestar-4-Ladung kann ihn
  alleine fast vollstaendig verbrauchen.
- Mit zwei 18-kW-Waermepumpen ist Winterautarkie nicht ueber Batteriegroesse
  allein erreichbar. Wenn Netzbezug wirklich ausgeschlossen bleiben soll,
  braucht es bei schlechtem PV-Wetter konsequenten Lastabwurf, deutlich mehr
  Erzeugungs-/Speicherreserve oder eine andere Reservequelle.
- Sinnvoll ist ein erweiterbarer Speicherplatz: 8 Packs als Grundausstattung,
  mechanisch und elektrisch aber auf 16 Packs vorbereiten.

## Aktualisierte Kostenschaetzung

Die Ursprungssumme bleibt als Startwert stehen, aber Batterie, Victron/Lynx-
DC-Verteilung und Wechselrichter sind zu niedrig angesetzt, wenn die Anlage wirklich als
vollstaendiges ESS mit kompletter Hauslast auf AC-out, Ersatzstrom,
0-Einspeisung und moeglichst 0 Netzbezug geplant wird.

### Minimal realistisch mit 3x 6k5 und 6 Packs

| Bereich | Ansatz |
|---|---:|
| Ursprungssumme | 36.214 EUR |
| Korrektur Batterieboxen/BMS und Victron/Lynx-DC-Verteilung gegenueber alter Pauschale | +3.000 bis +5.000 EUR |
| Mehrkosten/Reserve AC-Verteilung, Bypass, Messung, Lastmanagement | +1.000 bis +3.000 EUR |
| **Neue grobe Summe** | **40.000 bis 44.000 EUR** |

Diese Variante braucht zwingend Lastabwurf fuer Wallbox und gestaffelte
Waermepumpen, nicht nur bei Netzausfall, sondern immer dann, wenn sonst
Netzbezug entstehen wuerde. Sie ist guenstig, aber nicht "alles gleichzeitig".

### Guenstige Kompromissvariante mit 3x MultiPlus-II 48/10000

| Bereich | Ansatz |
|---|---:|
| Ursprungssumme | 36.214 EUR |
| Mehrkosten 3x 10k statt 3x 6k5 | +1.400 bis +1.700 EUR |
| Korrektur Batterieboxen/BMS und Victron/Lynx-DC-Verteilung | +3.000 bis +5.000 EUR |
| Mehrkosten/Reserve AC-Verteilung, Bypass, Messung, Lastmanagement | +1.000 bis +3.000 EUR |
| **Neue grobe Summe** | **42.000 bis 46.000 EUR** |

Diese Variante bleibt ein guenstiger Kompromiss, wenn die Wallbox bei
PV-Mangel, niedrigem Batterie-SoC und hoher Waermepumpenlast automatisch
begrenzt wird. Fuer das Ziel "moeglichst alles ueber AC-out ohne Netzbezug" ist
sie aber nicht mehr die Hauptempfehlung.

### Komfortvariante fuer 22-kW-Auto plus hohe Hauslast

| Bereich | Ansatz |
|---|---:|
| Ursprungssumme | 36.214 EUR |
| Mehrkosten 3x 15k oder 6x 8000 statt 3x 6k5 | +4.600 bis +5.000 EUR |
| Groesserer DC-Bus, Sicherungen, Kabel, Waermeabfuhr | +2.000 bis +5.000 EUR |
| Manueller Wartungs-Bypass / Parallel-AC-Aufbau bei 6x 8000 | +300 bis +1.000 EUR |
| Batterie/Lynx-DC-Verteilung-Korrektur | +3.000 bis +5.000 EUR |
| **Neue grobe Summe** | **47.000 bis 54.000 EUR** |

Diese Variante ist technisch angenehmer, aber nicht mehr die
Billig-Topologie. 6x 8000 ist dabei besonders spannend, wenn Modularitaet,
Redundanz und bessere Verteilung im Schaltschrank wichtiger sind als moeglichst
wenige Geraete.

### Zielvariante 6x MultiPlus-II 48/8000 mit 8 Batterie-Packs, vorbereitet auf 16

| Bereich | Ansatz |
|---|---:|
| Ursprungssumme | 36.214 EUR |
| Mehrkosten 6x 8000 statt 3x 6k5 | +4.600 bis +5.000 EUR |
| Batterie-Korrektur gegenueber alter Zell-/Gehaeuseposition: 8 Packs Heymy-Zellen + Gehaeuse/BMS, Erweiterung auf 16 Packs vorbereitet | +800 bis +1.700 EUR vor Versand/DDP/Zoll, ohne optionale weitere 8 Packs |
| Victron/Lynx-DC-Verteilung, Sicherungen, Kabel, Waermeabfuhr | +3.000 bis +6.000 EUR |
| Manueller Wartungs-Bypass / Parallel-AC-Aufbau | +300 bis +1.000 EUR |
| AC-Verteilung, Lastmanagement, Messung, Reserve | +1.500 bis +4.000 EUR |
| **Neue grobe Summe** | **47.000 bis 56.000 EUR plus finale Versand-/DDP-/Montageklaerung** |

Diese Summe ist die realistischere Planungszahl fuer die Variante, die deinem
Ziel am naechsten kommt: komplette Hauslast ueber Victron AC-out, 22-kW-Auto
moeglich, Waermepumpen eingebunden, Netzbezug im Regelbetrieb vermeiden.

## Noch fehlende oder zu klaerende Positionen

### Waermepumpen / Hydraulik

| Thema | Warum wichtig |
|---|---|
| Exaktes WP-Modell und Datenblatt | Modbus, Freigabe, Sollwertvorgabe und Fehlerkontakte vor Bestellung klaeren. |
| Hydraulikpumpen fuer die 18-kW-WPs | Im Lastenheft steht, dass bei der favorisierten Sunex die Umwaelzpumpe nicht integriert ist. |
| Sicherheitsgruppe, Ausdehnungsgefaess, Magnetit-/Schlammabscheider | In der Grobkalkulation nicht sichtbar. |
| Frostschutzkonzept Monoblock | Glykol, Notumlauf, Ablaufventile oder Frostschutzventile entscheiden. |
| Kondensat, Fundamente, Schallschutz, Abtauwasser | Oft nicht im reinen Geraetepreis enthalten. |
| 400-V-Zuleitungen, Absicherung, FI/LS, Lastmanagement | Muss mit PV/ESS und Hausanschluss zusammen geplant werden. |
| Waermemengenzaehler / Strommessung je WP | Fuer COP-Auswertung in HA sehr sinnvoll. |
| Warmwasser-WP Anschlussmaterial | Trinkwassersicherheitsgruppe, Ablauf, Zirkulation, Legionellenstrategie klaeren. |

## Bewertung

Die Grobkalkulation ist als erste Hausnummer brauchbar, aber noch nicht als
bestellfertige Liste. Der wichtigste Punkt ist nicht die PV-Groesse, sondern
die Gleichzeitigkeitsfrage: 22-kW-Polestar, zwei Waermepumpen und ganze
Hauslast koennen nicht einfach an einem 18-kW-Victron-System haengen, wenn im
Alltag wirklich alles ueber AC-out laufen und moeglichst kein Netzbezug
entstehen soll.

Auf Basis der neuen Zielsetzung ist 6x MultiPlus-II 48/8000 mit 8 Batterie-
Packs als Grundausstattung und Vorbereitung auf 16 Packs die passendere
Planungsbasis. 3x 10k bleibt eine guenstigere
Kompromissvariante, aber fuer 22-kW-Polestar plus Waermepumpen und moeglichst
0 Netzbezug ist sie zu eng. Auch mit 6x 8000 bleibt Lastmanagement noetig,
aber es wird nicht mehr jede groessere Last sofort zum Problem.

Die Akkugroesse loest jedoch nicht das Winterproblem: 8 Packs sind fuer
Tagespuffer und Leistung sinnvoll, aber bei Dezemberertraegen um ca. 23 kWh pro
Tag und Waermepumpenlast keine Garantie fuer 100 % Autarkie. 16 Packs machen
mehrtaegige Pufferung deutlich entspannter, ersetzen aber keinen saisonalen
Speicher. Fuer mehrere dunkle Wintertage braucht es Lastabwurf, mehr
Wintererzeugung oder eine Reservequelle. Ein dynamischer Stromtarif ist deshalb sinnvoll: Der Speicher
kann im Winter gezielt in guenstigen Preisfenstern geladen werden und
ueberbrueckt dann teure Zeitfenster.

## Naechste Planungsschritte

1. Elektrikerangebot GSB klaeren: Montage, Geruest/Steiger, Anmeldung,
   AC-Anschluss, Pruefprotokoll, Stringplan und Inbetriebnahme als enthalten
   bestaetigen lassen oder als Nachtrag anfragen.
2. Moduldaten und Dachbelegung eintragen: 65x 455 Wp aus dem Angebot,
   Dachflaechen, Ausrichtung, Neigung, Stringlaengen.
3. Echten Modulrasterplan zeichnen: Dach voll belegen, 450/460-W-Klasse und
   500-W-Klasse je Dachflaeche nach Anzahl moeglicher Modulplaetze vergleichen,
   Randabstaende, Hindernisse, Wartungswege.
4. Stringplan finalisieren: 8er-Strings bevorzugen, je Tracker nur ein String,
   Kaltspannung pruefen, Gaubenverschattung separat bewerten.
5. Schuppen-Nordseite als Option pruefen: echte Neigung, Verschattung,
   Modulanzahl, Mehrpreis pro kWp, eigener MPPT/Stringplan.
6. PV-Zaun pruefen: 20 m Sued priorisieren, restliche 10 m nach Ausrichtung
   bewerten, Windlast/Fundament/Beruehrschutz, bifaziale Module, eigener MPPT.
7. Zielvariante 6x MultiPlus-II 48/8000 pruefen: je 2 Geraete pro Phase,
   Haus dauerhaft auf AC-out, AC-out 63 A, manueller Bypass- und
   Wartungsumschalter.
8. Batteriekonzept anfragen: Grundausstattung 8x 16s mit 128 Heymy/E-V-E MB31
   Zellen. Gehaeuse parallel bei Senloong, ASGOFT, BetterESS und EEL anfragen:
   echter Preis fuer 8 Stk., DDP, JK-BMS/Display/Sicherung/Busbars enthalten,
   Victron-CAN/RS485, Zertifikate und Garantie. Vorbereitung der Anlage auf
   16 Packs einplanen und Angebot optional fuer weitere 8 Packs anfragen.
9. Victron/Lynx-DC-Verteilung planen: Batteriegruppen, MultiPlus-Abgaenge,
   MPPT-Abgaenge, Sicherungen in den Lynx-Komponenten, Kabelquerschnitte,
   Precharge nur falls nicht in Box/BMS geloest, Beschriftung.
10. AC-Schema mit Elektriker zeichnen: Zaehlerpunkt Haupthaus, Hinleitung
   Heizungsraum, Victron AC-in, AC-out Rueckleitung, Bypass, RCD/LS/SPD.
11. Lastmanagement in HA definieren: Wallbox 0/6/11/22 kW, WP1/WP2 Sperre oder
   Leistungsstufen, Warmwasser-WP nachrangig, Batterie-SoC-Grenzen.
12. Winterstrategie definieren: SoC-Schwellen fuer Wallbox-Stopp,
   Waermepumpen-Priorisierung, Warmwasser-Absenkung, Komfortabsenkung und
   optionaler Reservequelle.
13. Dynamischen Tarif pruefen: intelligentes Messsystem, Anbieter, API in Home
   Assistant, Preisgrenzen fuer Akku-Netzladung, Wallbox und Waermepumpen.
14. Danach zweite Kalkulationsrunde mit drei Spalten fuehren:
   bereits angeboten, noch zu kaufen, bewusst optional.
