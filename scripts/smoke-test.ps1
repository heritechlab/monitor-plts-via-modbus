param([string]$ApiUrl = "http://127.0.0.1:8000", [string]$DeviceSlug = "prime-rumah-01", [string]$ApiKey)
$ErrorActionPreference = "Stop"
if (-not $ApiKey) { throw "Gunakan -ApiKey dengan DEVICE_API_KEY dari .env" }
$Health = Invoke-RestMethod -Uri "$ApiUrl/health"
if ($Health.status -ne "ok") { throw "Health check gagal" }
$Raw = @{}
0..31 | ForEach-Object { $Raw[("0x{0:X4}" -f (0x3000 + $_))] = 0 }
$Raw["0x3001"] = 2200; $Raw["0x3002"] = 268; $Raw["0x3003"] = 10
$Raw["0x3004"] = 22; $Raw["0x3005"] = 220; $Raw["0x3009"] = 37
$Raw["0x3010"] = 100; $Raw["0x3012"] = 800
$Payload = @{
  schema_version = 1; sample_id = [guid]::NewGuid().ToString(); device_slug = $DeviceSlug
  recorded_at = [DateTimeOffset]::Now.ToString("o"); sequence_number = 1
  gateway_version = "smoke-test"; source = "simulator"; register_map_version = "prime-v1"
  metrics = @{ pv_voltage_v = 80; pv_current_a = 10; pv_power_w = 800; battery_voltage_v = 26.8; ac_output_voltage_v = 220; ac_output_current_a = 1; ac_output_power_w = 220; load_percent = 22; inverter_temperature_c = 37 }
  raw_registers = $Raw
}
$Headers = @{ Authorization = "Bearer $ApiKey" }
$Ingest = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/ingest/telemetry" -Headers $Headers -ContentType "application/json" -Body ($Payload | ConvertTo-Json -Depth 6)
$Latest = Invoke-RestMethod -Uri "$ApiUrl/api/v1/devices/$DeviceSlug/latest"
if ($Latest.telemetry.sample_id -ne $Payload.sample_id) { throw "Latest sample tidak sesuai" }
Write-Host "Smoke test LULUS: health -> ingest -> latest"

