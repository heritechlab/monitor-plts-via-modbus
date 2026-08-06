import { describe, expect, it } from "vitest";

import { buildHistoryWindow } from "./history-range";

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
