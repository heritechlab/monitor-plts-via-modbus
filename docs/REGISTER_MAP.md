# Register map PRIME LFT10224-H40

Seluruh operasi Modbus bersifat **read-only** menggunakan FC04, slave 1, 9600 8N1.

| Register | Field | Skala |
|---|---|---|
| `0x3001` | Tegangan output AC | raw / 10 V |
| `0x3002` | Tegangan baterai | raw / 10 V |
| `0x3003` | Arus output AC | raw / 10 A |
| `0x3004` | Persentase beban | raw % |
| `0x3005` | Daya output AC | raw W |
| `0x3009` | Suhu inverter | raw °C |
| `0x3010` | Arus PV | raw / 10 A |
| `0x3012` | Tegangan PV | raw / 10 V |

Daya PV dihitung sebagai `pv_voltage_v × pv_current_a`. Register lain tetap
disimpan tanpa diberi arti hingga terverifikasi. Jangan menjalankan QModMaster
bersamaan dengan gateway karena COM3 hanya dapat dimiliki satu proses.

