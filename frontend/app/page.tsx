"use client";

import { useEffect, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";
import { api, formatCurrency } from "@/lib/api";
import MetricCard from "@/components/MetricCard";

const COLORS = ["#1F5C46", "#B8823E", "#B3452F", "#4C7A9E", "#8B5FA3", "#63705F", "#D98A4C", "#3E8E7E"];

type DashboardData = {
  month: string;
  income: number;
  expenses: number;
  savings: number;
  savings_rate: number;
  investment: number;
  prev_month: { income: number; expenses: number; savings: number; investment: number };
  category_breakdown: { category: string; amount: number; percentage: number }[];
};

type TimeseriesPoint = {
  month: string; income: number; expenses: number; savings: number; investment: number;
};

type Insight = { text: string; detail: Record<string, unknown> };

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [series, setSeries] = useState<TimeseriesPoint[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [bizumsPending, setBizumsPending] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [hasData, setHasData] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/api/dashboard"),
      api.get("/api/dashboard/timeseries?months=12"),
      api.get("/api/insights"),
      api.get("/api/bizums/unidentified"),
    ])
      .then(([dash, ts, ins, bizums]) => {
        setData(dash);
        setSeries(ts);
        setInsights(ins);
        setBizumsPending(bizums.length);
        setHasData(dash.income > 0 || dash.expenses > 0 || ts.some((p: TimeseriesPoint) => p.income || p.expenses));
      })
      .finally(() => setLoading(false));
  }, []);

  // Igual que en /transactions y /analytics: sin esto, si el usuario añadía
  // un movimiento manual y volvía al resumen, seguía viendo los datos
  // antiguos porque nada disparaba una nueva carga. Recargamos en segundo
  // plano (sin mostrar el loader) al recuperar el foco o la visibilidad.
  useEffect(() => {
    const reload = () => {
      Promise.all([
        api.get("/api/dashboard"),
        api.get("/api/dashboard/timeseries?months=12"),
        api.get("/api/insights"),
        api.get("/api/bizums/unidentified"),
      ]).then(([dash, ts, ins, bizums]) => {
        setData(dash);
        setSeries(ts);
        setInsights(ins);
        setBizumsPending(bizums.length);
        setHasData(dash.income > 0 || dash.expenses > 0 || ts.some((p: TimeseriesPoint) => p.income || p.expenses));
      }).catch(() => {});
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
  }, []);

  if (loading) {
    return <div className="animate-pulse text-muted text-sm">Cargando resumen financiero...</div>;
  }

  if (!hasData) {
    return (
      <div className="card p-10 text-center max-w-md mx-auto mt-10">
        <div className="font-display text-lg font-semibold mb-2">Aún no has importado movimientos</div>
        <p className="text-sm text-muted mb-6">
          Puedes exportar tus movimientos desde imagin, MyInvestor o Trade Republic.
          No necesitamos tus contraseñas bancarias.
        </p>
        <a href="/import" className="inline-block btn-primary rounded-xl px-4 py-2 text-sm font-medium">
          Importar movimientos
        </a>
      </div>
    );
  }

  if (!data) return null;

  const savingsDelta = data.prev_month.savings !== 0 ? (data.savings - data.prev_month.savings) / Math.abs(data.prev_month.savings) : null;
  const incomeDelta = data.prev_month.income !== 0 ? (data.income - data.prev_month.income) / data.prev_month.income : null;
  const expensesDelta = data.prev_month.expenses !== 0 ? (data.expenses - data.prev_month.expenses) / data.prev_month.expenses : null;
  const investmentDelta = data.prev_month.investment !== 0 ? (data.investment - data.prev_month.investment) / data.prev_month.investment : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-xl font-semibold">Resumen financiero</h1>
        <p className="text-sm text-muted">{data.month}</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        <MetricCard label="Ingresos" value={data.income} delta={incomeDelta} tone="positive" />
        <MetricCard label="Gastos" value={data.expenses} delta={expensesDelta} tone="negative" />
        <MetricCard label="Ahorro" value={data.savings} delta={savingsDelta} />
        <MetricCard label="Inversión" value={data.investment} delta={investmentDelta} />
      </div>

      <div className="card p-4 md:p-5">
        <div className="text-xs text-muted font-medium mb-1">Tasa de ahorro</div>
        <div className="font-display text-xl font-semibold">{(data.savings_rate * 100).toFixed(1)}%</div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card p-4 md:p-5">
          <div className="text-sm font-medium mb-3">Ingresos vs. gastos (12 meses)</div>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={series}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E4E1D5" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => formatCurrency(v)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="income" name="Ingresos" stroke="#1F5C46" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="expenses" name="Gastos" stroke="#B3452F" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-4 md:p-5">
          <div className="text-sm font-medium mb-3">Distribución de gastos por categoría</div>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={data.category_breakdown}
                dataKey="amount"
                nameKey="category"
                innerRadius={55}
                outerRadius={90}
                paddingAngle={2}
              >
                {data.category_breakdown.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) => formatCurrency(v)} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card p-4 md:p-5">
        <div className="text-sm font-medium mb-3">Tasa de ahorro mensual</div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={series.map((s) => ({ month: s.month, rate: s.income > 0 ? (s.savings / s.income) * 100 : 0 }))}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E4E1D5" />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} unit="%" />
            <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
            <Bar dataKey="rate" name="Tasa de ahorro" fill="#1F5C46" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {insights.length > 0 && (
        <div className="card p-4 md:p-5">
          <div className="text-sm font-medium mb-3">Insights</div>
          <ul className="space-y-2">
            {insights.map((ins, i) => (
              <li key={i} className="text-sm text-ink bg-bg rounded-lg px-3 py-2 border border-border">
                {ins.text}
              </li>
            ))}
          </ul>
        </div>
      )}

      {bizumsPending > 0 && (
        <a href="/bizums" className="card p-4 md:p-5 flex items-center justify-between hover:border-accent transition-colors">
          <div>
            <div className="text-sm font-medium">Bizums pendientes de identificar</div>
            <div className="text-xs text-muted">Tienes {bizumsPending} Bizum(s) sin destinatario o categoría confirmada</div>
          </div>
          <span className="text-accent text-sm font-medium">Revisar →</span>
        </a>
      )}
    </div>
  );
}
