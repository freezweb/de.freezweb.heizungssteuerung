# Home Assistant Visualisierung

Diese Dateien bilden das Dashboard `Heizung` mit grafischem Hydraulikplan.

Live ist das Dashboard per HA-Storage-API unter `/dashboard-heizung/heizung`
angelegt. Die MQTT-Entities kommen per retained MQTT-Discovery und werden von
Home Assistant mit dem Geraetepraefix `heizung_hauptsteuerung_...` benannt.

## Dateien

| Datei | Ziel in HA |
|---|---|
| `packages/heizung_mqtt.yaml` | `/config/packages/heizung_mqtt.yaml` |
| `dashboards/heizung.yaml` | `/config/dashboards/heizung.yaml` |
| `www/heizung-hydraulik.svg` | `/config/www/heizung-hydraulik.svg` |

## configuration.yaml

Falls noch nicht vorhanden:

```yaml
homeassistant:
  packages: !include_dir_named packages

lovelace:
  mode: yaml
  dashboards:
    heizung:
      mode: yaml
      title: Heizung
      icon: mdi:heat-pump
      show_in_sidebar: true
      filename: dashboards/heizung.yaml
```

Danach Home Assistant YAML pruefen und neu laden bzw. neu starten.

## MQTT-Prinzip

HA sendet Senken-Anforderungen als JSON nach:

- `heizung/anforderung/fbh_eg/set`
- `heizung/anforderung/klima_og/set`
- `heizung/anforderung/nebengeb/set`
- `heizung/anforderung/pool/set`
- `heizung/anforderung/bwwp/set`

Der RevPi spiegelt den gemeinsamen Waermekreis zurueck:

- `heizung/gesamt/active`
- `heizung/gesamt/vl_soll/state`
- `heizung/routing/state`
- `heizung/freigabe/state`

Pool, Haus und Nebengebaeude sind Senken am gemeinsamen Gesamtwaermekreis.
WP1/WP2 sind Quellen und nicht fest einer Senke zugeordnet.

## Freigaben

Das Dashboard enthaelt Schalter fuer jede Quelle und jede Senke:

- Quellen: Oelbrenner, WP1, WP2, BWWP
- Senken: FBH EG, Klima OG, Nebengebaeude, HK Backup, Pool

Nur freigegebene Komponenten werden von der Regelung verwendet. Damit kann WP1
oder WP2 nach dem Einbau durch Setzen des Hakens in die Sequenz aufgenommen
werden, waehrend der Oelbrenner anfangs weiter freigegeben bleibt.
