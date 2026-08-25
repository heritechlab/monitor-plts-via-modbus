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

/** Gabungkan beberapa pack BMS jadi satu angka daya dan SOC untuk diagram
 * aliran, yang cuma punya satu simpul "Baterai" -- bukan satu per pack.
 *
 * Daya dijumlahkan bertanda (bukan dijumlah lalu diberi tanda gabungan),
 * supaya kalau satu pack mengisi dan satu discharge bersamaan, hasilnya tetap
 * mencerminkan aliran neto ke/dari bank baterai secara keseluruhan.
 *
 * SOC dirata-rata sederhana (bukan berbobot kapasitas) -- pack B1 dan B2
 * sama-sama 24V 100Ah, jadi rata-rata sederhana sudah representatif. Kalau
 * suatu saat kapasitasnya berbeda, ini perlu diberi bobot per pack. */
export function combineBatteryPacks(
  packs: { packPowerW: number | null; packCurrentA: number | null; socPercent: number | null }[],
): { batteryPowerW: number | null; batterySocPercent: number | null } {
  const signedPowers = packs
    .map((pack) => {
      if (pack.packPowerW === null || pack.packPowerW === undefined) return null;
      const sign = (pack.packCurrentA ?? 0) < 0 ? -1 : 1;
      return sign * Math.abs(pack.packPowerW);
    })
    .filter((value): value is number => value !== null);

  const socs = packs
    .map((pack) => pack.socPercent)
    .filter((value): value is number => value !== null && value !== undefined);

  return {
    batteryPowerW: signedPowers.length > 0 ? signedPowers.reduce((a, b) => a + b, 0) : null,
    batterySocPercent: socs.length > 0 ? socs.reduce((a, b) => a + b, 0) / socs.length : null,
  };
}
