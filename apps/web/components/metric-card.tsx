import type { LucideIcon } from "lucide-react";

export function MetricCard({
  label,
  value,
  unit,
  caption,
  icon: Icon,
}: {
  label: string;
  value: string;
  unit: string;
  caption?: string;
  icon: LucideIcon;
}) {
  return (
    <article className="metric-card">
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

