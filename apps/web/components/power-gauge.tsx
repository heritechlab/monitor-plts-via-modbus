"use client";

import { RadialBar, RadialBarChart, ResponsiveContainer } from "recharts";

import { number } from "@/lib/format";

function gaugeColor(percent: number): string {
  if (percent >= 100) return "var(--red)";
  if (percent >= 80) return "var(--amber)";
  return "var(--green)";
}

export function PowerGauge({
  label,
  value,
  max,
  unit,
}: {
  label: string;
  value: number | null;
  max: number;
  unit: string;
}) {
  const safeValue = value ?? 0;
  const percent = max > 0 ? Math.min(150, (safeValue / max) * 100) : 0;
  const color = gaugeColor(percent);
  const data = [{ value: Math.min(100, percent), fill: color }];

  return (
    <div style={{ position: "relative", height: 150 }}>
      <ResponsiveContainer height="100%" width="100%">
        <RadialBarChart
          barSize={12}
          cx="50%"
          cy="62%"
          data={data}
          endAngle={-20}
          innerRadius="72%"
          outerRadius="100%"
          startAngle={200}
        >
          <RadialBar
            background={{ fill: "color-mix(in srgb, var(--muted) 18%, transparent)" }}
            cornerRadius={8}
            dataKey="value"
            isAnimationActive={false}
          />
        </RadialBarChart>
      </ResponsiveContainer>
      <div
        style={{
          position: "absolute",
          top: "56%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 24, fontWeight: 680, letterSpacing: "-.03em", color: "var(--text)" }}>
          {number(value, 0)}
          <span style={{ fontSize: 13, color: "var(--muted)", marginLeft: 4 }}>{unit}</span>
        </div>
        <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 2 }}>{label}</div>
      </div>
    </div>
  );
}
