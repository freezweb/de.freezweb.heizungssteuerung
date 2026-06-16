# RevPi-Modulplanung

Stand: 2026-06-16

## Bestand

| Typ | Anzahl | Kapazitaet je Modul | Gesamt |
|---|---:|---|---|
| CPU RevPi Connect 4 | 4 | max. 10 Erweiterungsmodule je CPU | 4 Steuerungen moeglich |
| DIO | 3 | 14 DI + 14 DO | 42 DI + 42 DO |
| DI | 17 | 16 DI | 272 DI |
| AIO | 11 | 4 AI + 2 RTD + 2 AO | 44 AI + 22 RTD + 22 AO |

## Verteilung

| Standort | Module | Begruendung |
|---|---|---|
| Heizungsraum Hauptsteuerung | 2x DIO + 8x AIO + CPU | 21 DO, 16 DI, 16 direkte RTD, 10 AO; Connect-4-Limit voll genutzt |
| Hauptkeller Slave | 1x DIO + 3x AIO + CPU | Mischer/Pumpen lokal, 5 RTD benoetigt, Reserven vorhanden |
| Reserve | 2x CPU + 17x DI | Fuer spaetere Eingangsstationen, Zaehler, Taster, Stoermeldungen |

## Offene Designentscheidung

Die Hauptsteuerung hat mit 8 AIO nur 16 direkte RTD-Kanaele. Das ist fuer den
priorisierten Sensorumfang ausreichend, aber nicht fuer jeden moeglichen
Temperaturpunkt als eigener direkter PT1000-Fuehler.

Loesung:
- Kritische Fuehler direkt auf RTD legen.
- WP-interne Temperaturen primaer per Modbus lesen.
- Zusaetzliche Temperaturen bei Bedarf per 0-10V/4-20mA-Messumformer auf AI legen.
- Alternativ spaeter eine dritte CPU als dezentrale Sensorstation nutzen.

## Quellen

- RevPi DIO: https://revolutionpi.com/en/docs/revpi-dio
- RevPi DI: https://revolutionpi.com/en/docs/revpi-di
- RevPi AIO: https://revolutionpi.com/en/docs/revpi-aio
- RevPi Connect 4: https://revolutionpi.com/en/docs/revpi-connect-4
