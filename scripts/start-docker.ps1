$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker tidak ditemukan. Install Docker Desktop atau gunakan scripts\start-native.ps1."
}
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".env"))) {
  Copy-Item -LiteralPath (Join-Path $ProjectRoot ".env.example") -Destination (Join-Path $ProjectRoot ".env")
  throw ".env dibuat. Ganti password dan DEVICE_API_KEY, lalu jalankan ulang."
}
docker compose --env-file (Join-Path $ProjectRoot ".env") -f (Join-Path $ProjectRoot "infra\docker-compose.local.yml") up -d --build
docker compose --env-file (Join-Path $ProjectRoot ".env") -f (Join-Path $ProjectRoot "infra\docker-compose.local.yml") ps

