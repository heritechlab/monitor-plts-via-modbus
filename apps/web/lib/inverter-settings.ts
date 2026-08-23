/**
 * Referensi statis blok setelan inverter (0x4000, FC03).
 *
 * Bukan data live -- gateway produksi hanya membaca blok 0x3000 (telemetri).
 * Isi di sini berasal dari menjalankan scripts/inverter_settings_dump.py
 * secara manual di laptop server, lalu mencocokkan angkanya dengan menu
 * fisik di layar inverter. Perbarui `verifiedAt` dan baris terkait setiap
 * kali ada pembacaan ulang.
 */

export type SettingStatus = "confirmed" | "ambiguous" | "hypothesis" | "unmapped";

export interface InverterSettingEntry {
  code: string;
  label: string;
  registerAddress: string | string[];
  lastRaw: number | [number, number];
  displayValue: string;
  status: SettingStatus;
  note: string;
}

export const SETTINGS_VERIFIED_AT = "2026-08-23";

export const INVERTER_SETTINGS: InverterSettingEntry[] = [
  {
    code: "A0",
    label: "Mode kerja",
    registerAddress: "0x4000",
    lastRaw: 3,
    displayValue: "3 (diduga d3)",
    status: "hypothesis",
    note: "Operator mengonfirmasi mode aktif adalah d3. Nilai raw 3 cocok kalau d1/d2/d3 disimpan sebagai 1/2/3, tapi belum diuji langsung dengan mengubah A0 di menu.",
  },
  {
    code: "A2",
    label: "Constant charge voltage (batas atas / full)",
    registerAddress: "0x4008",
    lastRaw: 141,
    displayValue: "28,2 V",
    status: "confirmed",
    note: "Cocok persis dengan menu inverter yang dibaca operator. Skala per-12V dikonfirmasi manual: nilai disimpan per baterai tunggal, dikali 2 untuk sistem 24 V.",
  },
  {
    code: "A3",
    label: "Floating charge voltage",
    registerAddress: "0x4009",
    lastRaw: 139,
    displayValue: "27,8 V",
    status: "confirmed",
    note: "Cocok persis dengan menu inverter yang dibaca operator (27,8 V) -- satu-satunya register di blok ini bernilai itu, jadi tidak ambigu.",
  },
  {
    code: "A4",
    label: "Low voltage protection point",
    registerAddress: "0x400D",
    lastRaw: 119,
    displayValue: "23,8 V",
    status: "confirmed",
    note: "Cocok persis dengan menu inverter yang dibaca operator (23,8 V) -- satu-satunya register di blok ini bernilai itu, jadi tidak ambigu.",
  },
  {
    code: "A5",
    label: "Auto start output recover voltage",
    registerAddress: "0x4010",
    lastRaw: 123,
    displayValue: "24,6 V",
    status: "confirmed",
    note: "Terbukti lewat uji satu-klik: A5 diturunkan dari 24,8 V ke 24,6 V di menu (tersimpan dengan tahan FUNCTION 3 detik), lalu dibaca ulang. 0x4010 ikut turun ke 123 (24,6 V); 0x400E tetap 124 (24,8 V) -- jadi 0x400E BUKAN A5, kembar nilainya kebetulan saja.",
  },
  {
    code: "A6",
    label: "Kembali ke mode baterai",
    registerAddress: ["0x400F", "0x4012"],
    lastRaw: [129, 129],
    displayValue: "25,8 V (per menu operator)",
    status: "ambiguous",
    note: "Operator sempat mengubah A6 ke 26,0 V dan membaca ulang blok -- kedua register tetap 129/129, tidak ada yang bergerak. Itu bisa berarti A6 bukan di salah satu register ini, TAPI manual mensyaratkan menahan tombol FUNCTION 3 detik untuk menyimpan sebelum keluar dari menu setelan; kalau langkah itu terlewat, perubahannya tidak pernah tersimpan dan uji itu tidak berlaku. Sekarang A6 kembali terbaca 25,8 V, cocok dengan kedua register lagi. Perlu diulang dengan memastikan penyimpanan berhasil sebelum baca ulang.",
  },
  {
    code: "A7",
    label: "Pindah ke mode PLN",
    registerAddress: "0x4013",
    lastRaw: 125,
    displayValue: "25,0 V",
    status: "confirmed",
    note: "Cocok persis dengan menu inverter yang dibaca operator. Diuji langsung dua kali: beban 500-600 W menurunkan tegangan ke 25,8 V (masih di atas ambang) tanpa berpindah; dan dengan PLN tercolok pada tegangan baterai 25,8-26,0 V, inverter tetap di mode baterai -- sesuai setelan.",
  },
  {
    code: "A1, A8-A18",
    label: "Belum dipetakan",
    registerAddress: "0x4001-0x4007, 0x400A-0x400C, 0x400E, 0x4011, 0x4014-0x401F",
    lastRaw: 0,
    displayValue: "—",
    status: "unmapped",
    note: "Register-register ini terbukti diam (bukan pengukuran), tapi urutan alamatnya tidak mengikuti urutan kode A di menu -- percobaan menggeser posisi tidak pernah cocok. 0x400E terbukti BUKAN A5 (diam saat A5 diubah), jadi ia menyimpan sesuatu yang lain, belum diketahui apa. A1 (arus charge PLN, pilihan C0-C6) tidak bisa dicocokkan dengan cara yang sama karena bukan tegangan. Pemetaannya baru bisa dipastikan lewat kecocokan nilai satu per satu, seperti A2/A3/A4/A5/A7.",
  },
];

export const SETTINGS_STATUS_LABEL: Record<SettingStatus, string> = {
  confirmed: "Terbukti",
  ambiguous: "Ambigu",
  hypothesis: "Dugaan",
  unmapped: "Belum dipetakan",
};
