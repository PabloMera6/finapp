"use client";

import { useState } from "react";
import { api, formatCurrency } from "@/lib/api";

function currentYM() {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}
function prevYM({ year, month }: { year: number; month: number }) {
  return month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
}

type CompareRow = { category: string; month_a: number; month_b: number; diff: number; pct: number | null };
type CompareResponse = {
  month_a: string; month_b: string;
  totals_a: { income: number; expenses: number; savings: number; investment: number };
  totals_b: { income: number; expenses: number; savings: number; investment: number };
  categories: CompareRow[];
};

export default function ComparePage() {
  const now = currentYM();
  const prev = prevYM(now);
  const [a, setA] = useState(prev);
  const [b, setB] = useState(now);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const runCompare = () => {
    setLoading(true);
    api
      .get(`/api/analytics/comparison?year_a=${a.year}&month_a=${a.month}&year_b=${b.year}&month_b=${b.month}`)
      .then(setData)
      .finally(() => setLoading(false));
  };

  return (
    <div className="space-y-5 max-w-3xl">
      <h1 className="font-display text-xl font-semibold">Comparar meses</h1>

      <div className="card p-4 flex flex-wrap gap-4 items-end">
        <div>
          <label className="text-xs text-muted">Mes A</label>
          <input
            type="month"
            value={`${a.year}-${String(a.month).padStart(2, "0")}`}
            onChange={(e) => { const [y, m] = e.target.value.split("-"); setA({ year: +y, month: +m }); }}
            className="block input-field rounded-xl px-3 py-1.5 text-sm mt-1"
          />
        </div>
        <div>
          <label className="text-xs text-muted">Mes B</label>
          <input
            type="month"
            value={`${b.year}-${String(b.month).padStart(2, "0")}`}
            onChange={(e) => { const [y, m] = e.target.value.split("-"); setB({ year: +y, month: +m }); }}
            className="block input-field rounded-xl px-3 py-1.5 text-sm mt-1"
          />
        </div>
        <button onClick={runCompare} className="btn-primary rounded-xl px-4 py-2 text-sm font-medium">
          Comparar
        </button>
      </div>

      {loading && <p className="text-sm text-muted">Calculando...</p>}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: data.month_a, totals: data.totals_a },
              { label: data.month_b, totals: data.totals_b },
            ].map((col) => (
              <div key={col.label} className="card p-4">
                <div className="text-xs text-muted mb-2">{col.label}</div>
                <div className="text-sm space-y-1">
                  <div className="flex justify-between"><span className="text-muted">Ingresos</span><span>{formatCurrency(col.totals.income)}</span></div>
                  <div className="flex justify-between"><span className="text-muted">Gastos</span><span>{formatCurrency(col.totals.expenses)}</span></div>
                  <div className="flex justify-between font-medium"><span>Ahorro</span><span>{formatCurrency(col.totals.savings)}</span></div>
                  <div className="flex justify-between"><span className="text-muted">Inversión</span><span>{formatCurrency(col.totals.investment)}</span></div>
                </div>
              </div>
            ))}
          </div>

          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted border-b border-border">
                  <th className="px-3 py-2">Categoría</th>
                  <th className="px-3 py-2 text-right">{data.month_a}</th>
                  <th className="px-3 py-2 text-right">{data.month_b}</th>
                  <th className="px-3 py-2 text-right">Diferencia</th>
                  <th className="px-3 py-2 text-right">%</th>
                </tr>
              </thead>
              <tbody>
                {data.categories.map((row) => (
                  <tr key={row.category} className="border-b border-border last:border-0">
                    <td className="px-3 py-2">{row.category}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(row.month_a)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(row.month_b)}</td>
                    <td className={`px-3 py-2 text-right tabular-nums font-medium ${row.diff > 0 ? "text-negative" : "text-accent"}`}>
                      {row.diff > 0 ? "+" : ""}{formatCurrency(row.diff)}
                    </td>
                    <td className="px-3 py-2 text-right text-muted">{row.pct !== null ? `${row.pct > 0 ? "+" : ""}${row.pct}%` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
