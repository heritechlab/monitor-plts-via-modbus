# SPESIFIKASI IMPLEMENTASI
# SISTEM MONITORING PLTS PRIME — DEV LAN → PRODUCTION INTERNET

> **Koreksi validasi lapangan (2026-08-03):** register `0x3005` mengikuti
> persentase beban/kapasitas nominal dan mendekati VA, bukan watt aktif smart
> plug. Referensi lama yang menyebut `ac_output_power_w`, output kWh, atau
> estimated surplus dipertahankan sebagai riwayat rancangan dan telah digantikan
> oleh semantik `prime-v2`: beban AC estimasi dalam VA/kVAh. Surplus W−VA tidak
> dihitung; watt/kWh aktif memerlukan meter eksternal.

Dokumen ini adalah instruksi implementasi lengkap untuk Codex. Bangun proyek sampai dapat dijalankan, bukan hanya membuat scaffolding.

======================================================================
1. TUJUAN PROYEK
======================================================================

Bangun sistem monitoring PLTS berbasis web yang:

1. Membaca data inverter PRIME dari laptop gateway melalui USB-RS485.
2. Mengirim telemetry dari laptop ke API melalui HTTP/HTTPS.
3. Menyimpan data time-series ke PostgreSQL.
4. Menampilkan dashboard realtime, harian, mingguan, dan bulanan.
5. Menghitung produksi PV dan energi output AC secara akurat berdasarkan timestamp.
6. Menyimpan raw register agar pemetaan register dapat dilanjutkan tanpa mengulang pengukuran.
7. Tetap menyimpan data saat koneksi API/internet putus, lalu mengirim ulang saat koneksi kembali.
8. Dapat dipakai pada dua mode:
   - Development: laptop gateway dan server berada dalam satu jaringan LAN.
   - Production: laptop/ESP32 gateway dan VPS berada di jaringan berbeda melalui internet.
9. Mudah mengganti laptop gateway dengan ESP32 pada masa depan tanpa mengubah API, database, dan dashboard.
10. Seluruh komunikasi Modbus harus READ-ONLY. Jangan pernah mengirim function code tulis.

Timezone sistem: Asia/Jakarta.

======================================================================
2. KONDISI PERANGKAT SAAT INI
======================================================================

Inverter:
- PRIME low-frequency hybrid
- Model: LFT10224-H40
- Daya inverter: 1000 W
- Baterai: 24 V LiFePO4 8S 100 Ah
- Panel: 2 x 585 Wp seri, total 1170 Wp

Gateway saat ini:
- Laptop Windows 10 lama
- Python 3.13
- PySerial sudah terpasang
- USB-RS485 CH340 pada COM3
- RS485:
  - RJ45 pin 1 = RS485-B
  - RJ45 pin 2 = RS485-A
- Serial:
  - COM3
  - 9600 baud
  - 8 data bit
  - parity none
  - 1 stop bit
  - slave ID 1

Protokol inverter yang sudah terbukti:
- Modbus RTU
- Function Code 04: Read Input Registers
- Raw start address: 0x3000
- Quantity: 32 register
- Rentang: 0x3000–0x301F
- Request contoh:
  01 04 30 00 00 20 [CRC]

Register yang sudah terkonfirmasi:

| Raw register | Arti | Konversi |
|---|---|---|
| 0x3001 | Tegangan output AC | raw / 10 V |
| 0x3002 | Tegangan baterai dari inverter | raw / 10 V |
| 0x3003 | Arus output AC | raw / 10 A |
| 0x3004 | Persentase beban | raw % |
| 0x3005 | Estimasi beban semu inverter | raw VA (estimasi) |
| 0x3009 | Suhu inverter | raw °C |
| 0x3010 | Arus PV | raw / 10 A |
| 0x3012 | Tegangan PV | raw / 10 V |

Daya PV dihitung:
pv_power_w = pv_voltage_v * pv_current_a

Register lainnya belum diketahui. Simpan semuanya sebagai raw_registers JSON.

PENTING:
- Tidak boleh menggunakan FC05, FC06, FC15, FC16, atau fungsi tulis lainnya.
- Gateway hanya boleh memakai FC04.
- QModMaster dan gateway Python tidak boleh membuka COM3 bersamaan.

======================================================================
3. ARSITEKTUR SISTEM
======================================================================

3.1 DEVELOPMENT — SATU JARINGAN LAN

Inverter PRIME
    ↓ RS485
USB-RS485
    ↓ USB
Laptop gateway Windows
    ↓ HTTP melalui LAN
Server development / PC development
    ├── FastAPI
    ├── PostgreSQL
    └── Next.js dashboard

Contoh:
- Server dev LAN: 192.168.1.50
- API dev: http://192.168.1.50:8000
- Web dev: http://192.168.1.50:3000
- Logger laptop mengirim ke:
  http://192.168.1.50:8000/api/v1/ingest/telemetry

Jangan hard-code IP. Semua alamat harus berasal dari .env.

3.2 PRODUCTION — BERBEDA JARINGAN

Inverter PRIME
    ↓ RS485
Laptop gateway sementara / ESP32 nanti
    ↓ HTTPS keluar melalui internet
VPS
    ├── Nginx
    ├── FastAPI
    ├── PostgreSQL
    └── Next.js dashboard

Domain yang direkomendasikan:
- Dashboard: https://monitor-plts.example.com
- API ingest: https://ingest-plts.example.com

Logger memulai koneksi keluar ke VPS. Tidak memerlukan:
- IP publik rumah
- port forwarding
- Cloudflare Tunnel di rumah
- server lokal yang menerima koneksi internet

PostgreSQL tidak boleh diekspos ke internet.

======================================================================
4. STACK TEKNOLOGI
======================================================================

Gunakan monorepo:

Backend:
- Python
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic
- PostgreSQL driver async
- Uvicorn
- Pytest

Frontend:
- Next.js App Router
- TypeScript
- Tailwind CSS
- shadcn/ui atau komponen UI ringan setara
- Recharts untuk grafik
- TanStack Query atau polling fetch yang bersih
- Responsive mobile-first
- Dark theme sebagai default

Database:
- PostgreSQL
- Jangan gunakan TimescaleDB pada versi awal
- Jangan gunakan Redis pada versi awal
- Gunakan index B-tree berdasarkan device_id + recorded_at
- Tambahkan BRIN recorded_at hanya bila data sudah besar

Gateway:
- Python
- PySerial
- Requests atau HTTPX
- SQLite lokal untuk antrean offline
- python-dotenv
- CSV backup harian

Deployment:
- Docker Compose untuk API, Web, dan PostgreSQL
- Nginx pada VPS sebagai reverse proxy
- Cloudflare DNS/proxy opsional
- Cloudflare Access opsional hanya untuk dashboard, bukan endpoint ingest

======================================================================
5. STRUKTUR REPOSITORY
======================================================================

Buat struktur:

plts-monitoring/
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── core/
│   │   │   │   ├── config.py
│   │   │   │   ├── security.py
│   │   │   │   └── logging.py
│   │   │   ├── db/
│   │   │   │   ├── session.py
│   │   │   │   ├── base.py
│   │   │   │   └── models/
│   │   │   ├── schemas/
│   │   │   ├── api/
│   │   │   │   └── v1/
│   │   │   ├── services/
│   │   │   │   ├── ingest.py
│   │   │   │   ├── analytics.py
│   │   │   │   └── device_status.py
│   │   │   └── utils/
│   │   ├── alembic/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── .env.example
│   │
│   └── web/
│       ├── app/
│       │   ├── page.tsx
│       │   ├── dashboard/
│       │   ├── history/
│       │   ├── daily/
│       │   ├── monthly/
│       │   ├── devices/
│       │   └── data-quality/
│       ├── components/
│       │   ├── dashboard/
│       │   ├── charts/
│       │   ├── layout/
│       │   └── ui/
│       ├── lib/
│       │   ├── api.ts
│       │   ├── format.ts
│       │   └── timezone.ts
│       ├── public/
│       ├── Dockerfile
│       ├── package.json
│       └── .env.example
│
├── agents/
│   └── inverter-gateway/
│       ├── gateway.py
│       ├── modbus_reader.py
│       ├── api_client.py
│       ├── offline_queue.py
│       ├── csv_backup.py
│       ├── config.py
│       ├── requirements.txt
│       ├── run_gateway.bat
│       ├── install_gateway.bat
│       ├── .env.example
│       └── tests/
│
├── scripts/
│   ├── create_device.py
│   ├── import_existing_csv.py
│   ├── backfill_summaries.py
│   └── rotate_device_key.py
│
├── infra/
│   ├── docker-compose.dev.yml
│   ├── docker-compose.prod.yml
│   ├── nginx/
│   │   ├── monitor-plts.conf
│   │   └── ingest-plts.conf
│   └── postgres/
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── REGISTER_MAP.md
│   ├── API.md
│   ├── DEVELOPMENT.md
│   ├── PRODUCTION.md
│   └── TROUBLESHOOTING.md
│
├── .env.example
├── Makefile
├── README.md
└── LICENSE

======================================================================
6. MODEL DATABASE
======================================================================

Gunakan UUID untuk device dan sample_id. Gunakan TIMESTAMPTZ.

6.1 TABLE devices

Kolom:
- id UUID primary key
- slug VARCHAR unique not null
- name VARCHAR not null
- location VARCHAR nullable
- timezone VARCHAR not null default 'Asia/Jakarta'
- api_key_hash VARCHAR not null
- inverter_model VARCHAR nullable
- inverter_rated_w INTEGER default 1000
- pv_rated_wp INTEGER default 1170
- battery_nominal_v NUMERIC nullable
- battery_capacity_ah NUMERIC nullable
- is_active BOOLEAN default true
- last_seen_at TIMESTAMPTZ nullable
- created_at TIMESTAMPTZ default now()
- updated_at TIMESTAMPTZ default now()

6.2 TABLE inverter_telemetry

Kolom:
- id BIGSERIAL primary key
- sample_id UUID unique not null
- device_id UUID foreign key devices.id not null
- recorded_at TIMESTAMPTZ not null
- received_at TIMESTAMPTZ not null default now()

Data ter-normalisasi:
- pv_voltage_v NUMERIC(7,2)
- pv_current_a NUMERIC(7,2)
- pv_power_w NUMERIC(9,2)
- battery_voltage_v NUMERIC(7,2)
- ac_output_voltage_v NUMERIC(7,2)
- ac_output_current_a NUMERIC(7,2)
- ac_output_power_w NUMERIC(9,2)
- load_percent NUMERIC(6,2)
- inverter_temperature_c NUMERIC(6,2)

Metadata:
- raw_registers JSONB not null
- quality_flags TEXT[] default empty array
- gateway_version VARCHAR nullable
- source VARCHAR default 'usb-rs485-laptop'
- sequence_number BIGINT nullable

Index:
- unique(sample_id)
- index(device_id, recorded_at DESC)
- index(recorded_at DESC)
- index(device_id, received_at DESC)

6.3 TABLE hourly_summaries

Primary key gabungan:
- device_id
- bucket_start TIMESTAMPTZ

Kolom:
- pv_energy_wh
- ac_output_energy_wh
- estimated_surplus_wh
- avg_pv_power_w
- max_pv_power_w
- avg_ac_output_power_w
- max_ac_output_power_w
- avg_battery_voltage_v
- min_battery_voltage_v
- max_battery_voltage_v
- avg_temperature_c
- max_temperature_c
- sample_count
- valid_interval_seconds
- coverage_percent
- updated_at

6.4 TABLE daily_summaries

Primary key:
- device_id
- local_date DATE

Kolom:
- pv_energy_wh
- ac_output_energy_wh
- estimated_surplus_wh
- peak_pv_raw_w
- peak_pv_1m_avg_w
- peak_output_raw_w
- peak_output_1m_avg_w
- max_temperature_c
- min_battery_voltage_v
- max_battery_voltage_v
- pv_above_500_minutes
- pv_above_800_minutes
- pv_above_1000_minutes
- output_above_800_minutes
- online_minutes
- sample_count
- coverage_percent
- first_sample_at
- last_sample_at
- updated_at

6.5 TABLE ingest_events atau gateway_status

Kolom:
- id BIGSERIAL
- device_id
- event_type
- created_at
- detail JSONB

Gunakan untuk:
- gateway_start
- gateway_stop
- queue_flush
- serial_error
- api_error
- reconnect

6.6 RENCANA BMS MASA DEPAN

Siapkan migration atau table terpisah bms_telemetry, tetapi jangan wajib diimplementasikan pada MVP.

Field yang direncanakan:
- battery_current_a
- battery_power_w
- soc_percent
- remaining_ah
- cell_min_v
- cell_max_v
- cell_delta_v
- mos_temperature_c
- battery_temperature_1_c
- battery_temperature_2_c
- charge_enabled
- discharge_enabled
- balance_active
- raw_bms JSONB

======================================================================
7. API CONTRACT
======================================================================

Prefix:
 /api/v1

7.1 AUTHENTICATION DEVICE

Header:
Authorization: Bearer <DEVICE_API_KEY>

API key:
- Simpan hash di database, jangan plaintext.
- Gunakan constant-time comparison.
- Endpoint ingest tidak menggunakan cookie/session.
- Wajib HTTPS pada production.
- Dev boleh HTTP di LAN.

7.2 POST /api/v1/ingest/telemetry

Payload:

{
  "schema_version": 1,
  "sample_id": "uuid",
  "device_slug": "prime-rumah-01",
  "recorded_at": "2026-08-02T11:27:49+07:00",
  "sequence_number": 12345,
  "gateway_version": "0.1.0",
  "source": "usb-rs485-laptop",
  "metrics": {
    "pv_voltage_v": 79.9,
    "pv_current_a": 12.2,
    "pv_power_w": 974.8,
    "battery_voltage_v": 27.2,
    "ac_output_voltage_v": 217.5,
    "ac_output_current_a": 1.1,
    "ac_output_power_w": 240,
    "load_percent": 24,
    "inverter_temperature_c": 37
  },
  "raw_registers": {
    "0x3000": 80,
    "0x3001": 2175,
    "0x3002": 272,
    "0x3003": 11,
    "0x3004": 24,
    "0x3005": 240,
    "0x3006": 0,
    "0x3007": 0,
    "0x3008": 0,
    "0x3009": 37,
    "0x300A": 0,
    "0x300B": 2499,
    "0x300C": 0,
    "0x300D": 0,
    "0x300E": 0,
    "0x300F": 0,
    "0x3010": 122,
    "0x3011": 0,
    "0x3012": 799,
    "0x3013": 0,
    "0x3014": 0,
    "0x3015": 0,
    "0x3016": 0,
    "0x3017": 0,
    "0x3018": 0,
    "0x3019": 0,
    "0x301A": 0,
    "0x301B": 0,
    "0x301C": 0,
    "0x301D": 0,
    "0x301E": 0,
    "0x301F": 0
  }
}

Respons sukses:
- HTTP 201 untuk data baru
- HTTP 200 bila sample_id sudah pernah diterima
- Respons harus idempotent

{
  "status": "accepted",
  "sample_id": "...",
  "duplicate": false,
  "received_at": "..."
}

7.3 POST /api/v1/ingest/telemetry/batch

Menerima maksimal 100–500 sampel untuk flush antrean offline.

Payload:
{
  "samples": [ ... ]
}

Respons:
{
  "accepted": 98,
  "duplicates": 2,
  "rejected": 0,
  "errors": []
}

Satu sampel gagal tidak boleh menggagalkan seluruh batch.

7.4 GET /api/v1/devices/{slug}/latest

Mengembalikan data terbaru dan status online/offline.

Online:
- last_seen <= 30 detik

Degraded:
- 30–120 detik

Offline:
- > 120 detik

7.5 GET /api/v1/devices/{slug}/telemetry

Query:
- from
- to
- resolution=raw|1m|5m|15m|1h
- fields optional

Batasi jumlah data.
Jangan mengirim ratusan ribu titik ke browser.

Untuk resolution:
- raw: data asli, hanya rentang pendek
- 1m: agregasi per menit
- 5m
- 15m
- 1h

7.6 GET /api/v1/devices/{slug}/analytics/daily?date=YYYY-MM-DD

Kembalikan:
- total PV kWh
- total output AC kWh
- estimated surplus kWh
- peak PV raw
- peak PV 1-minute average
- peak output
- suhu max
- tegangan baterai min/max
- durasi PV di atas threshold
- coverage
- gap data

7.7 GET /api/v1/devices/{slug}/analytics/monthly?month=YYYY-MM

Kembalikan:
- total produksi PV
- total output AC
- rata-rata harian
- hari terbaik
- hari terendah
- peak bulan
- data per tanggal untuk grafik batang
- estimasi penghematan berdasarkan tarif configurable
- coverage per hari

7.8 GET /api/v1/devices/{slug}/export.csv

Query:
- from
- to
- resolution

7.9 GET /health

Kembalikan status API dan database.

======================================================================
8. VALIDASI DAN QUALITY FLAGS
======================================================================

Jangan membuang raw data. Simpan data, tetapi beri quality_flags.

Batas awal yang masuk akal untuk sistem ini:

- pv_voltage_v: 0–120
- pv_current_a: 0–20
- pv_power_w: 0–1500
- battery_voltage_v: 20–30
- ac_output_voltage_v: 180–260
- ac_output_current_a: 0–10
- ac_output_power_w: 0–1200
- load_percent: 0–150
- inverter_temperature_c: -20–100

Flag:
- out_of_range
- impossible_jump
- timestamp_in_future
- timestamp_too_old
- duplicate
- serial_crc_error
- partial_sample
- stale_gateway_clock

Anomali yang sebelumnya pernah terlihat:
- battery voltage 30.8 V
- battery voltage 39.4 V
- beberapa lonjakan satu sampel

Jangan gunakan sample invalid dalam perhitungan energi, tetapi tetap simpan.

======================================================================
9. PERHITUNGAN ENERGI
======================================================================

Gunakan integrasi trapezoidal berdasarkan timestamp aktual.

Untuk dua sampel berurutan:
energy_wh =
((power_1_w + power_2_w) / 2) * delta_seconds / 3600

Aturan:
- Urutkan berdasarkan recorded_at.
- Abaikan interval <= 0.
- Abaikan integrasi bila gap > 60 detik.
- Abaikan salah satu sampel bila power invalid.
- Simpan coverage_percent agar data yang hilang terlihat.
- Peak utama dashboard bulanan harus memakai rata-rata 1 menit, bukan hanya lonjakan satu sampel.
- Tetap simpan peak raw sebagai informasi tambahan.

estimated_surplus_w:
max(pv_power_w - ac_output_power_w, 0)

Catatan UI:
- Label sebagai "Estimasi surplus PV", bukan "daya charge baterai".
- Jangan menyebutnya energi baterai karena ada konsumsi dan rugi inverter.

Tarif PLN:
- configurable di tabel settings atau env
- default awal 1550 IDR/kWh
- penghematan estimasi:
  ac_output_energy_kwh * tariff
- Jelaskan bahwa ini estimasi penggantian konsumsi PLN, bukan audit resmi.

======================================================================
10. GATEWAY LAPTOP WINDOWS
======================================================================

Buat gateway baru dari logger yang sudah berhasil.

10.1 POLLING MODBUS

- Buka COM3.
- 9600 8N1.
- Slave 1.
- FC04.
- Start 0x3000.
- Count 32.
- Poll default setiap 5 detik untuk production.
- Dev boleh 2 detik.
- Validate CRC.
- Decode register yang terkonfirmasi.
- Simpan semua raw register.

10.2 KONFIGURASI .ENV

Contoh:

DEVICE_SLUG=prime-rumah-01
DEVICE_API_KEY=change-me
API_BASE_URL=http://192.168.1.50:8000
SERIAL_PORT=COM3
SERIAL_BAUD=9600
SLAVE_ID=1
POLL_INTERVAL_SECONDS=5
HTTP_TIMEOUT_SECONDS=10
QUEUE_DB_PATH=./data/offline_queue.sqlite3
CSV_BACKUP_DIR=./data/csv
GATEWAY_VERSION=0.1.0
TIMEZONE=Asia/Jakarta
VERIFY_TLS=true

Production:
API_BASE_URL=https://ingest-plts.example.com

10.3 OFFLINE QUEUE

Gunakan SQLite lokal.

Table queue:
- id integer primary key
- sample_id uuid unique
- payload_json text
- created_at
- attempt_count
- last_attempt_at
- last_error

Alur:
1. Baca Modbus.
2. Buat payload.
3. Masukkan ke queue SQLite dahulu.
4. Coba kirim batch data tertua.
5. Jika sukses, hapus dari queue.
6. Jika gagal, simpan error dan lanjut polling.
7. Setelah koneksi pulih, flush batch maksimal 100.
8. Gunakan sample_id untuk deduplication.

Jangan kehilangan data jika:
- internet mati
- API down
- laptop restart
- gateway ditutup paksa

10.4 CSV BACKUP

Buat file per tanggal:
data/csv/prime-rumah-01_YYYY-MM-DD.csv

CSV menyimpan:
- recorded_at
- semua field decoded
- semua raw register
- send_status
- sample_id

Rotasi otomatis per hari.

10.5 CONSOLE

Tampilkan format ringkas:

2026-08-02 11:27:49 |
PV 79.9 V 12.2 A 974.8 W |
BAT 27.2 V |
OUT 217.5 V 1.1 A 240 W 24% |
TEMP 37 C |
QUEUE 0 |
API OK

Gunakan logging yang jelas:
- INFO
- WARNING
- ERROR

10.6 WINDOWS STARTUP

Buat:
- install_gateway.bat
- run_gateway.bat
- opsi memasang Scheduled Task Windows agar gateway berjalan saat laptop startup/login
- dokumentasikan cara uninstall task

Jangan mematikan layar laptop melalui script.
Laptop boleh mematikan display, tetapi sleep/hibernate harus dinonaktifkan secara manual dan didokumentasikan.

======================================================================
11. FRONTEND NEXT.JS
======================================================================

11.1 DASHBOARD REALTIME

Halaman utama mobile-first.

Cards:
- PV Power
- PV Voltage
- PV Current
- Produksi hari ini
- Battery Voltage
- AC Output Power
- AC Output Voltage
- Load %
- Inverter Temperature
- Last update
- Device status

Energy flow:
- PV → inverter
- inverter → load
- estimated PV surplus
- jangan tampilkan charge baterai aktual sebelum data BMS tersedia

Update:
- polling 5 detik
- jangan langsung memakai WebSocket pada MVP
- tampilkan stale state bila data lama

11.2 CHART REALTIME/HARIAN

Grafik:
- PV power vs output power
- PV voltage dan current
- battery voltage
- load %
- temperature

Filter:
- 1 jam
- 6 jam
- hari ini
- 7 hari
- 30 hari
- custom range

Downsample melalui API.

11.3 DAILY PAGE

Tampilkan:
- total PV kWh
- total AC output kWh
- estimated surplus
- peak PV 1-minute average
- peak output
- suhu max
- baterai min/max
- jam produksi terbaik
- durasi PV >500, >800, >1000 W
- timeline gap/offline
- tabel data per jam

11.4 MONTHLY PAGE

Tampilkan:
- total PV bulan
- total output AC bulan
- rata-rata per hari
- hari terbaik/terendah
- estimasi penghematan
- production bar chart per date
- consumption/output chart
- heatmap jam vs tanggal
- coverage per day
- perbandingan bulan sebelumnya

11.5 DATA QUALITY PAGE

Tampilkan:
- jumlah sample
- duplicate
- invalid
- gap
- offline duration
- anomaly list
- raw register viewer
- download CSV

11.6 DEVICE PAGE

Tampilkan:
- model inverter
- rated power
- PV rated Wp
- battery capacity
- gateway version
- last seen
- API ingestion status
- queue backlog terakhir jika dikirim sebagai metadata
- register map dokumentasi

11.7 UI

- Bahasa Indonesia.
- Dark mode default.
- Angka memakai locale id-ID.
- kW/kWh otomatis.
- Responsive HP.
- Loading skeleton.
- Error boundary.
- Empty state.
- Tooltip yang menjelaskan bahwa surplus adalah estimasi.
- Jangan membuat dashboard penuh animasi berat.

======================================================================
12. IMPORT LOG CSV YANG SUDAH ADA
======================================================================

Buat scripts/import_existing_csv.py.

Harus dapat mengimpor file:
prime_inverter_log_v2.csv

Fungsi:
- map kolom lama ke schema baru
- buat sample_id deterministik agar import dapat diulang tanpa duplikasi
- parse timezone Asia/Jakarta
- simpan raw register
- beri source='csv-import'
- validasi quality flags
- opsi dry-run
- progress output
- summary accepted/duplicate/invalid

Contoh:
python scripts/import_existing_csv.py \
  --file "prime_inverter_log_v2.csv" \
  --device prime-rumah-01 \
  --dry-run

Lalu:
python scripts/import_existing_csv.py \
  --file "prime_inverter_log_v2.csv" \
  --device prime-rumah-01

======================================================================
13. DEVELOPMENT SETUP
======================================================================

Buat docker-compose.dev.yml:

Services:
- postgres
- api
- web

Postgres:
- volume persistent
- port boleh dibuka hanya ke localhost/dev host bila diperlukan
- healthcheck

API:
- port 8000
- bind 0.0.0.0 agar laptop gateway satu LAN dapat mengakses
- reload dev
- depends_on postgres health

Web:
- port 3000
- API URL dari env

Contoh .env dev:

POSTGRES_DB=plts
POSTGRES_USER=plts
POSTGRES_PASSWORD=dev-password
DATABASE_URL=postgresql+asyncpg://plts:dev-password@postgres:5432/plts
PUBLIC_API_BASE_URL=http://192.168.1.50:8000
CORS_ORIGINS=http://localhost:3000,http://192.168.1.50:3000
APP_TIMEZONE=Asia/Jakarta
DEVICE_BOOTSTRAP_SLUG=prime-rumah-01
DEVICE_BOOTSTRAP_API_KEY=dev-device-key

Langkah dev yang harus tersedia di README:

1. Copy env.
2. docker compose -f infra/docker-compose.dev.yml up -d --build
3. Jalankan migration.
4. Jalankan create_device.py.
5. Tes API dengan curl.
6. Ubah .env gateway laptop ke API LAN.
7. Jalankan gateway.
8. Buka dashboard melalui browser HP di LAN.

Pastikan Windows Firewall/server firewall mengizinkan port 8000 dan 3000 hanya pada jaringan private untuk dev.

======================================================================
14. PRODUCTION SETUP
======================================================================

Buat docker-compose.prod.yml:

- postgres hanya network internal
- api expose hanya 127.0.0.1:8000
- web expose hanya 127.0.0.1:3000
- restart unless-stopped
- healthchecks
- named volumes
- log rotation

Nginx:

monitor-plts.example.com:
- reverse proxy ke 127.0.0.1:3000
- secure headers
- gzip/brotli bila tersedia
- Cloudflare Access opsional

ingest-plts.example.com:
- reverse proxy ke 127.0.0.1:8000
- hanya route /api/v1/ingest/* dan /health yang publik
- rate limit yang masuk akal, misalnya 30–60 request/menit per IP dengan burst
- body size kecil
- timeout singkat
- jangan pasang Cloudflare Access login pada endpoint device ingest
- tetap gunakan Bearer API key

Backup:
- PostgreSQL backup harian
- retensi minimal 7 harian + 4 mingguan
- dokumentasikan restore test

Secret:
- gunakan env production terpisah
- jangan commit
- API key dapat dirotasi
- password database kuat

Production logger:
API_BASE_URL=https://ingest-plts.example.com

Tidak ada perubahan payload antara dev dan production.

======================================================================
15. AGGREGATION DAN SCHEDULER
======================================================================

MVP:
- Query agregasi on-demand untuk rentang pendek.
- Buat job backfill hourly/daily.

Gunakan salah satu:
- cron container sederhana
- APScheduler process terpisah
- CLI yang dijalankan cron

Jangan memakai Celery/Redis pada MVP.

Job:
- setiap 5 menit: update current hour
- setiap jam: finalize jam sebelumnya
- setiap 15 menit: refresh daily summary hari ini
- setelah tengah malam: finalize hari sebelumnya
- command backfill untuk tanggal/rentang tertentu

Semua job harus idempotent memakai upsert.

======================================================================
16. KEAMANAN
======================================================================

- Device ingest menggunakan Bearer API key.
- Simpan hash API key.
- Dashboard production dilindungi:
  - Cloudflare Access, atau
  - auth aplikasi pada fase berikutnya.
- Jangan expose PostgreSQL.
- CORS ketat.
- Validate payload.
- Batasi batch size.
- Batasi timestamp:
  - future tolerance 5 menit
  - data lama tetap boleh untuk offline queue, tetapi tandai.
- Audit event untuk key invalid/rate limit.
- Redact API key dari log.
- HTTPS wajib production.
- Endpoint dashboard read-only.
- Jangan membuat endpoint Modbus write/control.

======================================================================
17. TESTING
======================================================================

Backend unit tests:
- payload validation
- device authentication
- sample deduplication
- batch partial success
- quality flags
- energy trapezoidal integration
- ignore gap >60s
- timezone daily boundary Asia/Jakarta
- hourly/daily upsert

Gateway tests:
- CRC16 Modbus
- decode 32 register
- timeout handling
- Modbus exception handling
- offline queue persistence
- reconnect flush
- duplicate resend safe
- CSV rotation

Frontend tests:
- dashboard rendering
- offline/stale badge
- chart empty state
- monthly summary
- locale formatting

Integration test:
- simulator sends telemetry
- API stores
- dashboard reads latest
- stop simulator -> offline status
- restart -> online
- queue backlog -> batch upload without duplicate

Buat sample Modbus fixture dari respons nyata.

======================================================================
18. ACCEPTANCE CRITERIA
======================================================================

Proyek dianggap selesai bila:

1. docker compose dev dapat dijalankan dari README.
2. PostgreSQL migration berjalan.
3. Device dapat dibuat dan API key dihasilkan satu kali.
4. Curl telemetry masuk ke database.
5. Laptop gateway di jaringan LAN dapat mengirim data.
6. Dashboard menampilkan data terbaru maksimal 10 detik.
7. Status offline muncul setelah batas waktu.
8. Internet/API diputus, queue lokal bertambah.
9. API dipulihkan, queue terkirim tanpa duplikasi.
10. CSV backup harian terbentuk.
11. Produksi harian dihitung dengan integrasi timestamp.
12. Monthly page menampilkan data per hari.
13. Existing CSV dapat diimpor.
14. Raw register dapat dilihat.
15. Tidak ada function code Modbus tulis.
16. Production compose, Nginx config, dan deployment docs tersedia.
17. Semua test utama lulus.
18. Tidak ada secret di repository.

======================================================================
19. URUTAN IMPLEMENTASI UNTUK CODEX
======================================================================

Kerjakan urut dan jangan lompat:

PHASE 1 — FOUNDATION
- Buat monorepo.
- Docker Compose dev.
- PostgreSQL schema.
- Alembic migration.
- Device bootstrap command.
- Health endpoint.

PHASE 2 — INGEST API
- Device auth.
- Single ingest.
- Batch ingest.
- Dedup.
- Quality flags.
- Tests.

PHASE 3 — GATEWAY
- Port logic dari logger lama.
- Read-only Modbus.
- Decoder.
- SQLite queue.
- HTTP client.
- CSV backup.
- BAT launcher.
- Tests.

PHASE 4 — DASHBOARD REALTIME
- Latest endpoint.
- Overview cards.
- Status.
- Charts hari ini.
- Responsive HP.

PHASE 5 — ANALYTICS
- Energy integration.
- Hourly/daily summaries.
- Daily/monthly pages.
- Export CSV.
- Existing CSV importer.

PHASE 6 — PRODUCTION
- Prod Compose.
- Nginx.
- Security.
- Backup.
- Deployment docs.
- Production checklist.

Pada akhir setiap phase:
- jalankan lint
- jalankan tests
- perbaiki error
- update README
- jangan tinggalkan TODO kritis

======================================================================
20. OUTPUT YANG WAJIB DIHASILKAN CODEX
======================================================================

Codex harus menghasilkan:

- seluruh source code
- migration
- Dockerfiles
- docker compose dev/prod
- Nginx config
- .env.example
- gateway Windows
- import CSV
- tests
- README lengkap
- dokumentasi register
- dokumentasi API
- dokumentasi development
- dokumentasi production
- troubleshooting

Jangan hanya memberi contoh kode. Implementasikan proyek yang dapat dijalankan.

======================================================================
21. CATATAN DESAIN JANGKA PANJANG
======================================================================

Tahap sekarang:
USB-RS485 → laptop gateway → API → PostgreSQL → Next.js

Tahap berikutnya:
ESP32 + RS485 → Wi-Fi → API yang sama

Tahap BMS:
ESP32/laptop membaca JK BMS → bms_telemetry → dashboard gabungan

API contract dan database harus dirancang agar pergantian gateway tidak memerlukan pembangunan ulang website.

Nama sementara proyek:
PLTS Monitor Rumah
