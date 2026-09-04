param([string]$eaName = "QuantumSniper_v6_Institutional")
$metaeditor = "C:\Program Files\MetaTrader 5\metaeditor64.exe"
$mt5Include = "C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5"
$targetMq5 = "D:\project\trader-bot\versions\$eaName.mq5"
if (-not (Test-Path $targetMq5)) {
    $targetMq5 = "D:\project\trader-bot\$eaName.mq5"
}
$logFile = "D:\project\trader-bot\compile.log"

Write-Host "⚡ Compiling $targetMq5..." -ForegroundColor Cyan
Start-Process -FilePath $metaeditor -ArgumentList "/compile:"$targetMq5" /include:"$mt5Include" /log:"$logFile"" -Wait
Get-Content $logFile -Encoding Unicode | Select-String "Result:"
