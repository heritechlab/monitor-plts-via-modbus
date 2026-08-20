<#
.SYNOPSIS
    Deploy otomatis dari GitHub ke laptop production.
.DESCRIPTION
    Script ini dijalankan di laptop production. Ia akan:
    - Cek apakah ada commit baru di origin/$Branch
    - Backup database SQLite dan queue gateway
    - Stop service PLTS Monitor
    - Pull update dari GitHub
    - Update dependency Python dan npm
    - Jalankan database migration (Alembic)
    - Start service PLTS Monitor
    - Jalankan smoke test

    Setelah script ini tersedia di repo, alur deployment menjadi:
    1. Dev push ke GitHub (main)
    2. Di laptop production: jalankan deploy-production.ps1

.PARAMETER Branch
    Branch yang di-deploy. Default: main.

.PARAMETER SkipBackup
    Lewati backup database sebelum deploy. Tidak direkomendasikan.

.PARAMETER IncludeGateway
    Juga update dependency dan restart gateway inverter.

.PARAMETER Force
    Deploy meskipun tidak ada commit baru (tidak direkomendasikan).

.PARAMETER KeepBackups
    Jumlah backup terakhir yang dipertahankan per jenis. Default: 5.
    Tanpa rotasi, tiap deploy menambah satu salinan penuh database.
#>
param(
    [string]$Branch = "main",
    [switch]$SkipBackup,
    [switch]$IncludeGateway,
    [switch]$Force,
    [int]$KeepBackups = 5
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $ProjectRoot "apps\api"
$WebDir = Join-Path $ProjectRoot "apps\web"
$GatewayDir = Join-Path $ProjectRoot "agents\inverter-gateway"
$RuntimeDir = Join-Path $ProjectRoot "data\runtime"
$BackupDir = Join-Path $ProjectRoot "backups\deploy"
$RootEnv = Join-Path $ProjectRoot ".env"
$LogFile = Join-Path $RuntimeDir "deploy.log"

function Write-Log($Message) {
    $Line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $Message"
    Write-Host $Line
    if (-not (Test-Path -LiteralPath $RuntimeDir)) {
        New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    }
    Add-Content -LiteralPath $LogFile -Value "$Line`r`n" -Encoding utf8 -NoNewline
}

function Get-EnvValue($Key) {
    if (-not (Test-Path -LiteralPath $RootEnv)) { return $null }
    foreach ($Line in Get-Content -LiteralPath $RootEnv) {
        $Trimmed = $Line.Trim()
        if ($Trimmed -and -not $Trimmed.StartsWith("#") -and $Trimmed.Contains("=")) {
            $Name, $Value = $Trimmed.Split("=", 2)
            if ($Name.Trim() -eq $Key) { return $Value.Trim() }
        }
    }
    return $null
}

function Invoke-Backup() {
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

    $ApiDb = Join-Path $ApiDir "data\plts.sqlite3"
    $GatewayQueue = Join-Path $GatewayDir "data\offline_queue.sqlite3"
    $CsvDir = Join-Path $GatewayDir "data\csv"

    if (Test-Path -LiteralPath $ApiDb) {
        $BackupPath = Join-Path $BackupDir "plts_$Timestamp.sqlite3"
        Copy-Item -LiteralPath $ApiDb -Destination $BackupPath -Force
        Write-Log "Backup database: $BackupPath"
    }

    if (Test-Path -LiteralPath $GatewayQueue) {
        $BackupPath = Join-Path $BackupDir "offline_queue_$Timestamp.sqlite3"
        Copy-Item -LiteralPath $GatewayQueue -Destination $BackupPath -Force
        Write-Log "Backup gateway queue: $BackupPath"
    }

    if (Test-Path -LiteralPath $CsvDir) {
        $BackupPath = Join-Path $BackupDir "csv_$Timestamp"
        Copy-Item -LiteralPath $CsvDir -Destination $BackupPath -Recurse -Force
        Write-Log "Backup CSV: $BackupPath"
    }

    # Backup konfigurasi juga
    if (Test-Path -LiteralPath $RootEnv) {
        Copy-Item -LiteralPath $RootEnv -Destination (Join-Path $BackupDir ".env_$Timestamp") -Force
    }
}
function Remove-OldBackups([int]$Keep) {
    if (-not (Test-Path -LiteralPath $BackupDir)) { return }
    # Tiap jenis backup dirotasi terpisah supaya set terbaru selalu lengkap.
    $Groups = @("plts_*.sqlite3", "offline_queue_*.sqlite3", "csv_*", ".env_*")
    foreach ($Pattern in $Groups) {
        $Items = Get-ChildItem -LiteralPath $BackupDir -Filter $Pattern -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending
        if ($Items.Count -le $Keep) { continue }
        $Stale = $Items | Select-Object -Skip $Keep
        foreach ($Item in $Stale) {
            Remove-Item -LiteralPath $Item.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
        Write-Log "Rotasi backup '$Pattern': $($Stale.Count) salinan lama dihapus, $Keep disimpan."
    }
}


function Test-CommandAvailable($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-AlembicMigration() {
    $DbUrl = Get-EnvValue "DATABASE_URL"
    Push-Location $ApiDir
    try {
        if ($DbUrl -and $DbUrl.StartsWith("sqlite")) {
            $CheckScript = @'
import sqlite3
import sys
url = sys.argv[1]
url = url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
conn = sqlite3.connect(url)
cur = conn.cursor()
cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='alembic_version'")
if cur.fetchone()[0]:
    cur.execute("SELECT count(*) FROM alembic_version")
    print(cur.fetchone()[0])
else:
    print(0)
'@
            $TempCheck = Join-Path $env:TEMP "check_alembic_$([guid]::NewGuid().ToString()).py"
            Set-Content -LiteralPath $TempCheck -Value $CheckScript -Encoding utf8
            try {
                $VersionCount = & $ApiVenv $TempCheck $DbUrl
            } finally {
                Remove-Item -LiteralPath $TempCheck -ErrorAction SilentlyContinue
            }
            if ($VersionCount -eq "0") {
                Write-Log "Database SQLite belum memiliki alembic_version, stamp ke head..."
                & $ApiVenv -m alembic stamp head
                if (-not $?) { throw "Alembic stamp gagal" }
            }
        }
        Write-Log "Jalankan database migration..."
        & $ApiVenv -m alembic upgrade head
        if (-not $?) { throw "Alembic upgrade head gagal" }
    } finally {
        Pop-Location
    }
}

function Wait-ApiReady($Url = "http://127.0.0.1:8000", $TimeoutSeconds = 60) {
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        try {
            $Response = Invoke-RestMethod -Uri "$Url/health" -TimeoutSec 2 -ErrorAction Stop
            if ($Response.status -eq "ok") {
                Write-Log "API siap di $Url"
                return
            }
        } catch {
            # API belum siap, tunggu sebentar.
        }
        Start-Sleep -Seconds 2
    }
    throw "API tidak siap setelah $TimeoutSeconds detik"
}

# --- Pre-flight checks ---
Write-Log "Mulai deploy production | Branch=$Branch | SkipBackup=$SkipBackup | IncludeGateway=$IncludeGateway"

if (-not (Test-Path -LiteralPath $RootEnv)) {
    throw ".env root tidak ditemukan. Siapkan konfigurasi terlebih dahulu."
}

if (-not (Test-CommandAvailable "git")) {
    throw "Git tidak ditemukan di PATH. Install Git untuk Windows."
}

if (-not (Test-CommandAvailable "node")) {
    throw "Node.js tidak ditemukan di PATH."
}

# Pastikan kita berada di branch yang benar
$CurrentBranch = git -C $ProjectRoot rev-parse --abbrev-ref HEAD
if ($CurrentBranch -ne $Branch) {
    throw "Branch lokal saat ini '$CurrentBranch'. Script ini mensyaratkan berada di branch '$Branch'. Jalankan 'git checkout $Branch' terlebih dahulu."
}

# Cek working tree bersih
$Dirty = git -C $ProjectRoot status --porcelain
if ($Dirty) {
    throw "Working tree tidak bersih. Commit atau stash perubahan lokal terlebih dahulu.`n$Dirty"
}

# Cek apakah ada update baru
Write-Log "Fetch origin/$Branch ..."
git -C $ProjectRoot fetch origin $Branch

$LocalCommit = git -C $ProjectRoot rev-parse HEAD
$RemoteCommit = git -C $ProjectRoot rev-parse "origin/$Branch"

if ($LocalCommit -eq $RemoteCommit) {
    if (-not $Force) {
        Write-Log "Sudah versi terbaru ($Branch@$($LocalCommit.Substring(0,7))). Tidak perlu deploy."
        exit 0
    }
    Write-Log "Force deploy aktif meskipun tidak ada perubahan."
} else {
    Write-Log "Ada update baru: $Branch local=$($LocalCommit.Substring(0,7)) -> origin=$($RemoteCommit.Substring(0,7))"
}

# --- Backup ---
if (-not $SkipBackup) {
    Write-Log "Backup data production..."
    Invoke-Backup
    Remove-OldBackups -Keep $KeepBackups
} else {
    Write-Log "Backup dilewati."
}

# --- Stop services ---
Write-Log "Stop service PLTS Monitor..."
& (Join-Path $PSScriptRoot "stop-native.ps1")

if ($IncludeGateway) {
    Write-Log "Stop gateway inverter..."
    Stop-ScheduledTask -TaskName "PLTS Inverter Gateway" -ErrorAction SilentlyContinue
}

# --- Pull latest code ---
Write-Log "Pull update dari origin/$Branch..."
git -C $ProjectRoot pull origin $Branch

# --- Update API dependencies ---
$ApiVenv = Join-Path $ApiDir ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $ApiVenv) {
    Write-Log "Update dependency API..."
    & $ApiVenv -m pip install -e "$ApiDir[dev]"

    Invoke-AlembicMigration
} else {
    Write-Log "Virtual environment API belum ada. start-native.ps1 akan membuatnya saat start."
}

# --- Update Web dependencies ---
Write-Log "Update dependency web..."
Push-Location $WebDir
try {
    cmd /c npm ci
} finally {
    Pop-Location
}

# --- Update Gateway dependencies ---
if ($IncludeGateway) {
    $GatewayVenv = Join-Path $GatewayDir ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $GatewayVenv) {
        Write-Log "Update dependency gateway..."
        Push-Location $GatewayDir
        try {
            & $GatewayVenv -m pip install -r requirements.txt
        } finally {
            Pop-Location
        }
    } else {
        Write-Log "Virtual environment gateway belum ada. install_gateway.bat akan membuatnya nanti."
    }
}

# --- Start services ---
Write-Log "Start service PLTS Monitor..."
& (Join-Path $PSScriptRoot "start-native.ps1")

if ($IncludeGateway) {
    Write-Log "Start gateway inverter..."
    Start-ScheduledTask -TaskName "PLTS Inverter Gateway"
    Start-Sleep -Seconds 3
}

# --- Smoke test ---
$ApiKey = Get-EnvValue "DEVICE_API_KEY"
$DeviceSlug = Get-EnvValue "DEVICE_SLUG"
if (-not $ApiKey) { throw "DEVICE_API_KEY tidak ditemukan di .env" }
if (-not $DeviceSlug) { $DeviceSlug = "prime-rumah-01" }

Write-Log "Menunggu API siap..."
Wait-ApiReady

Write-Log "Jalankan smoke test..."
& (Join-Path $PSScriptRoot "smoke-test.ps1") -ApiKey $ApiKey -DeviceSlug $DeviceSlug

Write-Log "Deploy production selesai."
