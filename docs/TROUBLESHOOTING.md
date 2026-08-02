# Troubleshooting

## Port COM tidak dapat dibuka atau berubah setelah restart

- Tutup QModMaster dan aplikasi serial lain.
- Pastikan CH340 terlihat di Device Manager.
- Gunakan `SERIAL_PORT=auto` agar satu adaptor CH340 ditemukan otomatis.
- Bila ada lebih dari satu adaptor serial, tetapkan nomor COM secara eksplisit.
- Cabut-pasang USB-RS485; gateway akan mencoba ulang tanpa perlu restart.

Periksa port saat ini:

```powershell
Get-CimInstance Win32_SerialPort | Format-Table DeviceID, Description
```

## `_greenlet` gagal memuat DLL

Install Microsoft Visual C++ Redistributable x64 lalu buka ulang PowerShell:

```powershell
winget install --id Microsoft.VCRedist.2015+.x64 -e --source winget
```

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
pengujian manual berhasil dan pasang task server dengan:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-native-task.ps1
```

Gateway task berjalan tersembunyi dan menulis `agents/inverter-gateway/data/gateway.log`.

## Tunnel hanya membuka sebagian path

Pada Published application route Cloudflare, kosongkan kolom Path untuk
`plts-home.udigi.id`. Nilai seperti `^/blog` mencegah homepage, aset Next.js,
dan proxy API dashboard diteruskan ke laptop.
