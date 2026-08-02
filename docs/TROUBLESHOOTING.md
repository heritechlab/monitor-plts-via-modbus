# Troubleshooting

## COM3 tidak dapat dibuka

- Tutup QModMaster dan aplikasi serial lain.
- Pastikan CH340 terlihat di Device Manager.
- Pastikan `SERIAL_PORT=COM3` sesuai nomor aktual.
- Cabut-pasang USB-RS485 lalu jalankan gateway kembali.

## Dashboard menampilkan backend tidak dapat dihubungi

- Buka `http://127.0.0.1:8000/health`.
- Periksa `data/runtime/api-error.log` untuk mode native.
- Untuk Docker, jalankan `docker compose ... ps` dan `logs api`.

## Gateway API key ditolak

Nilai `DEVICE_API_KEY` pada root `.env` dan `.env` gateway harus sama saat device
pertama dibuat. Jangan menaruh API key di screenshot atau log.

## Data stale tetapi gateway online

Periksa status serial dan `last_serial_success_at`. Ini berarti heartbeat API
berjalan, tetapi inverter/COM tidak menghasilkan frame valid.

## Laptop restart atau sleep

Matikan sleep/hibernate secara manual. Pasang Scheduled Task gateway setelah
pengujian manual berhasil. Service API/web dapat dijalankan kembali dengan
script start yang sama.

