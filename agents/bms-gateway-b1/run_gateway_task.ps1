$ErrorActionPreference = "Stop"
$GatewayDir = $PSScriptRoot
$GatewayPython = Join-Path $GatewayDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $GatewayPython)) {
  throw "Virtual environment gateway belum ada. Jalankan install_gateway.bat."
}
if (-not (Test-Path -LiteralPath (Join-Path $GatewayDir ".env"))) {
  throw ".env gateway belum ada. Jalankan install_gateway.bat lalu isi konfigurasi."
}

Set-Location $GatewayDir
& $GatewayPython "gateway.py"
exit $LASTEXITCODE
