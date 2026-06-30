# Pumpengruppe RS485 Firmware

Erste Test-Firmware fuer die ESP32-Pumpengruppen-Platine.

## Funktionen in Version 0.1.0

- WLAN als Client, bei fehlender Verbindung Fallback-AP.
- Weboberflaeche fuer Status, Werteuebersicht, WLAN, RS485 und Mischerparameter.
- Web-Update unter `/update`.
- ArduinoOTA im lokalen Netz.
- Modbus-RTU-Slave mit den Registeradressen aus `docs/pumpengruppe-rs485-platine.md`.
- Optionaler Modbus-TCP-Server mit demselben Registersatz. Der Transport kann
  WLAN oder spaeter ein kabelgebundener IP-Pfad sein.
- Simulierte Vor-/Ruecklauftemperaturen, solange keine MAX31865-Hardware angeschlossen ist.
- Relais-/Mischerzustand und Bus-Watchdog als lauffaehige Logik.

## Flashen

```powershell
cd hardware\pumpengruppe-rs485\firmware
pio run -t upload
pio device monitor
```

Wenn kein WLAN konfiguriert ist oder die Verbindung fehlschlaegt, startet der
ESP32 einen Access Point:

- SSID: `Pumpengruppe-XXXXXX`
- Passwort: keines, offenes Einrichtungs-WLAN
- Web: `http://192.168.4.1/`
- Captive Portal: DNS leitet im Einrichtungs-WLAN auf die Weboberflaeche um.

Default-Login fuer die Weboberflaeche:

- Benutzer: `admin`
- Passwort: `admin`

Im offenen Einrichtungs-WLAN ist kein Login noetig. Sobald der ESP im normalen
WLAN erreichbar ist, schuetzt HTTP Basic Auth die Weboberflaeche. Bitte nach
dem ersten Test aendern.

## Vorlaeufige Pinbelegung

| Signal | GPIO |
|---|---:|
| Pumpe Relais | 25 |
| Mischer Freigabe | 26 |
| Mischer Richtung | 27 |
| RS485 TX | 17 |
| RS485 RX | 16 |
| RS485 DE/RE | 4 |
| RGB/SK6812 | 21 |
| SPI MOSI | 23 |
| SPI MISO | 19 |
| SPI SCK | 18 |

TX/RX/DE sind ueber die Weboberflaeche konfigurierbar, falls sich die finale
KiCad-Zuordnung noch aendert.

## Modbus

RTU und TCP verwenden denselben Registersatz:

- Holding Register 0..8: Master -> Board
- Input Register 0..8: Board -> Master

Modbus TCP ist ab Werk aktiv auf Port `502`. Die Unit-ID ist die eingestellte
Slave-ID, `255` wird ebenfalls akzeptiert. Falls nur RS485 genutzt werden soll,
kann TCP in der Weboberflaeche deaktiviert werden.
