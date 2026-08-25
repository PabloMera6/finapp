"use client";

import { useEffect, useRef, useState } from "react";
import { api, formatCurrency } from "@/lib/api";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, Cell,
} from "recharts";

type Summary = {
  period: { from: string; to: string };
  totals: { income: number; expenses: number; savings: number; investment: number; savings_rate: number; months: number };
  monthly: { month: string; income: number; expenses: number; savings: number; investment: number; savings_rate: number }[];
  top_categories: { category: string; amount: number }[];
};

type Merchant = { merchant: string; total: number; transaction_count: number; average_amount: number; last_date: string };
type AccountBreakdown = { account_id: string; account_name: string; institution: string; income: number; expenses: number; savings: number; investment: number; transaction_count: number };
type WeekdayBucket = { weekday: string; total: number; transaction_count: number; average_amount: number };
type Projection = {
  month: string; days_elapsed: number; days_total: number;
  income_so_far: number; expenses_so_far: number;
  projected_income: number; projected_expenses: number; projected_savings: number;
  is_current_month: boolean;
};
type MonthTransaction = {
  id: string; date: string; amount: number; description: string; type: string; source: string;
};

const defaultRange = () => {
  const now = new Date();
  const from = new Date(now.getFullYear(), now.getMonth() - 11, 1);
  return {
    from: `${from.getFullYear()}-${String(from.getMonth() + 1).padStart(2, "0")}`,
    to: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`,
  };
};

const HEAT_COLORS = ["#F5F3EC", "#EDE4CD", "#DFC79A", "#CBA562", "#B8823E", "#8C5F2A"];

function heatColor(value: number, max: number): string {
  if (max <= 0) return HEAT_COLORS[0];
  const ratio = value / max;
  const idx = Math.min(HEAT_COLORS.length - 1, Math.floor(ratio * (HEAT_COLORS.length - 1)));
  return HEAT_COLORS[idx];
}

// Último día del mes en formato YYYY-MM-DD, para pedir el rango completo
// de movimientos de ese mes al endpoint de transacciones.
function monthEnd(month: string): string {
  const [y, m] = month.split("-").map(Number);
  const last = new Date(y, m, 0).getDate();
  return `${month}-${String(last).padStart(2, "0")}`;
}

export default function AnalyticsPage() {
  const d = defaultRange();
  const [from, setFrom] = useState(d.from);
  const [to, setTo] = useState(d.to);
  const [data, setData] = useState<Summary | null>(null);
  const [merchants, setMerchants] = useState<Merchant[] | null>(null);
  const [byAccount, setByAccount] = useState<AccountBreakdown[] | null>(null);
  const [heatmap, setHeatmap] = useState<WeekdayBucket[] | null>(null);
  const [projection, setProjection] = useState<Projection | null>(null);
  const [loading, setLoading] = useState(false);

  const [expandedMonth, setExpandedMonth] = useState<string | null>(null);
  const [monthTx, setMonthTx] = useState<MonthTransaction[] | null>(null);
  const [monthTxLoading, setMonthTxLoading] = useState(false);

  const rangeRef = useRef({ from, to });
  rangeRef.current = { from, to };

  const run = async (opts?: { silent?: boolean }) => {
    const { from: f, to: t } = rangeRef.current;
    const [fy, fm] = f.split("-").map(Number);
    const [ty, tm] = t.split("-").map(Number);
    const qs = `year_from=${fy}&month_from=${fm}&year_to=${ty}&month_to=${tm}`;
    if (!opts?.silent) setLoading(true);
    try {
      const [summary, merchantsRes, accountsRes, heatmapRes] = await Promise.all([
        api.get(`/api/analytics/summary?${qs}`),
        api.get(`/api/analytics/merchants?${qs}&limit=10`),
        api.get(`/api/analytics/by-account?${qs}`),
        api.get(`/api/analytics/heatmap?${qs}`),
      ]);
      setData(summary);
      setMerchants(merchantsRes.merchants);
      setByAccount(accountsRes.accounts);
      setHeatmap(heatmapRes.weekdays);
    } finally {
      setLoading(false);
    }
  };

  // Carga inicial: antes el análisis no se calculaba hasta pulsar
  // "Analizar", así que la primera visita se quedaba vacía. Ahora se
  // calcula automáticamente con el rango por defecto (últimos 12 meses).
  useEffect(() => {
    run();
    api.get("/api/analytics/projection").then(setProjection).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Igual que en /transactions: si el usuario añade o edita un movimiento
  // (por ejemplo a mano) y vuelve a esta pestaña, recargamos el análisis
  // automáticamente para que refleje el cambio sin tener que pulsar
  // "Analizar" de nuevo.
  useEffect(() => {
    const reload = () => {
      run({ silent: true });
      if (expandedMonth) loadMonthTransactions(expandedMonth, { silent: true });
    };
    const onFocus = () => reload();
    const onVisibility = () => {
      if (document.visibilityState === "visible") reload();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expandedMonth]);

  const loadMonthTransactions = async (month: string, opts?: { silent?: boolean }) => {
    if (!opts?.silent) setMonthTxLoading(true);
    try {
      const qs = `date_from=${month}-01&date_to=${monthEnd(month)}&limit=1000`;
      const res = await api.get(`/api/transactions?${qs}`);
      setMonthTx(res.items);
    } finally {
      setMonthTxLoading(false);
    }
  };

  const toggleMonth = (month: string) => {
    if (expandedMonth === month) {
      setExpandedMonth(null);
      setMonthTx(null);
      return;
    }
    setExpandedMonth(month);
    setMonthTx(null);
    loadMonthTransactions(month);
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-display text-xl font-semibold">Análisis financiero</h1>
        <p className="text-sm text-muted">Consulta meses, años o cualquier periodo de hasta 10 años. Haz clic en un mes para ver sus movimientos.</p>
      </div>
      <div className="card p-4 flex flex-wrap gap-3 items-end">
        <div><label className="text-xs text-muted">Desde</label><input type="month" value={from} onChange={(e) => setFrom(e.target.value)} className="block input-field rounded-xl px-3 py-2 text-sm mt-1" /></div>
        <div><label className="text-xs text-muted">Hasta</label><input type="month" value={to} onChange={(e) => setTo(e.target.value)} className="block input-field rounded-xl px-3 py-2 text-sm mt-1" /></div>
        <button onClick={() => run()} className="btn-primary rounded-xl px-4 py-2 text-sm font-medium">Analizar</button>
      </div>
      {projection && (
        <div className="card p-4">
          <div className="text-sm font-medium mb-1">
            Proyección de {projection.month}
            {projection.is_current_month && (
              <span className="text-xs text-muted font-normal">
                {" "}— día {projection.days_elapsed} de {projection.days_total}
              </span>
            )}
          </div>
          <p className="text-xs text-muted mb-3">
            Estimación simple basada en el ritmo de gasto e ingreso hasta hoy, extrapolado al resto del mes.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div>
              <div className="text-xs text-muted">Ingresos hasta hoy</div>
              <div className="font-medium">{formatCurrency(projection.income_so_far)}</div>
            </div>
            <div>
              <div className="text-xs text-muted">Gastos hasta hoy</div>
              <div className="font-medium">{formatCurrency(projection.expenses_so_far)}</div>
            </div>
            <div>
              <div className="text-xs text-muted">Ahorro proyectado a fin de mes</div>
              <div className={`font-display text-lg font-semibold ${projection.projected_savings >= 0 ? "text-accent" : "text-negative"}`}>
                {formatCurrency(projection.projected_savings)}
              </div>
            </div>
          </div>
        </div>
      )}

      {loading && <p className="text-sm text-muted">Calculando...</p>}
      {data && <>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            ["Ingresos", data.totals.income],
            ["Gastos", data.totals.expenses],
            ["Ahorro", data.totals.savings],
            ["Inversión", data.totals.investment],
            ["Tasa ahorro", data.totals.savings_rate * 100],
          ].map(([label, value]) => (
            <div key={String(label)} className="card p-4"><div className="text-xs text-muted">{label}</div><div className="font-display text-lg font-semibold mt-1">{label === "Tasa ahorro" ? `${Number(value).toFixed(1)}%` : formatCurrency(Number(value))}</div></div>
          ))}
        </div>
        <div className="card p-4">
          <div className="text-sm font-medium mb-3">Evolución mensual</div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data.monthly}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="month" /><YAxis /><Tooltip formatter={(v: number) => formatCurrency(v)} /><Line type="monotone" dataKey="income" name="Ingresos" stroke="#1F5C46" /><Line type="monotone" dataKey="expenses" name="Gastos" stroke="#B3452F" /><Line type="monotone" dataKey="savings" name="Ahorro" stroke="#B8823E" /></LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-4">
          <div className="text-sm font-medium mb-1">Detalle por mes</div>
          <p className="text-xs text-muted mb-3">Haz clic en un mes para ver el listado de movimientos de ese periodo.</p>
          <div className="divide-y divide-border">
            {data.monthly.map((m) => (
              <div key={m.month}>
                <button
                  onClick={() => toggleMonth(m.month)}
                  className="w-full flex items-center justify-between py-2.5 text-sm hover:bg-bg rounded-lg px-2 -mx-2 transition-colors"
                >
                  <span className="font-medium flex items-center gap-2">
                    <span className={`transition-transform inline-block text-xs text-muted ${expandedMonth === m.month ? "rotate-90" : ""}`}>▶</span>
                    {m.month}
                  </span>
                  <span className="flex gap-4 text-xs">
                    <span className="text-accent">Ingr. {formatCurrency(m.income)}</span>
                    <span className="text-negative">Gast. {formatCurrency(m.expenses)}</span>
                    <span className={m.savings >= 0 ? "text-accent" : "text-negative"}>Ahorro {formatCurrency(m.savings)}</span>
                  </span>
                </button>
                {expandedMonth === m.month && (
                  <div className="pb-3 pl-6">
                    {monthTxLoading ? (
                      <p className="text-xs text-muted py-2">Cargando movimientos...</p>
                    ) : monthTx && monthTx.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-left text-muted border-b border-border">
                              <th className="py-1.5 pr-3">Fecha</th>
                              <th className="py-1.5 pr-3">Descripción</th>
                              <th className="py-1.5 pr-3">Entidad</th>
                              <th className="py-1.5 pr-3">Tipo</th>
                              <th className="py-1.5 pr-3 text-right">Importe</th>
                            </tr>
                          </thead>
                          <tbody>
                            {monthTx.map((t) => (
                              <tr key={t.id} className="border-b border-border last:border-0">
                                <td className="py-1.5 pr-3 text-muted whitespace-nowrap">{new Date(t.date).toLocaleDateString("es-ES")}</td>
                                <td className="py-1.5 pr-3 max-w-[240px] truncate">{t.description}</td>
                                <td className="py-1.5 pr-3 text-muted">{t.source}</td>
                                <td className="py-1.5 pr-3 text-muted">{t.type}</td>
                                <td className={`py-1.5 pr-3 text-right tabular-nums whitespace-nowrap ${t.amount < 0 ? "text-negative" : "text-accent"}`}>
                                  {formatCurrency(t.amount)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-xs text-muted py-2">Sin movimientos en este mes.</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div className="card p-4">
            <div className="text-sm font-medium mb-3">Ahorro por mes</div>
            <ResponsiveContainer width="100%" height={230}><BarChart data={data.monthly}><XAxis dataKey="month" /><YAxis /><Tooltip formatter={(v: number) => formatCurrency(v)} /><Bar dataKey="savings" name="Ahorro" fill="#1F5C46" /></BarChart></ResponsiveContainer>
          </div>
          <div className="card p-4">
            <div className="text-sm font-medium mb-3">Categorías de gasto</div>
            <div className="space-y-2">{data.top_categories.map((c) => <div key={c.category} className="flex justify-between text-sm"><span>{c.category}</span><span className="tabular-nums">{formatCurrency(c.amount)}</span></div>)}</div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div className="card p-4">
            <div className="text-sm font-medium mb-3">Top comercios</div>
            {merchants && merchants.length > 0 ? (
              <div className="space-y-2">
                {merchants.map((m) => (
                  <div key={m.merchant} className="flex justify-between items-baseline text-sm">
                    <div>
                      <div>{m.merchant}</div>
                      <div className="text-xs text-muted">
                        {m.transaction_count} {m.transaction_count === 1 ? "operación" : "operaciones"} · media {formatCurrency(m.average_amount)}
                      </div>
                    </div>
                    <span className="tabular-nums font-medium">{formatCurrency(m.total)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted">Sin datos suficientes en este periodo.</p>
            )}
          </div>

          <div className="card p-4">
            <div className="text-sm font-medium mb-3">Desglose por cuenta</div>
            {byAccount && byAccount.length > 0 ? (
              <div className="space-y-3">
                {byAccount.map((a) => (
                  <div key={a.account_id} className="text-sm">
                    <div className="flex justify-between">
                      <span className="font-medium">{a.account_name}</span>
                      <span className="text-xs text-muted">{a.transaction_count} mov.</span>
                    </div>
                    <div className="flex justify-between text-xs text-muted mt-0.5">
                      <span>Ingresos {formatCurrency(a.income)}</span>
                      <span>Gastos {formatCurrency(a.expenses)}</span>
                      <span className={a.savings >= 0 ? "text-accent" : "text-negative"}>
                        Ahorro {formatCurrency(a.savings)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted">Sin datos suficientes en este periodo.</p>
            )}
          </div>
        </div>

        {heatmap && (
          <div className="card p-4">
            <div className="text-sm font-medium mb-1">Gasto por día de la semana</div>
            <p className="text-xs text-muted mb-3">Ayuda a ver si gastas más entre semana o los fines de semana.</p>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={heatmap}>
                <XAxis dataKey="weekday" />
                <YAxis />
                <Tooltip
                  formatter={(v: number, name: string, entry: { payload?: WeekdayBucket }) =>
                    name === "Total" && entry?.payload
                      ? [`${formatCurrency(v)} (${entry.payload.transaction_count} mov.)`, "Total"]
                      : [formatCurrency(v), name]
                  }
                />
                <Bar dataKey="total" name="Total">
                  {heatmap.map((w, i) => (
                    <Cell key={i} fill={heatColor(w.total, Math.max(...heatmap.map((x) => x.total)))} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </>}
    </div>
  );
}
