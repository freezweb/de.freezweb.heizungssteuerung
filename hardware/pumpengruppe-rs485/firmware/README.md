# Pumpengruppe RS485 Firmware

Erste Test-Firmware fuer die ESP32-Pumpengruppen-Platine.

## Funktionen in Version 0.2.0

- WLAN als Client, bei fehlender Verbindung Fallback-AP.
- Weboberflaeche fuer Status, Werteuebersicht, WLAN, RS485 und Mischerparameter.
- Web-Update unter `/update`.
- ArduinoOTA im lokalen Netz.
- Modbus-RTU-Slave mit den Registeradressen aus `docs/pumpengruppe-rs485-platine.md`.
- Optionaler Modbus-TCP-Server mit demselben Registersatz. Der Transport kann
  WLAN oder spaeter ein kabelgebundener IP-Pfad sein.
- Optionaler MQTT-Client fuer Installationen ohne Modbus-Master.
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

## Konfiguration zuruecksetzen

Der Taster `BOOT/CFG RESET` liegt auf `GPIO0` gegen GND.

- kurzer Druck waehrend Reset/Power-Up: normaler ESP32-Bootloader/Flash-Modus
- langer Druck im laufenden Betrieb fuer mindestens 10 Sekunden:
  gespeicherte WLAN-, Web-, Modbus- und MQTT-Konfiguration wird geloescht,
  alle Ausgaenge werden abgeschaltet und der ESP startet neu

Danach startet wieder das offene Einrichtungs-WLAN.

## Vorlaeufige Pinbelegung

| Signal | GPIO |
|---|---:|
| Pumpe Relais | 35 |
| Mischer Freigabe | 36 |
| Mischer Richtung | 37 |
| RS485 TX | 17 |
| RS485 RX | 16 |
| RS485 DE/RE | 4 |
| RGB/SK6812 | 21 |
| SPI MOSI | 11 |
| SPI MISO | 13 |
| SPI SCK | 12 |
| RTD Vorlauf CS | 10 |
| RTD Ruecklauf CS | 9 |
| BOOT/CFG RESET | 0 |
| USB D- | native USB / GPIO19 |
| USB D+ | native USB / GPIO20 |

Die Platinenrevision nutzt `ESP32-S3-WROOM-1-N4`; der USB-UART-Baustein
entfaellt, Firmware/Monitor laufen direkt ueber natives USB-CDC.

J5 ist als Erweiterungsheader vorgesehen: `+5V`, `+3V3`, mehrfach `GND` sowie
freie S3-GPIOs `1`, `2`, `3`, `5`, `6`, `7`, `8`, `14`, `15`, `18`, `38`,
`39`, `40`, `41`, `42`. Diese Pins sind nicht fuer Relais, RS485, SPI, RGB,
USB oder Boot reserviert.

## Modbus

RTU und TCP verwenden denselben Registersatz:

- Holding Register 0..8: Master -> Board
- Input Register 0..8: Board -> Master

Modbus TCP ist ab Werk aktiv auf Port `502`. Die Unit-ID ist die eingestellte
Slave-ID, `255` wird ebenfalls akzeptiert. Falls nur RS485 genutzt werden soll,
kann TCP in der Weboberflaeche deaktiviert werden.

## MQTT

MQTT ist ab Werk deaktiviert und kann in der Weboberflaeche unter `MQTT`
aktiviert werden. Wenn kein Basis-Topic eingetragen ist, wird
`pumpengruppe/<hostname>` verwendet.

Command-Topics:

| Topic | Payload |
|---|---|
| `<base>/cmd` oder `<base>/set` | JSON, z.B. `{"pump":true,"target":56}` |
| `<base>/target/set` | Zielposition in Prozent, z.B. `56` |
| `<base>/pump/set` | `0/1`, `on/off`, `true/false` |
| `<base>/mode/set` | `auto`, `hand`, `cal_close`, `cal_open` |
| `<base>/modbus_tcp/set` | `0/1`, `on/off`, `true/false`, schaltet Modbus TCP sofort am ESP |

Status-Topics:

| Topic | Inhalt |
|---|---|
| `<base>/availability` | `online` / `offline` |
| `<base>/state` | JSON mit Firmware, IP, Pumpe, Ziel, Position, Temperaturen, Fehlern |
| `<base>/position/state` | Mischerposition in Prozent |
| `<base>/target/state` | Zielposition in Prozent |
| `<base>/pump/state` | realer Pumpenausgang `0/1` |
| `<base>/pump_requested/state` | angeforderte Pumpe `0/1` |
| `<base>/vl_temp/state` / `<base>/rl_temp/state` | Vor-/Ruecklauf in Grad C |
| `<base>/fault/state` | Fehlercode |
| `<base>/moving/state` | Mischerfahrt aktiv `0/1` |
| `<base>/modbus_tcp/state` | Modbus TCP aktiv `0/1` |
| `<base>/heartbeat` | JSON mit `uptimeS`/`uptimeMs` als Lebenszeichen |

Die Statuswerte werden nach dem MQTT-Connect einmal vollstaendig gesendet und
danach nur noch bei geaenderter Payload erneut veroeffentlicht. Der Heartbeat
kommt weiterhin zyklisch im eingestellten Statusintervall, damit man sieht,
dass das Board noch arbeitet.

Einrichtungshilfe:

Beim MQTT-Verbinden veroeffentlicht das Board retained Hilfe- und Beispieltopics
unter `<base>/help/...` und `<base>/example/...`. Die echten Command-Topics
werden bewusst nicht retained vom Board beschrieben, damit ein alter retained
Befehl beim Reconnect nicht automatisch erneut ausgefuehrt wird.

Solange MQTT verbunden ist, gilt die Brokerverbindung als Watchdog-Lebenszeichen.
Wenn WLAN/Broker ausfaellt, greift der vorhandene Watchdog wie bei Modbus.
