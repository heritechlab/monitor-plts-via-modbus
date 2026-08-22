import { describe, expect, it } from "vitest";

import { buildCustomHourWindow, buildHistoryWindow, resolutionForDuration } from "./history-range";

describe("buildHistoryWindow", () => {
  const now = new Date("2026-08-03T06:30:00+07:00");

  it("mengakhiri rentang hari ini pada waktu sekarang", () => {
    const window = buildHistoryWindow("2026-08-03", "12h", now);

    expect(window.end.toISOString()).toBe("2026-08-02T23:30:00.000Z");
    expect(window.start.toISOString()).toBe("2026-08-02T11:30:00.000Z");
  });

  it("mengakhiri rentang tanggal lampau di akhir hari Jakarta", () => {
    const window = buildHistoryWindow("2026-08-02", "12h", now);

    expect(window.start.toISOString()).toBe("2026-08-02T05:00:00.000Z");
    expect(window.end.toISOString()).toBe("2026-08-02T16:59:59.999Z");
  });

  it("mencakup satu tanggal penuh untuk 24 jam pada tanggal lampau", () => {
    const window = buildHistoryWindow("2026-08-02", "24h", now);

    expect(window.start.toISOString()).toBe("2026-08-01T17:00:00.000Z");
    expect(window.end.toISOString()).toBe("2026-08-02T16:59:59.999Z");
  });

  it("menolak tanggal mendatang", () => {
    expect(() => buildHistoryWindow("2026-08-04", "6h", now)).toThrow(
      "Tanggal mendatang belum dapat dipilih",
    );
  });

  it("mendukung tahun berbeda untuk riwayat lampau", () => {
    const pastYear = buildHistoryWindow("2025-12-25", "24h", now);

    expect(pastYear.start.toISOString()).toBe("2025-12-24T17:00:00.000Z");
    expect(pastYear.end.toISOString()).toBe("2025-12-25T16:59:59.999Z");
  });
});

describe("buildCustomHourWindow", () => {
  it("membangun rentang pada tanggal terpilih, bukan relatif ke sekarang", () => {
    const window = buildCustomHourWindow("2026-08-03", "06:00", "18:00");

    expect(window.start.toISOString()).toBe("2026-08-02T23:00:00.000Z");
    expect(window.end.toISOString()).toBe("2026-08-03T11:00:00.000Z");
  });

  it("menolak jam akhir sebelum atau sama dengan jam mulai", () => {
    expect(() => buildCustomHourWindow("2026-08-03", "18:00", "06:00")).toThrow(
      "Jam akhir harus setelah jam mulai",
    );
    expect(() => buildCustomHourWindow("2026-08-03", "06:00", "06:00")).toThrow(
      "Jam akhir harus setelah jam mulai",
    );
  });

  it("menolak format tanggal atau jam yang tidak valid", () => {
    expect(() => buildCustomHourWindow("03-08-2026", "06:00", "18:00")).toThrow(
      "Format tanggal tidak valid",
    );
    expect(() => buildCustomHourWindow("2026-08-03", "6:00", "18:00")).toThrow(
      "Format jam tidak valid",
    );
  });
});

describe("resolutionForDuration", () => {
  it("memilih resolusi berdasarkan panjang rentang", () => {
    expect(resolutionForDuration(6 * 3_600_000)).toBe("1m");
    expect(resolutionForDuration(12 * 3_600_000)).toBe("5m");
    expect(resolutionForDuration(24 * 3_600_000)).toBe("5m");
    expect(resolutionForDuration(7 * 24 * 3_600_000)).toBe("15m");
    expect(resolutionForDuration(30 * 24 * 3_600_000)).toBe("1h");
  });
});
