/**
 * Peta alamat blok setelan inverter (0x4000, FC03) -> kode A0-A18 di menu.
 *
 * Nilainya sendiri LIVE -- gateway produksi membaca blok ini tiap beberapa
 * menit dan menyimpannya (lihat GET /devices/{slug}/settings/latest). Yang
 * statis di sini hanya PEMETAAN alamat->kode, karena baru sebagian terbukti
 * lewat menu fisik inverter. Perbarui saat ada bukti baru (mis. hasil uji
 * satu-klik seperti yang dipakai membuktikan A5 = 0x4010).
 */

export type SettingStatus = "confirmed" | "ambiguous" | "hypothesis" | "unmapped";

/** raw/10 memberi volt per baterai tunggal; sistem 24V pakai 2 baterai (x2).
 * Dikonfirmasi dua arah: menu operator DAN manual ("24V system is 2 batteries"). */
type ValueScale = "battery-voltage-x2";

export interface InverterSettingEntry {
  code: string;
  label: string;
  /** Alamat register konkret untuk dicari nilainya di raw_registers, atau
   * string deskriptif (bukan alamat tunggal) untuk baris ringkasan seperti
   * "sisanya belum dipetakan" -- baris begitu tidak punya nilai live sendiri. */
  registerAddress: string | string[];
  scale?: ValueScale;
  status: SettingStatus;
  note: string;
}

export const SETTINGS_MAPPING_VERIFIED_AT = "2026-08-23";

export const INVERTER_SETTINGS: InverterSettingEntry[] = [
  {
    code: "A0",
    label: "Mode kerja",
    registerAddress: "0x4000",
    status: "hypothesis",
    note: "Operator mengonfirmasi mode aktif adalah d3. Nilai raw 3 cocok kalau d1/d2/d3 disimpan sebagai 1/2/3, tapi belum diuji langsung dengan mengubah A0 di menu.",
  },
  {
    code: "A2",
    label: "Constant charge voltage (batas atas / full)",
    registerAddress: "0x4008",
    scale: "battery-voltage-x2",
    status: "confirmed",
    note: "Cocok persis dengan menu inverter yang dibaca operator (28,2 V). Skala per-12V dikonfirmasi manual: nilai disimpan per baterai tunggal, dikali 2 untuk sistem 24 V.",
  },
  {
    code: "A3",
    label: "Floating charge voltage",
    registerAddress: "0x4009",
    scale: "battery-voltage-x2",
    status: "confirmed",
    note: "Cocok persis dengan menu inverter yang dibaca operator (27,8 V) -- satu-satunya register di blok ini bernilai itu saat diverifikasi, jadi tidak ambigu.",
  },
  {
    code: "A4",
    label: "Low voltage protection point",
    registerAddress: "0x400D",
    scale: "battery-voltage-x2",
    status: "confirmed",
    note: "Cocok persis dengan menu inverter yang dibaca operator (23,8 V) -- satu-satunya register di blok ini bernilai itu saat diverifikasi, jadi tidak ambigu.",
  },
  {
    code: "A5",
    label: "Auto start output recover voltage",
    registerAddress: "0x4010",
    scale: "battery-voltage-x2",
    status: "confirmed",
    note: "Terbukti lewat uji satu-klik: A5 diturunkan dari 24,8 V ke 24,6 V di menu (tersimpan dengan tahan FUNCTION 3 detik), lalu dibaca ulang. 0x4010 ikut turun ke 24,6 V; 0x400E tetap di 24,8 V -- jadi 0x400E BUKAN A5, kembar nilainya kebetulan saja.",
  },
  {
    code: "A6",
    label: "Kembali ke mode baterai",
    registerAddress: ["0x400F", "0x4012"],
    scale: "battery-voltage-x2",
    status: "ambiguous",
    note: "Operator sempat mengubah A6 di menu dan membaca ulang blok -- kedua register tidak bergerak. Itu bisa berarti A6 bukan di salah satu register ini, TAPI manual mensyaratkan menahan tombol FUNCTION 3 detik untuk menyimpan sebelum keluar dari menu setelan; kalau langkah itu terlewat, perubahannya tidak pernah tersimpan dan uji itu tidak berlaku. Perlu diulang dengan cara yang sama yang berhasil membuktikan A5 (satu klik, pastikan tersimpan, baca ulang).",
  },
  {
    code: "A7",
    label: "Pindah ke mode PLN",
    registerAddress: "0x4013",
    scale: "battery-voltage-x2",
    status: "confirmed",
    note: "Cocok persis dengan menu inverter yang dibaca operator (25,0 V). Diuji langsung dua kali: beban 500-600 W menurunkan tegangan ke 25,8 V (masih di atas ambang) tanpa berpindah; dan dengan PLN tercolok pada tegangan baterai 25,8-26,0 V, inverter tetap di mode baterai -- sesuai setelan.",
  },
  {
    code: "A1, A8-A18",
    label: "Belum dipetakan",
    registerAddress: "0x4001-0x4007, 0x400A-0x400C, 0x400E, 0x4011, 0x4014-0x401F",
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

const SINGLE_ADDRESS_PATTERN = /^0x[0-9A-Fa-f]{4}$/;

/** Alamat konkret untuk dicari di raw_registers, atau null kalau entry ini
 * cuma deskripsi rentang (baris ringkasan "belum dipetakan"). */
export function concreteAddresses(entry: InverterSettingEntry): string[] | null {
  const addresses = Array.isArray(entry.registerAddress)
    ? entry.registerAddress
    : [entry.registerAddress];
  return addresses.every((address) => SINGLE_ADDRESS_PATTERN.test(address))
    ? addresses
    : null;
}

export function formatSettingValue(
  entry: InverterSettingEntry,
  rawRegisters: Record<string, number>,
): { raw: string; value: string } {
  const addresses = concreteAddresses(entry);
  if (!addresses) return { raw: "—", value: "—" };

  const raws = addresses.map((address) => rawRegisters[address]);
  if (raws.some((raw) => raw === undefined)) {
    return { raw: "—", value: "belum ada data" };
  }

  const rawText = raws.join(" / ");
  if (!entry.scale) return { raw: rawText, value: rawText };

  const volts = raws.map((raw) => `${((raw / 10) * 2).toFixed(1).replace(".", ",")} V`);
  return { raw: rawText, value: volts.join(" / ") };
}
