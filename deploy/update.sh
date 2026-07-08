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
for f in io_map.yaml settings.yaml mqtt.yaml modbus_map.yaml io_map.keller_relais.yaml; do
  if [[ ! -f "$APP_DIR/config/$f" ]]; then
    cp "$APP_DIR/config/${f}.example" "$APP_DIR/config/$f"
  fi
done

# Zielgerichtete Live-Config-Migrationen. config/*.yaml werden bewusst nicht
# blind ueberschrieben, aber neue fest verdrahtete Kanaele muessen in der
# bestehenden Live-IO-Map ankommen.
python3 - <<'PY'
from pathlib import Path

path = Path("/opt/heizung/config/io_map.yaml")
if path.exists():
    text = path.read_text(encoding="utf-8")
    replacements = {
        "DI12": '  DI12: { module: DIO1, channel: I_12, pictory_name: "I_12",             komponente: "oelbrenner_wasserdruck_stoerung", beschreibung: "Oelbrenner Wasserdruck Stoerung", phase: A, polaritaet: NC_SAFE_HIGH }',
        "reserve_di_13": '  DI13: { module: DIO1, channel: I_13, pictory_name: "I_13",             komponente: "brenner_stoerung",  beschreibung: "Oelbrenner Stoermeldung",   phase: A }',
        "reserve_di_14": '  DI14: { module: DIO1, channel: I_14, pictory_name: "I_14",             komponente: "brenner_betrieb",   beschreibung: "Oelbrenner Betriebsmeldung", phase: A }',
        "DI15": '  DI15: { module: DIO2, channel: I_1,  pictory_name: "I_1_i17",          komponente: "oelbrenner_stb_stoerung", beschreibung: "Oelbrenner STB Stoerung", phase: A, polaritaet: NC_SAFE_HIGH }',
    }
    lines = text.splitlines()
    changed = False
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("DI12:") and "oelbrenner_wasserdruck_stoerung" not in line:
            lines[index] = replacements["DI12"]
            changed = True
        elif stripped.startswith("DI13:") and "reserve_di_13" in line:
            lines[index] = replacements["reserve_di_13"]
            changed = True
        elif stripped.startswith("DI14:") and "reserve_di_14" in line:
            lines[index] = replacements["reserve_di_14"]
            changed = True
        elif stripped.startswith("DI15:") and "oelbrenner_stb_stoerung" not in line:
            lines[index] = replacements["DI15"]
            changed = True
    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

"$APP_DIR/.venv/bin/pip" install -e "$APP_DIR" >/dev/null
systemctl restart heizung.service
systemctl status heizung.service --no-pager -l | head -20
