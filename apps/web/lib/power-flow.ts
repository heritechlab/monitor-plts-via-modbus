export type GridState = "supplying" | "standby" | "disconnected" | "unknown";

/** Ambang batas dianggap "mengalir" untuk keperluan visual (garis putus-putus
 * hijau vs statis) -- bukan ambang deteksi anomali, sekadar menghindari garis
 * "aktif" berkedip untuk noise pengukuran mendekati nol. */
const FLOW_THRESHOLD_W = 5;

export function derivePowerFlowVisuals(props: {
  pvWattW: number | null;
  gridState: GridState;
  batteryPowerW: number | null;
  loadVaW: number | null;
}): {
  pvFlowing: boolean;
  gridFlowing: boolean;
  batteryCharging: boolean;
  batteryFlowing: boolean;
  loadFlowing: boolean;
  gridLabel: string;
  gridTone: "blue" | "muted";
} {
  const { pvWattW, gridState, batteryPowerW, loadVaW } = props;
  const gridLabelByState: Record<GridState, string> = {
    supplying: "Menyuplai beban",
    standby: "Standby",
    disconnected: "Tidak terpasang",
    unknown: "—",
  };
  return {
    pvFlowing: (pvWattW ?? 0) > FLOW_THRESHOLD_W,
    gridFlowing: gridState === "supplying",
    batteryCharging: batteryPowerW !== null && batteryPowerW >= 0,
    batteryFlowing: batteryPowerW !== null && Math.abs(batteryPowerW) > FLOW_THRESHOLD_W,
    loadFlowing: (loadVaW ?? 0) > FLOW_THRESHOLD_W,
    gridLabel: gridLabelByState[gridState],
    gridTone: gridState === "supplying" ? "blue" : "muted",
  };
}
