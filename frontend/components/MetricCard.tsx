import { formatCurrency, formatPercent } from "@/lib/api";

export default function MetricCard({
  label,
  value,
  delta,
  tone = "neutral",
}: {
  label: string;
  value: number;
  delta?: number | null;
  tone?: "positive" | "negative" | "neutral";
}) {
  const toneClass =
    tone === "positive" ? "text-accent" : tone === "negative" ? "text-negative" : "text-ink";

  return (
    <div className="card p-4 md:p-5 relative overflow-hidden">
      <div
        className={`absolute top-0 left-0 right-0 h-[3px] ${
          tone === "positive" ? "bg-accent" : tone === "negative" ? "bg-negative" : "bg-gold"
        }`}
      />
      <div className="text-xs text-muted font-medium uppercase tracking-wide">{label}</div>
      <div className={`font-numeric text-2xl font-semibold mt-1.5 ${toneClass}`}>
        {formatCurrency(value)}
      </div>
      {delta !== undefined && delta !== null && (
        <div
          className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full mt-2.5 ${
            delta >= 0 ? "pill-positive" : "pill-negative"
          }`}
        >
          <span>{delta >= 0 ? "↑" : "↓"}</span>
          {formatPercent(delta)} vs. mes anterior
        </div>
      )}
    </div>
  );
}
