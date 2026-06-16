#!/usr/bin/env bash
# Update-Skript: Code aus dem Repo neu nach /opt/heizung syncen und Service neu starten
set -euo pipefail

APP_DIR=/opt/heizung
SRC_DIR="$(dirname "$(readlink -f "$0")")/.."

if [[ $EUID -ne 0 ]]; then
  echo "Bitte mit sudo ausfuehren." >&2
  exit 1
fi

rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
  --exclude='state' --exclude='*.log' --exclude='config/*.yaml' \
  "$SRC_DIR/" "$APP_DIR/"

# Falls neue Beispiel-Configs hinzukamen, .yaml-Stubs anlegen
for f in io_map.yaml settings.yaml mqtt.yaml modbus_map.yaml; do
  if [[ ! -f "$APP_DIR/config/$f" ]]; then
    cp "$APP_DIR/config/${f}.example" "$APP_DIR/config/$f"
  fi
done

"$APP_DIR/.venv/bin/pip" install -e "$APP_DIR" >/dev/null
systemctl restart heizung.service
systemctl status heizung.service --no-pager -l | head -20
