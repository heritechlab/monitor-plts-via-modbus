import { describe, expect, it } from "vitest";

import { combineBatteryPacks, derivePowerFlowVisuals, type GridState } from "./power-flow";

describe("derivePowerFlowVisuals", () => {
  it("marks PV and load as flowing above the threshold, static at/below it", () => {
    const above = derivePowerFlowVisuals({ pvWattW: 378, gridState: "standby", batteryPowerW: null, loadVaW: 241 });
    expect(above.pvFlowing).toBe(true);
    expect(above.loadFlowing).toBe(true);

    const atThreshold = derivePowerFlowVisuals({ pvWattW: 5, gridState: "standby", batteryPowerW: null, loadVaW: 5 });
    expect(atThreshold.pvFlowing).toBe(false);
    expect(atThreshold.loadFlowing).toBe(false);
  });

  it("treats null PV/load as zero, not flowing", () => {
    const result = derivePowerFlowVisuals({ pvWattW: null, gridState: "standby", batteryPowerW: null, loadVaW: null });
    expect(result.pvFlowing).toBe(false);
    expect(result.loadFlowing).toBe(false);
  });

  it("only marks the grid as flowing when actively supplying, not merely connected", () => {
    expect(derivePowerFlowVisuals({ pvWattW: 0, gridState: "supplying", batteryPowerW: null, loadVaW: 0 }).gridFlowing).toBe(true);
    expect(derivePowerFlowVisuals({ pvWattW: 0, gridState: "standby", batteryPowerW: null, loadVaW: 0 }).gridFlowing).toBe(false);
    expect(derivePowerFlowVisuals({ pvWattW: 0, gridState: "disconnected", batteryPowerW: null, loadVaW: 0 }).gridFlowing).toBe(false);
  });

  it("labels every grid state distinctly, standby distinct from disconnected", () => {
    const cases: Array<[GridState, string]> = [
      ["supplying", "Menyuplai beban"],
      ["standby", "Standby"],
      ["disconnected", "Tidak terpasang"],
      ["unknown", "—"],
    ];
    for (const [gridState, label] of cases) {
      expect(derivePowerFlowVisuals({ pvWattW: 0, gridState, batteryPowerW: null, loadVaW: 0 }).gridLabel).toBe(label);
    }
  });

  it("reads battery sign as charge direction: non-negative is charging", () => {
    expect(derivePowerFlowVisuals({ pvWattW: 0, gridState: "standby", batteryPowerW: 173, loadVaW: 0 }).batteryCharging).toBe(true);
    expect(derivePowerFlowVisuals({ pvWattW: 0, gridState: "standby", batteryPowerW: 0, loadVaW: 0 }).batteryCharging).toBe(true);
    expect(derivePowerFlowVisuals({ pvWattW: 0, gridState: "standby", batteryPowerW: -50, loadVaW: 0 }).batteryCharging).toBe(false);
  });

  it("battery flow uses the magnitude, not signed value, against the threshold", () => {
    expect(derivePowerFlowVisuals({ pvWattW: 0, gridState: "standby", batteryPowerW: -173, loadVaW: 0 }).batteryFlowing).toBe(true);
    expect(derivePowerFlowVisuals({ pvWattW: 0, gridState: "standby", batteryPowerW: -2, loadVaW: 0 }).batteryFlowing).toBe(false);
  });

  it("battery is never flowing when there is no BMS reading at all", () => {
    const result = derivePowerFlowVisuals({ pvWattW: 0, gridState: "standby", batteryPowerW: null, loadVaW: 0 });
    expect(result.batteryFlowing).toBe(false);
    // charging/discharging is meaningless without a reading, but must still resolve
    // to a boolean rather than throw -- the component decides what to render for it.
    expect(result.batteryCharging).toBe(false);
  });
});

describe("combineBatteryPacks", () => {
  it("sums two packs both charging, matching the reported dashboard numbers", () => {
    const result = combineBatteryPacks([
      { packPowerW: 73, packCurrentA: 2.77, socPercent: 47 },
      { packPowerW: 65, packCurrentA: 2.46, socPercent: 55 },
    ]);
    expect(result.batteryPowerW).toBe(138);
    expect(result.batterySocPercent).toBe(51);
  });

  it("nets opposite directions instead of summing magnitudes", () => {
    // One pack charging, one discharging -- the bank's net flow is the
    // difference, not 150 W. This is the reason power is summed SIGNED rather
    // than combined-then-signed by an overall direction.
    const result = combineBatteryPacks([
      { packPowerW: 100, packCurrentA: 4, socPercent: 60 },
      { packPowerW: 50, packCurrentA: -2, socPercent: 60 },
    ]);
    expect(result.batteryPowerW).toBe(50);
  });

  it("ignores packs with no power reading but keeps the ones that do", () => {
    const result = combineBatteryPacks([
      { packPowerW: null, packCurrentA: null, socPercent: null },
      { packPowerW: 90, packCurrentA: -3, socPercent: 40 },
    ]);
    expect(result.batteryPowerW).toBe(-90);
    expect(result.batterySocPercent).toBe(40);
  });

  it("returns null for both fields when no pack has data", () => {
    const result = combineBatteryPacks([{ packPowerW: null, packCurrentA: null, socPercent: null }]);
    expect(result.batteryPowerW).toBeNull();
    expect(result.batterySocPercent).toBeNull();
  });

  it("returns null for an empty pack list", () => {
    const result = combineBatteryPacks([]);
    expect(result.batteryPowerW).toBeNull();
    expect(result.batterySocPercent).toBeNull();
  });
});
