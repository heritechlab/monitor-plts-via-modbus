$ErrorActionPreference = "Stop"
$TaskName = "PLTS Monitor Server"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$StartScript = Join-Path $PSScriptRoot "start-native.ps1"
$RootEnv = Join-Path $ProjectRoot ".env"
$TaskUser = "$env:USERDOMAIN\$env:USERNAME"

if (-not (Test-Path -LiteralPath $RootEnv)) {
  throw ".env root belum ada. Siapkan konfigurasi sebelum memasang autostart."
}

$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartScript`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $TaskUser
$Principal = New-ScheduledTaskPrincipal `
  -UserId $TaskUser `
  -LogonType Interactive `
  -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -MultipleInstances IgnoreNew

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Principal $Principal `
  -Settings $Settings `
  -Force | Out-Null

Write-Host "Scheduled Task '$TaskName' berhasil dipasang."
Write-Host "Uji manual: Start-ScheduledTask -TaskName '$TaskName'"
