"use client";

import { useEffect, useRef, useState } from "react";
import { api, formatCurrency } from "@/lib/api";

type Transaction = {
  id: string; date: string; amount: number; description: string; type: string;
  category_id: string | null; is_internal_transfer: boolean; is_bizum: boolean;
  bizum_recipient: string | null; source: string;
};

type CategoryOpt = { id: string; name: string; subcategories: { id: string; name: string }[] };
type AccountOpt = { id: string; account_name: string; institution: string };

const PAGE_SIZE = 100;

export default function TransactionsPage() {
  const [items, setItems] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [categories, setCategories] = useState<CategoryOpt[]>([]);
  const [accounts, setAccounts] = useState<AccountOpt[]>([]);
  const [institutions, setInstitutions] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [institutionFilter, setInstitutionFilter] = useState("");
  const [amountMin, setAmountMin] = useState("");
  const [amountMax, setAmountMax] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [newTx, setNewTx] = useState({ account_id: "", date: new Date().toISOString().slice(0, 10), amount: "", description: "", type: "EXPENSE" });
  const [loading, setLoading] = useState(true);

  // Guardamos los filtros actuales en un ref para poder recargar (p.ej. al
  // volver a la pestaña) sin depender de closures obsoletos del useEffect.
  const filtersRef = useRef({ search, institutionFilter, amountMin, amountMax, page });
  filtersRef.current = { search, institutionFilter, amountMin, amountMax, page };

  const buildQuery = (opts?: { page?: number }) => {
    const f = filtersRef.current;
    const p = opts?.page ?? f.page;
    const params = new URLSearchParams();
    if (f.search) params.set("search", f.search);
    if (f.institutionFilter) params.set("institution", f.institutionFilter);
    if (f.amountMin) params.set("amount_min", f.amountMin);
    if (f.amountMax) params.set("amount_max", f.amountMax);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(p * PAGE_SIZE));
    return params.toString();
  };

  const load = (opts?: { page?: number; silent?: boolean }) => {
    if (!opts?.silent) setLoading(true);
    const qs = buildQuery(opts);
    const requests: Promise<unknown>[] = [api.get(`/api/transactions?${qs}`)];
    // Solo hace falta traer categorías/cuentas/entidades una vez; en
    // recargas silenciosas (p.ej. al volver a la pestaña) nos ahorramos
    // esas llamadas.
    if (!opts?.silent) {
      requests.push(api.get("/api/categories"), api.get("/api/accounts"), api.get("/api/transactions/institutions"));
    }
    Promise.all(requests)
      .then((results) => {
        const tx = results[0] as { items: Transaction[]; total: number };
        setItems(tx.items);
        setTotal(tx.total);
        if (!opts?.silent) {
          const [, cats, accs, insts] = results as [unknown, CategoryOpt[], AccountOpt[], { institutions: string[] }];
          setCategories(cats);
          setAccounts(accs);
          setInstitutions(insts.institutions);
          if (!newTx.account_id && accs.length) setNewTx((v) => ({ ...v, account_id: accs[0].id }));
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // El análisis y los listados solo se cargaban una vez al entrar en la
  // página. Si el usuario añadía un movimiento manual en otra pestaña, o
  // volvía a esta pestaña tras un rato, los datos se quedaban desactualizados
  // porque nada disparaba una nueva carga. Recargamos automáticamente al
  // recuperar el foco o la visibilidad de la pestaña.
  useEffect(() => {
    const onFocus = () => load({ page: filtersRef.current.page, silent: true });
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        load({ page: filtersRef.current.page, silent: true });
      }
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runFilters = () => {
    setPage(0);
    load({ page: 0 });
  };

  const goToPage = (p: number) => {
    setPage(p);
    load({ page: p });
  };

  const handleCategoryChange = async (txId: string, categoryId: string) => {
    setItems((prev) => prev.map((t) => (t.id === txId ? { ...t, category_id: categoryId } : t)));
    await api.patch(`/api/transactions/${txId}`, { category_id: categoryId, remember_rule: true });
  };

  const handleDelete = async (txId: string) => {
    if (!window.confirm("¿Eliminar este movimiento?")) return;
    await api.del(`/api/transactions/${txId}`);
    load({ page, silent: true });
  };

  const handleCreate = async () => {
    if (!newTx.account_id || !newTx.amount || !newTx.description) return;
    await api.post("/api/transactions", {
      ...newTx,
      amount: Number(newTx.amount),
      date: `${newTx.date}T12:00:00`,
    });
    setShowAdd(false);
    setNewTx((v) => ({ ...v, amount: "", description: "" }));
    setPage(0);
    load({ page: 0 });
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="font-display text-xl font-semibold">Movimientos</h1>
        <div className="flex gap-2">
          <button onClick={() => setShowAdd(true)} className="bg-accent text-white rounded-lg px-3 py-1.5 text-sm font-medium">+ Añadir</button>
        </div>
      </div>

      <div className="card p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="text-xs text-muted block mb-1">Buscar</label>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runFilters()}
            placeholder="Descripción..."
            className="border border-border rounded-lg px-3 py-1.5 text-sm w-48"
          />
        </div>
        <div>
          <label className="text-xs text-muted block mb-1">Entidad</label>
          <select
            value={institutionFilter}
            onChange={(e) => setInstitutionFilter(e.target.value)}
            className="border border-border rounded-lg px-3 py-1.5 text-sm"
          >
            <option value="">Todas</option>
            {institutions.map((inst) => (
              <option key={inst} value={inst}>{inst}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-muted block mb-1">Importe mín. (€)</label>
          <input
            type="number"
            step="0.01"
            value={amountMin}
            onChange={(e) => setAmountMin(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runFilters()}
            placeholder="0"
            className="border border-border rounded-lg px-3 py-1.5 text-sm w-28"
          />
        </div>
        <div>
          <label className="text-xs text-muted block mb-1">Importe máx. (€)</label>
          <input
            type="number"
            step="0.01"
            value={amountMax}
            onChange={(e) => setAmountMax(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runFilters()}
            placeholder="9999"
            className="border border-border rounded-lg px-3 py-1.5 text-sm w-28"
          />
        </div>
        <button onClick={runFilters} className="border border-border rounded-lg px-3 py-1.5 text-sm">Filtrar</button>
        {(search || institutionFilter || amountMin || amountMax) && (
          <button
            onClick={() => {
              setSearch(""); setInstitutionFilter(""); setAmountMin(""); setAmountMax("");
              filtersRef.current = { search: "", institutionFilter: "", amountMin: "", amountMax: "", page: 0 };
              setPage(0);
              load({ page: 0 });
            }}
            className="text-xs text-muted underline"
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {showAdd && (
        <div className="card p-4 space-y-3">
          <div className="text-sm font-medium">Nuevo movimiento</div>
          <div className="grid md:grid-cols-2 gap-3">
            <select value={newTx.account_id} onChange={(e) => setNewTx({ ...newTx, account_id: e.target.value })} className="border border-border rounded-lg px-3 py-2 text-sm">
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.account_name}</option>)}
            </select>
            <input type="date" value={newTx.date} onChange={(e) => setNewTx({ ...newTx, date: e.target.value })} className="border border-border rounded-lg px-3 py-2 text-sm" />
            <input type="number" step="0.01" value={newTx.amount} onChange={(e) => setNewTx({ ...newTx, amount: e.target.value })} placeholder="Importe" className="border border-border rounded-lg px-3 py-2 text-sm" />
            <select value={newTx.type} onChange={(e) => setNewTx({ ...newTx, type: e.target.value })} className="border border-border rounded-lg px-3 py-2 text-sm">
              <option value="EXPENSE">Gasto</option><option value="INCOME">Ingreso</option><option value="TRANSFER">Transferencia</option><option value="INVESTMENT_BUY">Compra inversión</option><option value="INVESTMENT_SELL">Venta inversión</option><option value="DIVIDEND">Dividendo</option><option value="INTEREST">Intereses</option><option value="FEE">Comisión</option>
            </select>
          </div>
          <input value={newTx.description} onChange={(e) => setNewTx({ ...newTx, description: e.target.value })} placeholder="Descripción" className="w-full border border-border rounded-lg px-3 py-2 text-sm" />
          <div className="flex gap-2 justify-end"><button onClick={() => setShowAdd(false)} className="border border-border rounded-lg px-3 py-2 text-sm">Cancelar</button><button onClick={handleCreate} className="bg-accent text-white rounded-lg px-3 py-2 text-sm">Guardar</button></div>
        </div>
      )}
      {loading ? (
        <p className="text-sm text-muted">Cargando...</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted">No hay movimientos que coincidan.</p>
      ) : (
        <>
          <div className="text-xs text-muted">
            {total} {total === 1 ? "movimiento" : "movimientos"} en total
            {totalPages > 1 && ` · página ${page + 1} de ${totalPages}`}
          </div>
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted border-b border-border">
                  <th className="px-3 py-2">Fecha</th>
                  <th className="px-3 py-2">Descripción</th>
                  <th className="px-3 py-2">Entidad</th>
                  <th className="px-3 py-2">Importe</th>
                  <th className="px-3 py-2">Categoría</th>
                  <th className="px-3 py-2">Estado</th><th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((t) => (
                  <tr key={t.id} className="border-b border-border last:border-0">
                    <td className="px-3 py-2 text-muted whitespace-nowrap">{new Date(t.date).toLocaleDateString("es-ES")}</td>
                    <td className="px-3 py-2 max-w-[220px] truncate">{t.description}</td>
                    <td className="px-3 py-2 text-xs text-muted">{t.source}</td>
                    <td className={`px-3 py-2 tabular-nums whitespace-nowrap ${t.amount < 0 ? "text-negative" : "text-accent"}`}>
                      {formatCurrency(t.amount)}
                    </td>
                    <td className="px-3 py-2">
                      <select
                        value={t.category_id || ""}
                        onChange={(e) => handleCategoryChange(t.id, e.target.value)}
                        className="border border-border rounded-md px-2 py-1 text-xs bg-transparent"
                      >
                        <option value="">Sin categorizar</option>
                        {categories.map((c) => (
                          <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      {t.is_internal_transfer && <span className="text-[11px] pill-positive px-2 py-0.5 rounded-full mr-1">Transferencia</span>}
                      {t.is_bizum && <span className="text-[11px] px-2 py-0.5 rounded-full bg-bg border border-border">Bizum</span>}
                    </td>
                    <td className="px-3 py-2 text-right"><button onClick={() => handleDelete(t.id)} className="text-negative text-xs">Eliminar</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => goToPage(page - 1)}
                className="border border-border rounded-lg px-3 py-1.5 text-sm disabled:opacity-40"
              >
                ← Anterior
              </button>
              <span className="text-xs text-muted px-2">{page + 1} / {totalPages}</span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => goToPage(page + 1)}
                className="border border-border rounded-lg px-3 py-1.5 text-sm disabled:opacity-40"
              >
                Siguiente →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
