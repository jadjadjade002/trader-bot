$mt5EaDir = "C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors"
$metaeditor = "C:\Program Files\MetaTrader 5\metaeditor64.exe"
$mt5Include = "C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5"

Write-Host "🚀 Deploying v7.1 Institutional Hardened to MT5..." -ForegroundColor Green
Copy-Item "D:\project\trader-bot\QuantumSniper_EA.mq5" "$mt5EaDir\QuantumSniper_EA.mq5" -Force

Write-Host "⚡ Compiling on MT5..." -ForegroundColor Cyan
$deployLog = "$mt5EaDir\deploy.log"
$argList = @("/compile:$mt5EaDir\QuantumSniper_EA.mq5", "/include:$mt5Include", "/log:$deployLog")
Start-Process -FilePath $metaeditor -ArgumentList $argList -Wait
if (Test-Path $deployLog) {
    Get-Content $deployLog -Encoding Unicode | Select-String "Result:"
}
Write-Host "✅ Deployment Complete! MT5 will auto-reload EA." -ForegroundColor Green
