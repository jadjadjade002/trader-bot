$mt5EaDir = "C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors"
$metaeditor = "C:\Program Files\MetaTrader 5\metaeditor64.exe"
$mt5Include = "C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5"

Write-Host "🚀 Deploying hardened code to QuantumSniper_EA and QuantumSniper_v7_Apex..." -ForegroundColor Green
Copy-Item "D:\project\trader-bot\QuantumSniper_EA.mq5" "$mt5EaDir\QuantumSniper_EA.mq5" -Force
Copy-Item "D:\project\trader-bot\QuantumSniper_EA.mq5" "$mt5EaDir\QuantumSniper_v7_Apex.mq5" -Force
Copy-Item "D:\project\trader-bot\QuantumSniper_EA.mq5" "D:\project\trader-bot\versions\QuantumSniper_v7_Apex.mq5" -Force

Write-Host "⚡ Compiling QuantumSniper_v7_Apex on MT5..." -ForegroundColor Cyan
$deployLogApex = "$mt5EaDir\deploy_apex.log"
$argListApex = @("/compile:$mt5EaDir\QuantumSniper_v7_Apex.mq5", "/include:$mt5Include", "/log:$deployLogApex")
Start-Process -FilePath $metaeditor -ArgumentList $argListApex -Wait
if (Test-Path $deployLogApex) {
    Get-Content $deployLogApex -Encoding Unicode | Select-String "Result:"
}

Write-Host "⚡ Compiling QuantumSniper_EA on MT5..." -ForegroundColor Cyan
$deployLogEa = "$mt5EaDir\deploy_ea.log"
$argListEa = @("/compile:$mt5EaDir\QuantumSniper_EA.mq5", "/include:$mt5Include", "/log:$deployLogEa")
Start-Process -FilePath $metaeditor -ArgumentList $argListEa -Wait
if (Test-Path $deployLogEa) {
    Get-Content $deployLogEa -Encoding Unicode | Select-String "Result:"
}

Write-Host "✅ Live Deployment Complete! MT5 will auto-reload active charts." -ForegroundColor Green
