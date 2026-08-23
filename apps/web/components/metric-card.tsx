import type { LucideIcon } from "lucide-react";

export function MetricCard({
  label,
  value,
  unit,
  caption,
  icon: Icon,
  muted,
  compact,
}: {
  label: string;
  value: string;
  unit: string;
  caption?: string;
  icon: LucideIcon;
  muted?: boolean;
  /** Kartu lebih pendek/rapat -- dipakai grid KPI besar (mis. dashboard utama)
   * supaya tidak terlalu banyak makan tempat vertikal. */
  compact?: boolean;
}) {
  const classes = [
    "metric-card",
    muted && "metric-card--muted",
    compact && "metric-card--compact",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <article className={classes}>
      <div className="metric-label">
        <span>{label}</span>
        <Icon className="metric-icon" size={16} />
      </div>
      <div className="metric-value">
        {value}<span className="metric-unit">{unit}</span>
      </div>
      {caption && <div className="metric-caption">{caption}</div>}
    </article>
  );
}
