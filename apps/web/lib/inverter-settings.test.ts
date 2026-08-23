import { describe, expect, it } from "vitest";

import { concreteAddresses, formatSettingValue, type InverterSettingEntry } from "./inverter-settings";

const confirmedSingle: InverterSettingEntry = {
  code: "A7",
  label: "Pindah ke mode PLN",
  registerAddress: "0x4013",
  scale: "battery-voltage-x2",
  status: "confirmed",
  note: "",
};

const ambiguousPair: InverterSettingEntry = {
  code: "A6",
  label: "Kembali ke mode baterai",
  registerAddress: ["0x400F", "0x4012"],
  scale: "battery-voltage-x2",
  status: "ambiguous",
  note: "",
};

const unscaled: InverterSettingEntry = {
  code: "A0",
  label: "Mode kerja",
  registerAddress: "0x4000",
  status: "hypothesis",
  note: "",
};

const summaryRow: InverterSettingEntry = {
  code: "A1, A8-A18",
  label: "Belum dipetakan",
  registerAddress: "0x4001-0x4007, 0x400A-0x400C, 0x4011, 0x4014-0x401F",
  status: "unmapped",
  note: "",
};

describe("concreteAddresses", () => {
  it("returns a single-element array for a plain hex address", () => {
    expect(concreteAddresses(confirmedSingle)).toEqual(["0x4013"]);
  });

  it("returns both addresses for an ambiguous pair", () => {
    expect(concreteAddresses(ambiguousPair)).toEqual(["0x400F", "0x4012"]);
  });

  it("returns null for a descriptive range string, not a lookup address", () => {
    expect(concreteAddresses(summaryRow)).toBeNull();
  });
});

describe("formatSettingValue", () => {
  it("converts raw to volts using the x2 battery scale, real menu-confirmed values", () => {
    // 0x4013 = 125 raw -> A7 = 25.0V, confirmed against the operator's own menu.
    expect(formatSettingValue(confirmedSingle, { "0x4013": 125 })).toEqual({
      raw: "125",
      value: "25,0 V",
    });
  });

  it("formats both candidates side by side for an ambiguous pair", () => {
    expect(formatSettingValue(ambiguousPair, { "0x400F": 129, "0x4012": 129 })).toEqual({
      raw: "129 / 129",
      value: "25,8 V / 25,8 V",
    });
  });

  it("shows raw only, no volt conversion, when the entry has no known scale", () => {
    expect(formatSettingValue(unscaled, { "0x4000": 3 })).toEqual({
      raw: "3",
      value: "3",
    });
  });

  it("reports missing data distinctly from a zero reading", () => {
    expect(formatSettingValue(confirmedSingle, {})).toEqual({
      raw: "—",
      value: "belum ada data",
    });
  });

  it("treats a partially-present pair as missing rather than showing one side blank", () => {
    expect(formatSettingValue(ambiguousPair, { "0x400F": 129 })).toEqual({
      raw: "—",
      value: "belum ada data",
    });
  });

  it("never attempts a lookup for a descriptive range row", () => {
    expect(formatSettingValue(summaryRow, { "0x4001": 100 })).toEqual({
      raw: "—",
      value: "—",
    });
  });
});
