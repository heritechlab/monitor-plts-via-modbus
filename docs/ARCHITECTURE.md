# Arsitektur local-first

## Saat ini

```text
PRIME inverter --RS485/FC04--> gateway Python
                                  | commit-first
                                  v
                             SQLite queue ----HTTP loopback----> FastAPI
                                  |                                 |
                                  +--> CSV harian                   v
                                                            SQLite/PostgreSQL
                                                                    |
Browser <--HTTPS-- Cloudflare Tunnel <-- Next.js BFF <--------------+
```

FastAPI hanya bind ke `127.0.0.1`. Cloudflare Tunnel hanya mempublikasikan
Next.js pada port 3000. Browser tidak mengetahui alamat FastAPI maupun database.

## Migrasi mendatang

ESP32 mempertahankan kontrak `/api/v1/ingest/*`, mengganti `source` menjadi
`esp32-rs485`, memakai NTP, HTTPS, API key device, dan queue flash/SD. FastAPI,
database, serta dashboard dipindahkan ke VPS tanpa perubahan model data.

## Sumber kebenaran

- Raw register adalah bukti pengukuran utama.
- Metrics adalah hasil decode dengan `register_map_version` dan `decoder_version`.
- `recorded_at` adalah waktu pengukuran; `received_at` adalah waktu penerimaan API.
- `sample_id` menjamin resend aman dan idempotent.

