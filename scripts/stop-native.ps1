$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $ProjectRoot "data\runtime\pids.json"
if (-not (Test-Path -LiteralPath $PidFile)) {
  Write-Host "Tidak ada PID runtime yang tersimpan."
  exit 0
}
$Processes = Get-Content -Raw -LiteralPath $PidFile | ConvertFrom-Json
foreach ($ProcessId in @($Processes.api, $Processes.web)) {
  if ($ProcessId -and (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
    & taskkill.exe /PID $ProcessId /T /F *> $null
  }
}
Remove-Item -LiteralPath $PidFile
Write-Host "Service native PLTS Monitor dihentikan."
