$ErrorActionPreference = "Stop"
$TaskName = "PLTS Monitor Server"

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
  Write-Host "Scheduled Task '$TaskName' dihapus."
} else {
  Write-Host "Scheduled Task '$TaskName' tidak ditemukan."
}
