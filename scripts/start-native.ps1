param([switch]$Development)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $ProjectRoot "apps\api"
$WebDir = Join-Path $ProjectRoot "apps\web"
$RuntimeDir = Join-Path $ProjectRoot "data\runtime"
$ApiDataDir = Join-Path $ApiDir "data"
$RootEnv = Join-Path $ProjectRoot ".env"

$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
$PythonExe = if ($PythonCommand) { $PythonCommand.Source } else { $null }
if (-not $PythonExe) {
  $PythonExe = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA "Programs\Python\Python3*\python.exe") -ErrorAction SilentlyContinue |
    Where-Object { $_.Directory.Name -match '^Python3(1[3-9]|[2-9][0-9])$' } |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName
}
if (-not $PythonExe) {
  throw "Python 3.13+ tidak ditemukan. Install Python lalu aktifkan Add Python to PATH."
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw "Node.js tidak ditemukan di PATH."
}
$env:NODE_OPTIONS = "--use-system-ca --dns-result-order=ipv4first"
if (-not (Test-Path -LiteralPath $RootEnv)) {
  Copy-Item -LiteralPath (Join-Path $ProjectRoot ".env.native.example") -Destination $RootEnv
  throw ".env dibuat dari .env.native.example. Ganti DEVICE_API_KEY, lalu jalankan ulang."
}
New-Item -ItemType Directory -Force -Path $RuntimeDir, $ApiDataDir | Out-Null
Get-Content -LiteralPath $RootEnv | ForEach-Object {
  $Line = $_.Trim()
  if ($Line -and -not $Line.StartsWith("#") -and $Line.Contains("=")) {
    $Name, $Value = $Line.Split("=", 2)
    [Environment]::SetEnvironmentVariable($Name.Trim(), $Value.Trim(), "Process")
  }
}
$ConfiguredKey = [Environment]::GetEnvironmentVariable("DEVICE_API_KEY", "Process")
if (-not $ConfiguredKey -or $ConfiguredKey.StartsWith("ganti-")) {
  throw "Ganti DEVICE_API_KEY di .env dengan kunci acak panjang sebelum menjalankan service."
}

$VenvPython = Join-Path $ApiDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
  Push-Location $ApiDir
  try {
    & $PythonExe -m venv .venv
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -e ".[dev]"
  } finally { Pop-Location }
}
if (-not (Test-Path -LiteralPath (Join-Path $WebDir "node_modules"))) {
  Push-Location $WebDir
  try { cmd /c npm ci } finally { Pop-Location }
}

$ApiArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000")
if ($Development) { $ApiArgs += "--reload" }
$ApiProcess = Start-Process -FilePath $VenvPython -ArgumentList $ApiArgs -WorkingDirectory $ApiDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RuntimeDir "api.log") -RedirectStandardError (Join-Path $RuntimeDir "api-error.log") -PassThru

$NpmArgs = if ($Development) { "/c npm run dev" } else { "/c npm run build && npm run start" }
$WebProcess = Start-Process -FilePath "cmd.exe" -ArgumentList $NpmArgs -WorkingDirectory $WebDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RuntimeDir "web.log") -RedirectStandardError (Join-Path $RuntimeDir "web-error.log") -PassThru
@{ api = $ApiProcess.Id; web = $WebProcess.Id } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RuntimeDir "pids.json")
Write-Host "PLTS Monitor sedang dimulai. Log: $RuntimeDir"
Write-Host "Dashboard: http://127.0.0.1:3000"
Write-Host "API docs: http://127.0.0.1:8000/docs"
