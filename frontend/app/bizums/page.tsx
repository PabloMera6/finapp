"use client";

import { useEffect, useState } from "react";
import { api, formatCurrency } from "@/lib/api";

type Bizum = {
  id: string; date: string; amount: number; description: string;
  bizum_direction: string | null; category_id: string | null;
};
type CategoryOpt = { id: string; name: string };

const BIZUM_CATEGORY_OPTIONS = [
  "Restaurantes", "Ocio", "Transporte", "Vivienda", "Alimentación", "Viajes", "Compras", "Otros",
];

export default function BizumsPage() {
  const [items, setItems] = useState<Bizum[]>([]);
  const [categories, setCategories] = useState<CategoryOpt[]>([]);
  const [drafts, setDrafts] = useState<Record<string, { recipient: string; categoryId: string; saved: boolean }>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.get("/api/bizums/unidentified"), api.get("/api/categories")])
      .then(([bizums, cats]) => {
        setItems(bizums);
        setCategories(cats.filter((c: any) => BIZUM_CATEGORY_OPTIONS.includes(c.name)));
        const initial: Record<string, { recipient: string; categoryId: string; saved: boolean }> = {};
        bizums.forEach((b: Bizum) => {
          initial[b.id] = { recipient: "", categoryId: b.category_id || "", saved: false };
        });
        setDrafts(initial);
      })
      .finally(() => setLoading(false));
  }, []);

  const updateDraft = (id: string, field: "recipient" | "categoryId", value: string) => {
    setDrafts((prev) => ({ ...prev, [id]: { ...prev[id], [field]: value, saved: false } }));
  };

  const save = async (id: string) => {
    const draft = drafts[id];
    await api.patch(`/api/bizums/${id}`, {
      bizum_recipient: draft.recipient || undefined,
      category_id: draft.categoryId || undefined,
      remember_contact: !!draft.recipient,
    });
    setDrafts((prev) => ({ ...prev, [id]: { ...prev[id], saved: true } }));
  };

  if (loading) return <p className="text-sm text-muted">Cargando...</p>;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-xl font-semibold">Bizums pendientes de identificar</h1>
        <p className="text-sm text-muted mt-1">
          El destinatario y la categoría son independientes: puedes guardar solo una de las dos.
        </p>
      </div>

      {items.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">No tienes Bizums pendientes de identificar 🎉</div>
      ) : (
        <div className="space-y-3">
          {items.map((b) => {
            const draft = drafts[b.id] || { recipient: "", categoryId: "", saved: false };
            return (
              <div key={b.id} className="card p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <div className="text-sm font-medium">{new Date(b.date).toLocaleDateString("es-ES")} — {b.description}</div>
                    <div className="text-xs text-muted">Destinatario: no identificado</div>
                  </div>
                  <div className={`font-numeric font-semibold ${b.amount < 0 ? "text-negative" : "text-accent"}`}>
                    {formatCurrency(b.amount)}
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <input
                    placeholder="Destinatario (opcional)"
                    value={draft.recipient}
                    onChange={(e) => updateDraft(b.id, "recipient", e.target.value)}
                    className="input-field rounded-xl px-3 py-1.5 text-sm"
                  />
                  <select
                    value={draft.categoryId}
                    onChange={(e) => updateDraft(b.id, "categoryId", e.target.value)}
                    className="input-field rounded-xl px-3 py-1.5 text-sm"
                  >
                    <option value="">Tipo de gasto (opcional)</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => save(b.id)}
                    className="btn-primary rounded-xl px-3 py-1.5 text-sm font-medium"
                  >
                    {draft.saved ? "Guardado ✓" : "Guardar"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
