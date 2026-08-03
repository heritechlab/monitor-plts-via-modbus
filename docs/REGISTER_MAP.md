# Register map PRIME LFT10224-H40

Seluruh operasi Modbus bersifat **read-only** menggunakan FC04, slave 1, 9600 8N1.

| Register | Field | Skala |
|---|---|---|
| `0x3001` | Tegangan output AC | raw / 10 V |
| `0x3002` | Tegangan baterai | raw / 10 V |
| `0x3003` | Arus output AC | raw / 10 A |
| `0x3004` | Persentase beban | raw % |
| `0x3005` | Estimasi beban semu inverter | raw VA (estimasi) |
| `0x3009` | Suhu inverter | raw °C |
| `0x3010` | Arus PV | raw / 10 A |
| `0x3012` | Tegangan PV | raw / 10 V |

Daya PV dihitung sebagai `pv_voltage_v × pv_current_a`. Register lain tetap
disimpan tanpa diberi arti hingga terverifikasi. Jangan menjalankan QModMaster
bersamaan dengan gateway karena COM3 hanya dapat dimiliki satu proses.

## Koreksi hasil validasi lapangan

Perbandingan serentak dengan smart plug menunjukkan `0x3005` mengikuti
`load_percent × kapasitas nominal` dan mendekati `tegangan × arus` (VA), tetapi
tidak mengikuti watt aktif smart plug. Karena itu:

- `0x3005` tidak boleh dipakai sebagai watt/kWh aktif;
- field transport lama `ac_output_power_w` dipertahankan hanya untuk kompatibilitas;
- UI menampilkannya sebagai beban AC estimasi dalam VA/kVAh;
- daya aktif memerlukan meter eksternal atau register lain yang sudah tervalidasi;
- surplus PV tidak dihitung dari pengurangan W terhadap VA.

Mapping hasil koreksi diberi `register_map_version=prime-v2` dan
`decoder_version=prime-v2-apparent-load`.

## Inspeksi register dari dashboard

Halaman publik `/settings` menampilkan 32 raw register FC04 terakhir dan
menganalisis perubahan dari riwayat telemetry yang sudah ada. Register yang
belum dipetakan hanya diberi status kandidat bila variasi dan korelasinya cukup
kuat; status tersebut tetap memerlukan validasi manual sebelum masuk register
map resmi.

Analisis ini database-only: tidak menambah polling serial, tidak melakukan scan
FC03, dan tidak mengganggu siklus gateway/dashboard live. Pemindaian alamat baru
di luar blok FC04 yang sudah dibaca harus dilakukan nanti melalui prosedur
terpisah yang dibatasi dan diawasi.
