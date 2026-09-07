param([string]$eaName = "QuantumTitan_v13_Singularity", [string]$mt5Include = "")
$metaeditor = "C:\Program Files\MetaTrader 5\metaeditor64.exe"
if (-not $mt5Include) {
    $candidate = Get-ChildItem "$env:APPDATA\MetaQuotes\Terminal\*\MQL5" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    if ($candidate) {
        $mt5Include = $candidate
    } else {
        $mt5Include = "C:\Program Files\MetaTrader 5\MQL5"
    }
}
$targetMq5 = $eaName
if (-not (Test-Path $targetMq5)) {
    $targetMq5 = "$PSScriptRoot\..\$eaName.mq5"
}
if (-not (Test-Path $targetMq5)) {
    $targetMq5 = "$PSScriptRoot\..\versions\$eaName.mq5"
}
if (-not (Test-Path $targetMq5)) {
    $targetMq5 = "$PSScriptRoot\..\tests\$eaName.mq5"
}
$logFile = "$PSScriptRoot\..\compile.log"

Write-Host "⚡ Compiling $targetMq5..." -ForegroundColor Cyan
$argList = @("/compile:$targetMq5", "/include:$mt5Include", "/log:$logFile")
Start-Process -FilePath $metaeditor -ArgumentList $argList -Wait
if (Test-Path $logFile) {
    Get-Content $logFile -Encoding Unicode | Select-String "Result:"
} else {
    Write-Host "Compile log not found." -ForegroundColor Yellow
}
