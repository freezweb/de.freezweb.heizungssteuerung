# Hydraulik-Schema (Endausbau)

Grundprinzip: **WP1 und WP2 speisen beide denselben Gesamtwaermekreis**.
Haus, Nebengebaeude, Pool und HK-Backup sind Senken an diesem gemeinsamen
Erzeuger-/Verteilerkreis. Es gibt keine feste Zuordnung "WP1 = Haus" oder
"WP2 = Pool"; jede aktive Waermequelle kann jede aktive Senke bedienen.

```mermaid
flowchart LR
    subgraph HR[Heizungsraum]
        WP1[WP1 16 kW Monoblock]
        WP2[WP2 16 kW Monoblock]
        BWWP[Brauchwasser-WP<br/>200 L]
        SVW1[WP1-Kreisventil<br/>in Sammelvorlauf]
        SVW2[WP2-Kreisventil<br/>in Sammelvorlauf]
        VL[Sammelvorlauf<br/>Gesamtwaermekreis]
        RL[Sammelruecklauf<br/>Gesamtwaermekreis]
        BR[Brunnenpumpe]
        WTK[WT Brunnen-Kuehlung]
        SVP[Pool-Kreisventil]
        PPool[Pumpe Pool-Kreis]
        PWT[Pool-Waermetauscher]
        SVN[Nebengebaeude-Kreisventil]
        PNeb[Pumpe Nebengebaeude]
        SVH[HK-Backup-Kreisventil OG]
        BWS[Trinkwarmwasser-<br/>Speicher 200 L]
    end

    subgraph HK[Hauptkeller]
        SVF[3WV Mischer FBH]
        PF[Pumpe FBH-EG]
        SVK[3WV Mischer Klima-OG]
        PK[Pumpe Klimakreis-OG]
    end

    subgraph EG[Erdgeschoss]
        FBH[Fussbodenheizung<br/>+ Shelly-Ventile]
    end

    subgraph OG[Obergeschoss]
        K1[Klima Kind]
        K2[Klima Buero]
        K3[Klima Schlaf]
        K4[Klima Bad]
        K5[Klima Flur]
        HKB[Heizkoerper-Backup OG]
    end

    subgraph POOL[Pool]
        BEC[Pool 30 m3<br/>35 Grad ganzjaehrig]
    end

    subgraph NEB[Nebengebaeude]
        NHK[Heizkreis Nebengebaeude]
    end

    WP1 --> SVW1 --> VL
    WP2 --> SVW2 --> VL
    VL --> SVF --> PF --> FBH --> RL
    VL --> SVK --> PK --> K1 & K2 & K3 & K4 & K5 --> RL
    VL --> SVN --> PNeb --> NHK --> RL
    VL --> SVH --> HKB --> RL
    VL --> SVP --> PPool --> PWT --> BEC --> RL
    BWWP --> BWS
    BR --> WTK --> SVK
```

## Regelungsprinzip

- **Gesamtwaermekreis**: Alle normalen Heiz-/Pool-Anforderungen werden gesammelt.
  Der hoechste geforderte Vorlauf plus Mischerreserve ergibt den WP-Sollwert.
- **WP1/WP2**: Beide WPs bekommen denselben Sollwert fuer den Sammelvorlauf.
  Bei kleiner Last laeuft eine WP, bei mehreren aktiven Senken oder hoher Last
  laufen beide parallel. Laufzeitrotation wird separat gepflegt.
- **Pool**: Der Pool ist eine Senke am Gesamtwaermekreis. Er wird ueber sein
  Kreisventil und die Pool-Kreis-Pumpe zugeschaltet, nicht ueber eine exklusiv
  zugeordnete Waermepumpe.
- **Nebengebaeude / Haus / HK-Backup**: Ebenfalls Senken am gemeinsamen Kreis.
- **BWWP**: Die Brauchwasser-WP bleibt ein separater kleiner Steuerkreis fuer den
  Trinkwarmwasserspeicher.
- **Brunnen-WT**: Eigener Kuehlpfad in den Klimakreis, getrennt von der
  Waermeerzeugerlogik.

## Wichtige Konsequenz

Software, HA-Visualisierung und Beschriftung muessen immer von Quellen und
Senken sprechen:

- Quellen: `wp1`, `wp2`, spaeter ggf. `oelbrenner`
- Gemeinsamer Knoten: `gesamtwaermekreis`
- Senken: `fbh_eg`, `klima_og`, `nebengeb`, `hk_backup`, `pool`

Damit bleibt die Anlage routingfaehig: **alles kann auf alles geroutet werden**,
solange Ventilstellung, Pumpenfreigabe und Solltemperatur dazu passen.
