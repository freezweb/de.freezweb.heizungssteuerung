#!/usr/bin/env bash
# Installations-Skript fuer den RevPi
# Aufruf:  sudo bash deploy/install.sh
set -euo pipefail

APP_DIR=/opt/heizung
APP_USER=heizung

if [[ $EUID -ne 0 ]]; then
  echo "Bitte mit sudo ausfuehren." >&2
  exit 1
fi

echo "==> System-Pakete"
apt-get update -qq
apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip \
  git revpi-tools python3-revpimodio2

echo "==> User $APP_USER anlegen"
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"
fi
# Zugriff auf RevPi-I/O. Auf aktuellen RevPi-Images heisst die Gruppe kleingeschrieben.
PICONTROL_GROUP=picontrol
if ! getent group "$PICONTROL_GROUP" >/dev/null 2>&1; then
  PICONTROL_GROUP=piControl
fi
usermod -aG "$PICONTROL_GROUP" "$APP_USER"

echo "==> Quellcode nach $APP_DIR"
mkdir -p "$APP_DIR"
SRC_DIR="$(dirname "$(readlink -f "$0")")/.."
rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
  --exclude='state' --exclude='*.log' "$SRC_DIR/" "$APP_DIR/"
mkdir -p "$APP_DIR/state" /var/log
chown -R "$APP_USER:$APP_USER" "$APP_DIR/state"
touch /var/log/heizung.log
chown "$APP_USER:$APP_USER" /var/log/heizung.log

echo "==> Python-Venv"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"

echo "==> Config-Stubs (falls noch nicht vorhanden)"
for f in io_map.yaml settings.yaml mqtt.yaml modbus_map.yaml; do
  if [[ ! -f "$APP_DIR/config/$f" ]]; then
    cp "$APP_DIR/config/${f}.example" "$APP_DIR/config/$f"
    chmod 640 "$APP_DIR/config/$f"
    chown root:"$APP_USER" "$APP_DIR/config/$f"
  fi
done

echo "==> systemd-Unit"
install -m 0644 "$APP_DIR/deploy/heizung.service" /etc/systemd/system/heizung.service
systemctl daemon-reload
# revpipyload zugunsten unserer Steuerung deaktivieren
systemctl disable --now revpipyload.service 2>/dev/null || true
systemctl enable heizung.service

echo ""
echo "Fertig. Naechste Schritte:"
echo "  1) sudo nano $APP_DIR/config/mqtt.yaml           # MQTT-Passwort eintragen"
echo "  2) sudo systemctl start heizung.service"
echo "  3) journalctl -u heizung -f"
