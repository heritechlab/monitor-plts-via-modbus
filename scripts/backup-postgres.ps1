$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackupDir = Join-Path $ProjectRoot "backups"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Target = Join-Path $BackupDir "plts_$Timestamp.sql"
docker compose --env-file (Join-Path $ProjectRoot ".env") -f (Join-Path $ProjectRoot "infra\docker-compose.local.yml") exec -T postgres pg_dump -U plts -d plts -f "/tmp/plts_backup.sql"
docker compose --env-file (Join-Path $ProjectRoot ".env") -f (Join-Path $ProjectRoot "infra\docker-compose.local.yml") cp postgres:/tmp/plts_backup.sql $Target
Write-Host "Backup berhasil: $Target"

