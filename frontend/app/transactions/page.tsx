"use client";

import { useEffect, useState } from "react";
import { api, formatCurrency } from "@/lib/api";

type Transaction = {
  id: string; date: string; amount: number; description: string; type: string;
  category_id: string | null; is_internal_transfer: boolean; is_bizum: boolean;
  bizum_recipient: string | null; source: string;
};

type CategoryOpt = { id: string; name: string; subcategories: { id: string; name: string }[] };
type AccountOpt = { id: string; account_name: string; institution: string };

export default function TransactionsPage() {
  const [items, setItems] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<CategoryOpt[]>([]);
  const [accounts, setAccounts] = useState<AccountOpt[]>([]);
  const [search, setSearch] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [newTx, setNewTx] = useState({ account_id: "", date: new Date().toISOString().slice(0, 10), amount: "", description: "", type: "EXPENSE" });
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    const qs = search ? `?search=${encodeURIComponent(search)}` : "";
    Promise.all([api.get(`/api/transactions${qs}`), api.get("/api/categories"), api.get("/api/accounts")])
      .then(([tx, cats, accs]) => {
        setItems(tx.items);
        setCategories(cats);
        setAccounts(accs);
        if (!newTx.account_id && accs.length) setNewTx((v) => ({ ...v, account_id: accs[0].id }));
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCategoryChange = async (txId: string, categoryId: string) => {
    setItems((prev) => prev.map((t) => (t.id === txId ? { ...t, category_id: categoryId } : t)));
    await api.patch(`/api/transactions/${txId}`, { category_id: categoryId, remember_rule: true });
  };

  const handleDelete = async (txId: string) => {
    if (!window.confirm("¿Eliminar este movimiento?")) return;
    await api.del(`/api/transactions/${txId}`);
    setItems((prev) => prev.filter((t) => t.id !== txId));
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
    load();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="font-display text-xl font-semibold">Movimientos</h1>
        <div className="flex gap-2">
          <button onClick={() => setShowAdd(true)} className="bg-accent text-white rounded-lg px-3 py-1.5 text-sm font-medium">+ Añadir</button>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            placeholder="Buscar..."
            className="border border-border rounded-lg px-3 py-1.5 text-sm w-48"
          />
          <button onClick={load} className="border border-border rounded-lg px-3 py-1.5 text-sm">Buscar</button>
        </div>
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
      )}
    </div>
  );
}
