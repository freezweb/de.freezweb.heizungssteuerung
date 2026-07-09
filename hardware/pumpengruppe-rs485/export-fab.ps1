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
$BomAisler = Join-Path $Fab "pumpengruppe-rs485-aisler-mpn-bom.csv"
$BomTemp = Join-Path $Fab "pumpengruppe-rs485-bom-tempinput.csv"
$Pos = Join-Path $Fab "pumpengruppe-rs485-pick-place.csv"
$PosTemp = Join-Path $Fab "pumpengruppe-rs485-pick-place-tempinput.csv"
$Zip = Join-Path $Fab "pumpengruppe-rs485-revA-preliminary-gerber.zip"

New-Item -ItemType Directory -Force -Path $Gerber, $Drill | Out-Null
Get-ChildItem -LiteralPath $Gerber, $Drill -File | Remove-Item -Force

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

& $Cli.Source pcb export pos `
    --output $Pos `
    --side both `
    --format csv `
    --units mm `
    $Board

$DnpRefs = @("D50", "D51", "D52")
$PosRows = Import-Csv $Pos | Where-Object { $DnpRefs -notcontains $_.Ref }
$PosRows | Export-Csv -NoTypeInformation -Encoding UTF8 $Pos

$TempDnpRefs = @(
    "X1", "X2", "X3", "F1", "PSU1", "K1", "K2", "K3",
    "Q1", "Q2", "Q3",
    "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12",
    "D1", "D2", "D3", "D10", "D11", "D12",
    "R40", "R41", "D40", "D41", "RV1",
    "D50", "D51", "D52"
)
foreach ($i in 64..83) {
    $TempDnpRefs += "D$i"
    $TempDnpRefs += "C$i"
}
$PosTempRows = Import-Csv $Pos | Where-Object { $TempDnpRefs -notcontains $_.Ref }
$PosTempRows | Export-Csv -NoTypeInformation -Encoding UTF8 $PosTemp

& $Cli.Source sch export bom `
    --output $Bom `
    --fields "Reference,Value,Footprint,QUANTITY,DNP,Manufacturer,MPN,AISLER_MPN,Supplier,AssemblyNote" `
    --labels "Refs,Value,Footprint,Qty,DNP,Manufacturer,MPN,AISLER_MPN,Supplier,AssemblyNote" `
    --group-by "Value,Footprint,Manufacturer,MPN,AISLER_MPN,DNP,AssemblyNote" `
    --exclude-dnp `
    $Sch

& $Cli.Source sch export bom `
    --output $BomAisler `
    --fields "Reference,Value,Footprint,QUANTITY,DNP,Manufacturer,MPN,AISLER_MPN,Supplier,AssemblyNote" `
    --labels "Refs,Value,Footprint,Qty,DNP,Manufacturer,MPN,AISLER_MPN,Supplier,AssemblyNote" `
    --group-by "Value,Footprint,Manufacturer,MPN,AISLER_MPN,DNP,AssemblyNote" `
    --exclude-dnp `
    $Sch

$RawBom = Join-Path $Fab "pumpengruppe-rs485-bom-ungrouped.csv"
& $Cli.Source sch export bom `
    --output $RawBom `
    --fields "Reference,Value,Footprint,QUANTITY,DNP,Manufacturer,MPN,AISLER_MPN,Supplier,AssemblyNote" `
    --labels "Refs,Value,Footprint,Qty,DNP,Manufacturer,MPN,AISLER_MPN,Supplier,AssemblyNote" `
    --exclude-dnp `
    $Sch
$TempBomRows = Import-Csv $RawBom | Where-Object { $TempDnpRefs -notcontains $_.Refs }
$TempBomRows | Export-Csv -NoTypeInformation -Encoding UTF8 $BomTemp
Remove-Item -LiteralPath $RawBom -Force

if (Test-Path $Zip) {
    Remove-Item -LiteralPath $Zip
}
Compress-Archive -Path (Join-Path $Gerber "*"), (Join-Path $Drill "*"), $Bom, $BomAisler, $Pos, $BomTemp, $PosTemp -DestinationPath $Zip

Write-Host "Fertig: $Zip"
