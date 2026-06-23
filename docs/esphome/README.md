# ESPHome Wasserverbrauch Pumpe

`wasserverbrauch-pumpe.yaml` ist der aktuell bekannte Stand des ESP32 am
Flowmeter der Brunnenpumpe.

## Ziel fuer die Brunnenregelung

Die ESPHome-Konfig stellt den Momentandurchfluss als lokalen Modbus-TCP-Server
per WLAN bereit.

| Register | Typ | Inhalt | Skalierung |
|---|---|---|---|
| 0 | Input Register | Wasserdurchfluss | L/min * 100 |
| 1/2 | Input Register | Wasserverbrauch Gesamt | L * 1000 |

Beispiel: Registerwert `125` bedeutet `1.25 L/min`.

## Modbus TCP

- TCP-Port: `502`
- Unit-ID: `1`
- Function 3 und 4 werden beantwortet
- Register 0: Durchfluss `L/min * 100`
- Register 1/2: Gesamtverbrauch `L * 1000`

## Anbindung an die Hauptsteuerung

ESPHome bringt `async_tcp` als TCP-Grundlage mit, aber keinen fertigen
Modbus-TCP-Server fuer diesen Flowmeter-Fall. Deshalb startet die YAML in
`on_boot` einen kleinen AsyncTCP-Server direkt aus einem Lambda. Es wird keine
zweite Datei und keine External Component benoetigt.

Die Hauptsteuerung liest:

- Host: `wasserverbrauch-pumpe.local` bzw. die per mDNS aufgeloeste IP
- TCP-Port: `502`
- Unit-ID: `1`
- Function: `4` / Input Register
- Register: `0`
- Skalierung: `100`
