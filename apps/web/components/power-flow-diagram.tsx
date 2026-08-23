"use client";

import type { CSSProperties, ReactNode } from "react";
import { BatteryMedium, CircuitBoard, HousePlug, PlugZap, SunMedium } from "lucide-react";

import { number } from "@/lib/format";
import { derivePowerFlowVisuals, type GridState } from "@/lib/power-flow";

interface PowerFlowDiagramProps {
  pvWattW: number | null;
  gridVoltageV: number | null;
  gridState: GridState;
  /** Positif = mengisi baterai, negatif = discharge. null kalau tidak ada BMS
   * terhubung -- inverter sendiri tidak melaporkan arus baterai bertanda. */
  batteryPowerW: number | null;
  batterySocPercent: number | null;
  /** true kalau SOC berasal dari BMS (akurat); false berarti dari inverter
   * (turunan tegangan, jauh kurang akurat untuk LiFePO4). */
  batterySocFromBms: boolean;
  loadVaW: number | null;
  inverterOnline: boolean;
}

// Titik jangkar ikon dalam persen (0..100), dipakai bersama oleh node HTML
// (posisi absolute) dan path SVG di bawahnya -- keduanya HARUS memakai angka
// yang sama, karena SVG viewBox 0..100 tidak tahu tata letak grid/flex CSS.
const ANCHORS = {
  pv: { x: 10, y: 16 },
  grid: { x: 90, y: 16 },
  battery: { x: 10, y: 84 },
  load: { x: 90, y: 84 },
  center: { x: 50, y: 50 },
};

function FlowNode({
  icon,
  label,
  value,
  caption,
  tone,
  x,
  y,
  side,
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  caption?: string;
  tone: "green" | "blue" | "amber" | "muted";
  x: number;
  y: number;
  side: "left" | "right";
}) {
  const style: CSSProperties = {
    position: "absolute",
    top: `${y}%`,
    [side]: `${side === "left" ? x : 100 - x}%`,
    transform: "translateY(-50%)",
  };
  return (
    <div className={`power-flow-node power-flow-node--${side}`} style={style}>
      <div className={`power-flow-icon power-flow-icon--${tone}`}>{icon}</div>
      <div className="power-flow-node-text">
        <strong>{value}</strong>
        <span>{label}</span>
        {caption && <span className="power-flow-caption">{caption}</span>}
      </div>
    </div>
  );
}

// Elbow dua-segmen antara sudut node dan tepi kotak inverter, ditulis dengan
// urutan titik yang cocok dengan ARAH aliran -- SVG hanya bisa memasang
// panah (marker-end) di ujung AKHIR path, jadi arah trace path itu sendiri
// yang menentukan ke mana panah menghadap.
//   "into"  = dari sudut node menuju inverter (produksi PV, PLN menyuplai,
//             baterai discharge)
//   "out"   = dari inverter menuju sudut node (beban selalu begini; baterai
//             begini juga saat sedang diisi)
//
// `edgeY` memisahkan jalur masuk dari jalur keluar pada sisi yang sama: tanpa
// itu, PV dan baterai (sama-sama di kiri) akan menumpuk di satu garis
// horizontal yang sama, begitu pula PLN dan beban di kanan -- animasinya jadi
// tampak seperti satu aliran, bukan dua yang terpisah.
function elbowPath(
  corner: { x: number; y: number },
  edgeX: number,
  edgeY: number,
  direction: "into" | "out",
): string {
  if (direction === "into") {
    return `M ${corner.x} ${corner.y} V ${edgeY} H ${edgeX}`;
  }
  return `M ${edgeX} ${edgeY} H ${corner.x} V ${corner.y}`;
}

export function PowerFlowDiagram({
  pvWattW,
  gridVoltageV,
  gridState,
  batteryPowerW,
  batterySocPercent,
  batterySocFromBms,
  loadVaW,
  inverterOnline,
}: PowerFlowDiagramProps) {
  const { pvFlowing, gridFlowing, batteryCharging, batteryFlowing, loadFlowing, gridLabel, gridTone } =
    derivePowerFlowVisuals({ pvWattW, gridState, batteryPowerW, loadVaW });

  // Path elbow: turun/naik dari sudut menuju salah satu dari dua ketinggian
  // sambungan, lalu mendatar ke tepi kotak inverter (bukan sampai titik
  // pusatnya, supaya tidak menumpuk di belakang ikon).
  // Kotak inverter berukuran tetap 68px; dalam persen container (~285x270 px
  // pada layout dua kolom) itu sekitar 24% lebar dan 25% tinggi. Jalur harus
  // berhenti DI LUAR kotak, bukan di dalamnya -- kalau di dalam, kepala panah
  // tertutup kotak dan arah aliran jadi tak terlihat.
  const { pv, grid, battery, load, center } = ANCHORS;
  const boxHalfWidth = 14;
  const boxHalfHeight = 15;
  const centerLeftEdge = center.x - boxHalfWidth;
  const centerRightEdge = center.x + boxHalfWidth;
  // Dua ketinggian sambungan terpisah supaya PV dan baterai (sama-sama di kiri)
  // tidak menumpuk di satu garis, begitu pula PLN dan beban di kanan.
  const upperEdgeY = center.y - boxHalfHeight;
  const lowerEdgeY = center.y + boxHalfHeight;

  const batteryDirection: "into" | "out" = batteryCharging ? "out" : "into";
  const batteryTone = batteryCharging ? "green" : "amber";

  return (
    <div className="power-flow">
      <svg className="power-flow-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <marker id="power-flow-arrow-green" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 Z" fill="var(--green)" />
          </marker>
          <marker id="power-flow-arrow-blue" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 Z" fill="var(--blue)" />
          </marker>
          <marker id="power-flow-arrow-amber" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 Z" fill="var(--amber)" />
          </marker>
        </defs>
        <path
          className={`power-flow-path ${pvFlowing ? "power-flow-path--active" : ""}`}
          d={elbowPath(pv, centerLeftEdge, upperEdgeY, "into")}
          markerEnd={pvFlowing ? "url(#power-flow-arrow-green)" : undefined}
          pathLength={100}
        />
        <path
          className={`power-flow-path ${gridFlowing ? "power-flow-path--active" : ""}`}
          d={elbowPath(grid, centerRightEdge, upperEdgeY, "into")}
          markerEnd={gridFlowing ? "url(#power-flow-arrow-blue)" : undefined}
          pathLength={100}
        />
        <path
          className={`power-flow-path ${batteryFlowing ? "power-flow-path--active" : ""}`}
          d={elbowPath(battery, centerLeftEdge, lowerEdgeY, batteryDirection)}
          markerEnd={batteryFlowing ? `url(#power-flow-arrow-${batteryTone})` : undefined}
          pathLength={100}
        />
        <path
          className={`power-flow-path ${loadFlowing ? "power-flow-path--active" : ""}`}
          d={elbowPath(load, centerRightEdge, lowerEdgeY, "out")}
          markerEnd={loadFlowing ? "url(#power-flow-arrow-green)" : undefined}
          pathLength={100}
        />
      </svg>

      <FlowNode
        x={pv.x}
        y={pv.y}
        side="left"
        icon={<SunMedium size={18} />}
        tone="green"
        label="Produksi PV"
        value={`${number(pvWattW, 0)} W`}
      />
      <FlowNode
        x={grid.x}
        y={grid.y}
        side="right"
        icon={<PlugZap size={18} />}
        tone={gridTone}
        label="Jaringan (PLN)"
        value={gridVoltageV === null ? "—" : `${number(gridVoltageV, 0)} V`}
        caption={gridLabel}
      />
      <div
        className="power-flow-center"
        style={{
          position: "absolute",
          left: `${center.x}%`,
          top: `${center.y}%`,
          transform: "translate(-50%, -50%)",
        }}
      >
        <div className={`power-flow-inverter ${inverterOnline ? "power-flow-inverter--online" : ""}`}>
          <CircuitBoard size={20} />
          <span>PRIME</span>
        </div>
      </div>
      <FlowNode
        x={battery.x}
        y={battery.y}
        side="left"
        icon={<BatteryMedium size={18} />}
        tone={batteryPowerW === null ? "muted" : batteryCharging ? "green" : "amber"}
        label="Baterai"
        value={batterySocPercent === null ? "—" : `${number(batterySocPercent, 0)}%`}
        caption={
          batteryPowerW === null
            ? batterySocFromBms
              ? undefined
              : "Estimasi dari tegangan"
            : `${number(Math.abs(batteryPowerW), 0)} W (${batteryCharging ? "mengisi" : "discharge"})`
        }
      />
      <FlowNode
        x={load.x}
        y={load.y}
        side="right"
        icon={<HousePlug size={18} />}
        tone="muted"
        label="Beban AC"
        value={`${number(loadVaW, 0)} VA`}
        caption="Estimasi, bukan watt aktif"
      />
    </div>
  );
}
