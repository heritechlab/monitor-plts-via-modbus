"use client";

import {
  Area,
  CartesianGrid,
  Line,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { number, timeOnly } from "@/lib/format";
import type { HistoryPoint } from "@/lib/types";

export function PowerChart({ points }: { points: HistoryPoint[] }) {
  if (!points.length) return <div className="empty">Belum ada data pada rentang ini.</div>;
  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points} margin={{ top: 8, right: 4, left: -24, bottom: 0 }}>
          <defs>
            <linearGradient id="pvFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--green)" stopOpacity={0.3} />
              <stop offset="95%" stopColor="var(--green)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="recorded_at"
            tickFormatter={timeOnly}
            stroke="var(--muted)"
            tickLine={false}
            axisLine={false}
            fontSize={10}
            minTickGap={36}
          />
          <YAxis
            stroke="var(--muted)"
            tickLine={false}
            axisLine={false}
            fontSize={10}
            tickFormatter={(value) => `${number(value, 0)}`}
          />
          <Tooltip
            labelFormatter={(value) => timeOnly(String(value))}
            formatter={(value, name) => [
              `${number(Number(value), 1)} ${name === "pv_power_w" ? "W" : "VA"}`,
              name === "pv_power_w" ? "PV" : "Beban AC estimasi",
            ]}
            contentStyle={{
              border: "1px solid var(--border)",
              borderRadius: 12,
              background: "var(--surface-raised)",
              fontSize: 11,
            }}
          />
          <Area
            type="monotone"
            dataKey="pv_power_w"
            stroke="var(--green)"
            fill="url(#pvFill)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="ac_output_power_w"
            stroke="var(--blue)"
            strokeWidth={1.6}
            dot={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
