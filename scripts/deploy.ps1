$metaeditor = "C:\Program Files\MetaTrader 5\metaeditor64.exe"
$terminalDir = Get-ChildItem "$env:APPDATA\MetaQuotes\Terminal\*\MQL5" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if (-not $terminalDir) {
    $terminalDir = "C:\Program Files\MetaTrader 5\MQL5"
}
$mt5EaDir = "$terminalDir\Experts\Advisors"
$mt5Include = $terminalDir

if (-not (Test-Path $mt5EaDir)) {
    New-Item -ItemType Directory -Force -Path $mt5EaDir | Out-Null
}

$projectRoot = "$PSScriptRoot\.."
Write-Host "Deploying latest EA to $mt5EaDir..." -ForegroundColor Green
Copy-Item "$projectRoot\QuantumTitan_v13_Singularity.mq5" "$mt5EaDir\QuantumTitan_v13_Singularity.mq5" -Force
Copy-Item "$projectRoot\QuantumTitan_v13_Singularity.ex5" "$mt5EaDir\QuantumTitan_v13_Singularity.ex5" -Force

Write-Host "Compiling QuantumTitan_v13_Singularity on MT5..." -ForegroundColor Cyan
$deployLog = "$mt5EaDir\deploy_v13.log"
$argList = @("/compile:$mt5EaDir\QuantumTitan_v13_Singularity.mq5", "/include:$mt5Include", "/log:$deployLog")
Start-Process -FilePath $metaeditor -ArgumentList $argList -Wait
if (Test-Path $deployLog) {
    Get-Content $deployLog -Encoding Unicode | Select-String "Result:"
}

Write-Host "Live Deployment Complete! MT5 will auto-reload active charts." -ForegroundColor Green
