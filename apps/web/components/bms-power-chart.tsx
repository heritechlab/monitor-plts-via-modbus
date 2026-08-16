"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { number, timeOnly } from "@/lib/format";
import type { BmsHistoryPoint } from "@/lib/types";

export function BmsPowerChart({ points }: { points: BmsHistoryPoint[] }) {
  if (!points.length) return <div className="empty">Belum ada data pada rentang ini.</div>;
  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 8, right: 4, left: -24, bottom: 0 }}>
          <defs>
            <linearGradient id="socFill" x1="0" y1="0" x2="0" y2="1">
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
            domain={[0, 100]}
            stroke="var(--muted)"
            tickLine={false}
            axisLine={false}
            fontSize={10}
            tickFormatter={(value) => `${number(value, 0)}%`}
          />
          <Tooltip
            labelFormatter={(value) => timeOnly(String(value))}
            formatter={(value) => [`${number(Number(value), 0)}%`, "SOC"]}
            contentStyle={{
              border: "1px solid var(--border)",
              borderRadius: 12,
              background: "var(--surface-raised)",
              fontSize: 11,
            }}
          />
          <Area
            type="monotone"
            dataKey="soc_percent"
            stroke="var(--green)"
            fill="url(#socFill)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
