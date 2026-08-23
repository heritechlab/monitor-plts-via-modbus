import { describe, expect, it } from "vitest";

import { derivePowerFlowVisuals, type GridState } from "./power-flow";

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
