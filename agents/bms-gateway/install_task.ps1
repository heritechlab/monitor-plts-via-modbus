$ErrorActionPreference = "Stop"
$TaskName = "PLTS BMS Gateway"
$Runner = Join-Path $PSScriptRoot "run_gateway_task.ps1"
$GatewayPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$GatewayEnv = Join-Path $PSScriptRoot ".env"
$TaskUser = "$env:USERDOMAIN\$env:USERNAME"

if (-not (Test-Path -LiteralPath $GatewayPython)) {
  throw "Virtual environment gateway belum ada. Jalankan install_gateway.bat."
}
if (-not (Test-Path -LiteralPath $GatewayEnv)) {
  throw ".env gateway belum ada. Jalankan install_gateway.bat lalu isi konfigurasi."
}

$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Runner`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $TaskUser
$Principal = New-ScheduledTaskPrincipal `
  -UserId $TaskUser `
  -LogonType Interactive `
  -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -RestartCount 10 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -MultipleInstances IgnoreNew

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Principal $Principal `
  -Settings $Settings `
  -Force | Out-Null

Write-Host "Scheduled Task '$TaskName' berhasil dipasang (hidden, restart otomatis)."
