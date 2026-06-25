$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Cli = Get-Command kicad-cli -ErrorAction SilentlyContinue
if (-not $Cli) {
    $Candidates = @(
        "C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
        "C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
        "C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
        "C:\Program Files\KiCad\bin\kicad-cli.exe"
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path $Candidate) {
            $Cli = [pscustomobject]@{ Source = $Candidate }
            break
        }
    }
}

if (-not $Cli) {
    throw "kicad-cli wurde nicht gefunden. KiCad installieren oder kicad-cli.exe in PATH aufnehmen."
}

$KiCadRoot = Split-Path -Parent (Split-Path -Parent $Cli.Source)
$FontConfig = Join-Path $KiCadRoot "etc\fonts\fonts.conf"
if (Test-Path $FontConfig) {
    $env:FONTCONFIG_FILE = $FontConfig
}

$Board = Join-Path $ProjectRoot "pumpengruppe-rs485.kicad_pcb"
$Sch = Join-Path $ProjectRoot "pumpengruppe-rs485.kicad_sch"
$Fab = Join-Path $ProjectRoot "fab"
$Gerber = Join-Path $Fab "gerber"
$Drill = Join-Path $Fab "drill"
$Bom = Join-Path $Fab "pumpengruppe-rs485-bom.csv"
$Zip = Join-Path $Fab "pumpengruppe-rs485-revA-preliminary-gerber.zip"

New-Item -ItemType Directory -Force -Path $Gerber, $Drill | Out-Null

& $Cli.Source pcb export gerbers `
    --output $Gerber `
    --layers "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts,User.Drawings" `
    --no-x2 `
    $Board

& $Cli.Source pcb export drill `
    --output $Drill `
    --format excellon `
    --excellon-zeros-format decimal `
    $Board

& $Cli.Source sch export bom `
    --output $Bom `
    $Sch

# The schematic is intentionally block-level in RevA. KiCad's generic BOM
# exporter may omit block symbols, so keep an explicit review BOM here.
@"
"Refs","Value","Footprint","Qty","DNP"
"X1","230V_IN_L_N_PE","FW_Pumpengruppe:TB_3_762","1",""
"X2","PUMPE_L_SW_N_PE","FW_Pumpengruppe:TB_3_762","1",""
"X3","MISCHER_AUF_ZU_N_PE","FW_Pumpengruppe:TB_4_762","1",""
"F1","TBD_T2A_T4A","FW_Pumpengruppe:FUSE_5X20","1",""
"PSU1","IRM-05-5 / AC-DC 230VAC to 5V","FW_Pumpengruppe:ACDC_IRM05","1",""
"K1","RELAY_PUMPE_16A","FW_Pumpengruppe:Relay_SPST_16A","1",""
"K2,K3","RELAY_MISCHER_AUF_ZU","FW_Pumpengruppe:Relay_SPST_8A","2",""
"U1","ESP32-WROOM-32U external antenna","FW_Pumpengruppe:ESP32_WROOM_KEEP_OUT","1",""
"U2,U3","MAX31865 RTD frontend","FW_Pumpengruppe:SOIC16_RTD","2",""
"U4","Isolated RS485 transceiver/module","FW_Pumpengruppe:ISO_RS485_MODULE","1",""
"U5","3V3 regulator","FW_Pumpengruppe:LDO_SOT223","1",""
"U6","CP2102N USB-UART","FW_Pumpengruppe:USB_UART_QFN24","1",""
"J1,J2","RJ45 RS485 daisychain","FW_Pumpengruppe:RJ45_SHIELDED_GENERIC","2",""
"J3,J4","YSTY RS485 screw terminal","FW_Pumpengruppe:TB_3_350","2",""
"X4,X5","RTD screw terminal VL/RL","FW_Pumpengruppe:TB_2_350","2",""
"X6","USB-C service / flash","FW_Pumpengruppe:USB_C_SERVICE","1",""
"R1,R2","5k1 USB-C CC pulldown","FW_Pumpengruppe:R_0603","2",""
"R3","120R RS485 termination","FW_Pumpengruppe:R_0603","1",""
"JP1","RS485 termination enable jumper","FW_Pumpengruppe:JP_2_254","1",""
"@ | Set-Content -NoNewline -Encoding UTF8 $Bom

if (Test-Path $Zip) {
    Remove-Item -LiteralPath $Zip
}
Compress-Archive -Path (Join-Path $Gerber "*"), (Join-Path $Drill "*"), $Bom -DestinationPath $Zip

Write-Host "Fertig: $Zip"
