import type { LucideIcon } from "lucide-react";

export function MetricCard({
  label,
  value,
  unit,
  caption,
  icon: Icon,
  muted,
}: {
  label: string;
  value: string;
  unit: string;
  caption?: string;
  icon: LucideIcon;
  muted?: boolean;
}) {
  return (
    <article className={`metric-card${muted ? " metric-card--muted" : ""}`}>
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
