"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

const INSTITUTIONS = [\n  { key: "bbva", label: "BBVA" },
  { key: "imagin", label: "imagin" },
  { key: "myinvestor", label: "MyInvestor" },
  { key: "trade_republic", label: "Trade Republic" },
];

type PreviewRow = {
  row_index: number; date: string | null; description: string | null;
  amount: string | null; detected_type: string | null; is_duplicate: boolean; error?: string;
};

type PreviewResponse = {
  detected_institution: string | null;
  chosen_institution: string;
  total_rows: number; new_rows: number; duplicate_rows: number; error_rows: number;
  sample: PreviewRow[]; import_token: string;
  existing_accounts: { id: string; account_name: string }[];
};

export default function ImportPage() {
  const router = useRouter();
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [manualInstitution, setManualInstitution] = useState<string>("");
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [accountChoice, setAccountChoice] = useState<string>("new");
  const [newAccountName, setNewAccountName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ imported: number; duplicates: number } | null>(null);

  const runPreview = useCallback(async (f: File, institution?: string) => {
    setLoading(true);
    setError(null);
    setPreview(null);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("file", f);
      const qs = institution ? `?institution=${institution}` : "";
      const res: PreviewResponse = await api.post(`/api/imports/preview${qs}`, formData);
      setPreview(res);
      setNewAccountName(`${res.chosen_institution} - cuenta principal`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al procesar el archivo");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleFile = (f: File) => {
    setFile(f);
    runPreview(f);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  };

  const handleConfirm = async () => {
    if (!preview) return;
    setLoading(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        import_token: preview.import_token,
        institution: preview.chosen_institution,
      };
      if (accountChoice === "new") {
        payload.new_account_name = newAccountName;
      } else {
        payload.account_id = accountChoice;
      }
      const res = await api.post("/api/imports/confirm", payload);
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al confirmar la importación");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="font-display text-xl font-semibold">Importar movimientos</h1>

      {!preview && !result && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`card p-10 text-center border-2 border-dashed transition-colors ${
            dragOver ? "border-accent bg-accentSoft/40" : "border-border"
          }`}
        >
          <p className="text-sm text-muted mb-3">Arrastra aquí tu archivo CSV, XLSX o PDF</p>
          <label className="inline-block btn-primary rounded-xl px-4 py-2 text-sm font-medium cursor-pointer">
            Seleccionar archivo
            <input
              type="file"
              accept=".csv,.xlsx,.xls,.pdf"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
            />
          </label>
          <p className="text-xs text-muted mt-6 leading-relaxed">
            Exporta tus movimientos desde BBVA, imagin, MyInvestor o Trade Republic. BBVA: Excel/CSV; Trade Republic: PDF.
            <br />No necesitamos tus contraseñas bancarias.
          </p>
        </div>
      )}

      {loading && <p className="text-sm text-muted">Procesando...</p>}
      {error && <p className="text-sm text-negative">{error}</p>}

      {preview && !result && (
        <div className="space-y-4">
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-xs text-muted">Entidad detectada</div>
                <div className="font-medium">{preview.detected_institution || "No detectada"}</div>
              </div>
              <select
                value={preview.chosen_institution}
                onChange={(e) => file && runPreview(file, e.target.value)}
                className="input-field rounded-xl px-3 py-1.5 text-sm"
              >
                {INSTITUTIONS.map((i) => (
                  <option key={i.key} value={i.key}>{i.label}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <div className="font-display text-lg font-semibold text-accent">{preview.new_rows}</div>
                <div className="text-xs text-muted">Nuevos</div>
              </div>
              <div>
                <div className="font-display text-lg font-semibold text-muted">{preview.duplicate_rows}</div>
                <div className="text-xs text-muted">Duplicados</div>
              </div>
              <div>
                <div className="font-display text-lg font-semibold text-negative">{preview.error_rows}</div>
                <div className="text-xs text-muted">Errores</div>
              </div>
            </div>
          </div>

          <div className="card p-4">
            <div className="text-xs text-muted font-medium mb-2">Cuenta destino</div>
            <select
              value={accountChoice}
              onChange={(e) => setAccountChoice(e.target.value)}
              className="w-full input-field rounded-xl px-3 py-2 text-sm mb-2"
            >
              <option value="new">Crear nueva cuenta</option>
              {preview.existing_accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.account_name}</option>
              ))}
            </select>
            {accountChoice === "new" && (
              <input
                value={newAccountName}
                onChange={(e) => setNewAccountName(e.target.value)}
                className="w-full input-field rounded-xl px-3 py-2 text-sm"
                placeholder="Nombre de la cuenta"
              />
            )}
          </div>

          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted border-b border-border">
                  <th className="px-3 py-2">Fecha</th>
                  <th className="px-3 py-2">Concepto</th>
                  <th className="px-3 py-2">Importe</th>
                  <th className="px-3 py-2">Estado</th>
                </tr>
              </thead>
              <tbody>
                {preview.sample.slice(0, 15).map((row, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="px-3 py-2 text-muted">{row.date || "—"}</td>
                    <td className="px-3 py-2">{row.error ? <span className="text-negative">{row.error}</span> : row.description}</td>
                    <td className="px-3 py-2 tabular-nums">{row.amount || "—"}</td>
                    <td className="px-3 py-2">
                      {row.error ? null : row.is_duplicate ? (
                        <span className="text-[11px] pill-negative px-2 py-0.5 rounded-full">Duplicado</span>
                      ) : (
                        <span className="text-[11px] pill-positive px-2 py-0.5 rounded-full">Nuevo</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => { setPreview(null); setFile(null); }}
              className="flex-1 btn-secondary rounded-xl py-2.5 text-sm font-medium"
            >
              Cancelar
            </button>
            <button
              onClick={handleConfirm}
              disabled={loading || preview.new_rows === 0}
              className="flex-1 btn-primary rounded-xl py-2.5 text-sm font-medium disabled:opacity-50"
            >
              Confirmar importación
            </button>
          </div>
        </div>
      )}

      {result && (
        <div className="card p-6 text-center">
          <div className="font-display text-lg font-semibold mb-2">Importación completada</div>
          <p className="text-sm text-muted mb-4">
            {result.imported} movimientos nuevos importados · {result.duplicates} duplicados descartados
          </p>
          <button onClick={() => router.push("/")} className="btn-primary rounded-xl px-4 py-2 text-sm font-medium">
            Ir al resumen
          </button>
        </div>
      )}
    </div>
  );
}
