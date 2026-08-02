@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment belum ada. Jalankan install_gateway.bat terlebih dahulu.
  exit /b 1
)
if not exist ".env" (
  echo File .env belum ada. Salin .env.example menjadi .env lalu isi API key.
  exit /b 1
)
".venv\Scripts\python.exe" gateway.py

