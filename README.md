# de.freezweb.heizungssteuerung

Heizungssteuerung auf Revolution Pi Connect 4 mit Anbindung an Home Assistant (MQTT).

Komplette Spezifikation: siehe [LASTENHEFT.md](LASTENHEFT.md).

## Komponenten
- **Hauptsteuerung** Heizungsraum (RevPi #1, `10.1.25.10`)
- **Slave-Steuerung** Hauptkeller (RevPi #2, `10.1.25.11`, sp&auml;ter)
- **Visualisierung + History**: Home Assistant via MQTT-Discovery
- **Failsafe**: Witterungsgef&uuml;hrte Heizkurve bei MQTT-/HA-Ausfall

## Stack
- Python 3.11 (Asyncio)
- `revpimodio2` &mdash; RevPi-I/O
- `paho-mqtt` &mdash; HA-Kopplung
- `pymodbus` &mdash; W&auml;rmepumpen, Klima-Innenger&auml;te, Slave-CPU
- systemd (`Type=simple, Restart=on-failure`)

## Verzeichnisstruktur
```
src/heizung/        Hauptcode
config/             Live-Configs (gitignored, *.example committet)
pictory/            RevPi-PiCtory-Export
tests/              Pytest
deploy/             systemd-Unit + install/update Scripts
docs/               Hydraulik-, I/O- und MQTT-Doku
```

Wichtige Hardware-Planung:
- [docs/revpi-modulplanung.md](docs/revpi-modulplanung.md)
- [docs/io-belegung.md](docs/io-belegung.md)

## Quick start (Entwicklung)
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
cp config/settings.yaml.example config/settings.yaml
# Anpassen, dann:
python -m heizung
```

## Deployment auf RevPi
Siehe `deploy/install.sh`.

## Phasen-Plan
Siehe [LASTENHEFT.md Abschnitt 10](LASTENHEFT.md#10-phasen-plan-reihenfolge).
