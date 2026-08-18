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
    <div className="card p-4 md:p-5">
      <div className="text-xs text-muted font-medium">{label}</div>
      <div className={`font-display text-2xl font-semibold mt-1 ${toneClass}`}>{formatCurrency(value)}</div>
      {delta !== undefined && delta !== null && (
        <div
          className={`inline-block text-[11px] font-medium px-2 py-0.5 rounded-full mt-2 ${
            delta >= 0 ? "pill-positive" : "pill-negative"
          }`}
        >
          {formatPercent(delta)} vs. mes anterior
        </div>
      )}
    </div>
  );
}
