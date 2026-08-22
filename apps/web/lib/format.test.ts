import { describe, expect, it } from "vitest";

import { apparentEnergy, apparentPower, dayLabel, number, power } from "./format";

describe("format Indonesia", () => {
  it("memformat angka dan unit daya", () => {
    expect(number(1234.5, 1)).toContain("1.234,5");
    expect(power(1250)).toEqual({ value: "1,25", unit: "kW" });
  });

  it("membedakan daya semu dari watt aktif", () => {
    expect(apparentPower(212)).toEqual({ value: "212", unit: "VA" });
    expect(apparentPower(1250)).toEqual({ value: "1,25", unit: "kVA" });
    expect(apparentEnergy(4.329)).toBe("4,329 kVAh");
  });

  it("memformat label hari dari tanggal ISO", () => {
    expect(dayLabel("2026-08-03")).toBe("Sen, 03 Agu");
    expect(dayLabel(null)).toBe("—");
    expect(dayLabel(undefined)).toBe("—");
  });
});
