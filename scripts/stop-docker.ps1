$ProjectRoot = Split-Path -Parent $PSScriptRoot
docker compose --env-file (Join-Path $ProjectRoot ".env") -f (Join-Path $ProjectRoot "infra\docker-compose.local.yml") down

