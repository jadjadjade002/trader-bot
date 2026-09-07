param([string]$eaName = "QuantumSniper_EA")
$metaeditor = "C:\Program Files\MetaTrader 5\metaeditor64.exe"
$mt5Include = "C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5"
$targetMq5 = $eaName
if (-not (Test-Path $targetMq5)) {
    $targetMq5 = "D:\project\trader-bot\$eaName.mq5"
}
if (-not (Test-Path $targetMq5)) {
    $targetMq5 = "D:\project\trader-bot\versions\$eaName.mq5"
}
if (-not (Test-Path $targetMq5)) {
    $targetMq5 = "D:\project\trader-bot\tests\$eaName.mq5"
}
$logFile = "D:\project\trader-bot\compile.log"

Write-Host "⚡ Compiling $targetMq5..." -ForegroundColor Cyan
$argList = @("/compile:$targetMq5", "/include:$mt5Include", "/log:$logFile")
Start-Process -FilePath $metaeditor -ArgumentList $argList -Wait
if (Test-Path $logFile) {
    Get-Content $logFile -Encoding Unicode | Select-String "Result:"
} else {
    Write-Host "Compile log not found." -ForegroundColor Yellow
}
