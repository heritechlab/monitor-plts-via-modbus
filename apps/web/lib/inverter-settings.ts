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
    code: "A6",
    label: "Kembali ke mode baterai",
    registerAddress: ["0x400F", "0x4012"],
    lastRaw: [129, 129],
    displayValue: "belum ditemukan",
    status: "unmapped",
    note: "Kedua kandidat GUGUR. Operator mengubah A6 di menu dari 25,8 V ke 26,0 V, lalu blok dibaca ulang -- 0x400F dan 0x4012 tetap 129/129, tidak ada yang bergerak ke nilai yang diharapkan (130). A6 bukan di salah satu register ini; letaknya harus dicari di alamat lain.",
  },
  {
    code: "A7",
    label: "Pindah ke mode PLN",
    registerAddress: "0x4013",
    lastRaw: 125,
    displayValue: "25,0 V",
    status: "confirmed",
    note: "Cocok persis dengan menu inverter yang dibaca operator. Diuji langsung: beban 500-600 W menurunkan tegangan ke 25,8 V (masih di atas ambang) dan inverter tetap di mode baterai, sesuai setelan.",
  },
  {
    code: "A1, A3-A5, A8-A18",
    label: "Belum dipetakan",
    registerAddress: "0x4001-0x4007, 0x4009-0x401F",
    lastRaw: 0,
    displayValue: "—",
    status: "unmapped",
    note: "Register-register ini terbukti diam (bukan pengukuran), tapi urutan alamatnya tidak mengikuti urutan kode A di menu -- percobaan menggeser posisi tidak pernah cocok. Pemetaannya baru bisa dipastikan lewat kecocokan nilai satu per satu, seperti A2/A6/A7.",
  },
];

export const SETTINGS_STATUS_LABEL: Record<SettingStatus, string> = {
  confirmed: "Terbukti",
  ambiguous: "Ambigu",
  hypothesis: "Dugaan",
  unmapped: "Belum dipetakan",
};
