# PLTS Monitor Rumah

Sistem monitoring lokal untuk inverter PRIME LFT10224-H40 melalui USB-RS485.
Arsitekturnya local-first, tetapi kontrak ingest dan database tetap siap dipindah
ke VPS serta menerima gateway ESP32 di masa depan.

## Yang sudah tersedia

- Modbus RTU read-only: slave 1, FC04, `0x3000–0x301F`, 9600 8N1.
- Gateway Windows dengan reader dan uploader terpisah.
- SQLite queue commit-first, retry eksponensial, deduplikasi, dan dead-letter.
- CSV backup harian seluruh metrics dan raw register.
- FastAPI ingest tunggal/batch, heartbeat, device status, quality flags, dan export.
- Perhitungan energi trapezoidal dengan timestamp aktual dan gap maksimal 60 detik.
- Dashboard Next.js mobile-first: realtime, riwayat, harian, bulanan, device, dan kualitas data.
- Mode native ringan memakai SQLite serta mode Docker/PostgreSQL.
- Cloudflare Tunnel hanya untuk dashboard; FastAPI dan database tetap lokal.

## Prasyarat

Mode native:

- Python 3.13 atau lebih baru. Script juga mendeteksi instalasi Python user yang belum masuk PATH.
- Node.js 20.9 atau lebih baru.
- Microsoft Visual C++ Redistributable 2015-2022 x64, dibutuhkan modul `greenlet`.
- Internet saat instalasi dependency pertama.

Mode Docker:

- Docker Desktop dengan Docker Compose.

Gateway nyata juga membutuhkan adaptor CH340 dan tidak boleh dijalankan
bersamaan dengan QModMaster. `SERIAL_PORT=auto` akan mencari satu adaptor CH340
dan tetap bekerja bila Windows mengganti nomor COM setelah restart.

Install runtime Visual C++ bila `_greenlet` gagal memuat DLL:

```powershell
winget install --id Microsoft.VCRedist.2015+.x64 -e --source winget
```

## Quick start native tanpa Docker

Mode ini adalah cara tercepat untuk menguji pada laptop saat ini.

```powershell
Copy-Item .env.native.example .env
notepad .env
```

Ganti `DEVICE_API_KEY` dengan string acak panjang. Lalu:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-native.ps1 -Development
```

Instalasi pertama membuat virtual environment Python dan memasang dependency
npm. Setelah service siap:

- Dashboard: <http://127.0.0.1:3000>
- API: <http://127.0.0.1:8000>
- OpenAPI: <http://127.0.0.1:8000/docs>

Uji alur health → ingest → latest:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1 `
  -ApiKey "NILAI_DEVICE_API_KEY_ANDA"
```

Kirim data simulasi selama satu menit:

```powershell
.\apps\api\.venv\Scripts\python.exe .\agents\inverter-gateway\simulator.py `
  --api-key "NILAI_DEVICE_API_KEY_ANDA" --count 60 --interval 1
```

Hentikan service:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-native.ps1
```

Database native berada di `apps/api/data/plts.sqlite3`.

Untuk penggunaan 24/7, jalankan production tanpa `-Development`, lalu pasang
Scheduled Task dari PowerShell Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-native.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-native.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\install-native-task.ps1
```

Hapus autostart server dengan `scripts/uninstall-native-task.ps1`.

## Quick start Docker/PostgreSQL

```powershell
Copy-Item .env.example .env
notepad .env
powershell -ExecutionPolicy Bypass -File .\scripts\start-docker.ps1
```

Ganti minimal `POSTGRES_PASSWORD`, `DATABASE_URL`, dan `DEVICE_API_KEY` dengan
nilai yang konsisten. Pada `DATABASE_URL`, password harus sama dengan
`POSTGRES_PASSWORD`.

Untuk melihat log:

```powershell
docker compose --env-file .env -f infra/docker-compose.local.yml logs -f api web
```

Untuk berhenti tanpa menghapus database:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-docker.ps1
```

Jangan gunakan `down -v` kecuali memang ingin menghapus seluruh database.

## Menjalankan gateway inverter

```powershell
Set-Location .\agents\inverter-gateway
Copy-Item .env.example .env
notepad .env
.\install_gateway.bat
.\run_gateway.bat
```

Pastikan:

- `DEVICE_API_KEY` sama dengan root `.env`.
- `API_BASE_URL=http://127.0.0.1:8000`.
- `SERIAL_PORT=auto` direkomendasikan untuk satu adaptor CH340. Nomor COM tetap
  dapat diisi eksplisit bila ada lebih dari satu adaptor serial.
- QModMaster sudah ditutup.

Setelah gateway terbukti stabil, pasang Scheduled Task:

```powershell
.\install_task.bat
```

Task menjalankan gateway secara tersembunyi, tanpa batas waktu tiga hari,
dan mencoba restart otomatis bila gateway berhenti. Log tersedia di
`data/gateway.log` dengan rotasi maksimal lima berkas. Hapus task dengan
`uninstall_task.bat`.

## Menjalankan tests

Backend:

```powershell
Set-Location apps\api
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

Gateway, menggunakan venv gateway:

```powershell
Set-Location agents\inverter-gateway
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest
```

Frontend:

```powershell
Set-Location apps\web
cmd /c npm test
cmd /c npm run lint
cmd /c npm run build
```

## Cloudflare Tunnel

Lakukan ini hanya setelah dashboard lokal stabil.

1. Buat tunnel pada Cloudflare Zero Trust.
2. Tambahkan Published application route dengan hostname
   `plts-home.udigi.id`, kolom Path kosong, Type `HTTP`, dan URL
   `127.0.0.1:3000`.
3. Buat aplikasi Cloudflare Access untuk seluruh hostname tersebut dan hanya
   izinkan email Anda.
4. Install `cloudflared` sebagai Windows service menggunakan perintah token
   yang diberikan dashboard. Jangan simpan token ke GitHub atau screenshot.
5. Pastikan connector berstatus Healthy, lalu uji dari jaringan seluler.
6. Jangan membuat route ke port 8000 atau 5432.

Tidak ada perubahan `.env` yang wajib untuk tunnel karena browser menggunakan
proxy same-origin Next.js. Domain publik tetap tercantum pada `CORS_ORIGINS`
contoh konfigurasi untuk kompatibilitas, sedangkan `INTERNAL_API_BASE_URL` dan
gateway `API_BASE_URL` tetap memakai loopback lokal.

Template lokal tersedia di `cloudflared/config.yml.example`. Bila memakai
tunnel remotely-managed, service Compose opsional dapat diaktifkan dengan:

```powershell
docker compose --env-file .env -f infra/docker-compose.local.yml `
  --profile tunnel up -d cloudflared
```

## Backup

SQLite native:

```powershell
.\apps\api\.venv\Scripts\python.exe .\scripts\backup_sqlite.py
```

PostgreSQL Docker:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup-postgres.ps1
```

Salin folder `backups` dan CSV gateway ke disk atau lokasi lain. Queue, database,
dan CSV yang semuanya berada pada satu laptop bukan perlindungan terhadap
kerusakan disk.

## Import CSV lama

Jalankan dry-run terlebih dahulu:

```powershell
.\apps\api\.venv\Scripts\python.exe .\scripts\import_existing_csv.py `
  --file "prime_inverter_log_v2.csv" `
  --device prime-rumah-01 `
  --api-key "NILAI_DEVICE_API_KEY_ANDA" `
  --dry-run
```

Hapus `--dry-run` setelah mapping kolom terlihat benar. `sample_id` dibuat
deterministik sehingga import ulang tidak menggandakan data.

## Struktur utama

```text
apps/api                 FastAPI, SQLAlchemy, Alembic, analytics
apps/web                 Next.js App Router dashboard
agents/inverter-gateway  Modbus, queue, uploader, simulator
infra                    Docker Compose lokal
cloudflared              Template Tunnel Windows
scripts                  Start/stop, smoke test, import, backup
docs                     Arsitektur, API, register map, troubleshooting
```

## Batas keselamatan

Gateway hanya memiliki implementasi FC04. Tidak ada fungsi tulis Modbus pada
source. `estimated_surplus` adalah selisih PV dan output AC, bukan daya charge
baterai. Penghematan rupiah adalah nilai energi ekuivalen, bukan audit PLN.

Lihat juga [arsitektur](docs/ARCHITECTURE.md), [API](docs/API.md),
[register map](docs/REGISTER_MAP.md), dan [troubleshooting](docs/TROUBLESHOOTING.md).
