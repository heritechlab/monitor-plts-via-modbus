import { describe, expect, it } from "vitest";

import { number, power } from "./format";

describe("format Indonesia", () => {
  it("memformat angka dan unit daya", () => {
    expect(number(1234.5, 1)).toContain("1.234,5");
    expect(power(1250)).toEqual({ value: "1,25", unit: "kW" });
  });
});

