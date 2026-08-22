import { localDateInput } from "./format";

export const historyRanges = {
  "1h": { label: "1 jam", hours: 1, resolution: "1m" },
  "6h": { label: "6 jam", hours: 6, resolution: "5m" },
  "12h": { label: "12 jam", hours: 12, resolution: "5m" },
  "24h": { label: "24 jam", hours: 24, resolution: "5m" },
  "7d": { label: "7 hari", hours: 24 * 7, resolution: "15m" },
  "30d": { label: "30 hari", hours: 24 * 30, resolution: "1h" },
} as const;

export type HistoryRangeKey = keyof typeof historyRanges;

const jakartaOffset = "+07:00";
const datePattern = /^\d{4}-\d{2}-\d{2}$/;

export function buildHistoryWindow(
  selectedDate: string,
  range: HistoryRangeKey,
  now = new Date(),
): { start: Date; end: Date } {
  if (!datePattern.test(selectedDate)) {
    throw new Error("Format tanggal tidak valid");
  }

  const today = localDateInput(now);
  if (selectedDate > today) {
    throw new Error("Tanggal mendatang belum dapat dipilih");
  }

  const isToday = selectedDate === today;
  const end = isToday
    ? new Date(now)
    : new Date(`${selectedDate}T23:59:59.999${jakartaOffset}`);
  if (Number.isNaN(end.getTime())) {
    throw new Error("Tanggal tidak valid");
  }

  const durationMs = historyRanges[range].hours * 3_600_000;
  // Tambahkan 1 ms untuk tanggal lampau agar rentang 24 jam tepat dimulai 00:00.
  const inclusiveAdjustment = isToday ? 0 : 1;
  const start = new Date(end.getTime() - durationMs + inclusiveAdjustment);

  return { start, end };
}

export type ResolutionKey = "1m" | "5m" | "15m" | "1h";

export function resolutionForDuration(durationMs: number): ResolutionKey {
  const hours = durationMs / 3_600_000;
  if (hours <= 6) return "1m";
  if (hours <= 24) return "5m";
  if (hours <= 24 * 14) return "15m";
  return "1h";
}

const timePattern = /^\d{2}:\d{2}$/;

/** Jendela waktu jam-tertentu pada TANGGAL TERPILIH (bukan relatif ke sekarang),
 * supaya kurva produksi hari itu tetap terlihat lengkap kapan pun halaman dibuka —
 * berbeda dari rentang preset "N jam terakhir" yang bergantung waktu akses. */
export function buildCustomHourWindow(
  selectedDate: string,
  startTime: string,
  endTime: string,
): { start: Date; end: Date } {
  if (!datePattern.test(selectedDate)) {
    throw new Error("Format tanggal tidak valid");
  }
  if (!timePattern.test(startTime) || !timePattern.test(endTime)) {
    throw new Error("Format jam tidak valid");
  }
  const start = new Date(`${selectedDate}T${startTime}:00${jakartaOffset}`);
  const end = new Date(`${selectedDate}T${endTime}:00${jakartaOffset}`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    throw new Error("Jam tidak valid");
  }
  if (end <= start) {
    throw new Error("Jam akhir harus setelah jam mulai");
  }
  return { start, end };
}
