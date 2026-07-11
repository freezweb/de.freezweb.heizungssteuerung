# Prodino Pool Firmware

Firmware fuer den KMP Prodino MKR Zero Ethernet als Pool-I/O per Modbus TCP:

- Relay 1: Pool-Nachfuellventil
- Relay 2: Flockungsmittel-Peristaltikpumpe
- OptoIn1: Schwimmer, Kontakt geschlossen = Pool zu leer

Modbus TCP:

- Port: `502`
- Unit-ID: `1`
- Coils `0..3`: Relais 1..4, schreibbar per FC05/FC15, lesbar per FC01
- Discrete Inputs `0..3`: OptoIn 1..4, lesbar per FC02
- Holding/Input Register FC03/FC04:
  - `0`: Uptime Sekunden Low-Word
  - `1`: Uptime Sekunden High-Word
  - `2`: Relaismaske, Bit 0 = Relais 1
  - `3`: Eingangsmaske, Bit 0 = OptoIn 1
  - `4`: Firmware-Version

Sicherheit:

- Wenn 120 Sekunden kein Modbus-Schreibkommando kommt, werden alle Relais ausgeschaltet.
- DHCP wird zuerst versucht; als Fallback nutzt die Firmware `10.1.1.146`.

Flashen:

```powershell
cd hardware\prodino-pool\firmware
pio run -t upload
pio device monitor -b 115200
```
