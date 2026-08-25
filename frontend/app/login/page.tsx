"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.post("/api/auth/login", { email, password });
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al iniciar sesión");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-accent to-accentDeep flex items-center justify-center shadow-pop mx-auto mb-4">
            <span className="text-white text-lg font-display font-bold">F</span>
          </div>
          <div className="font-display text-2xl font-semibold text-ink tracking-tight">Finanzas</div>
          <p className="text-sm text-muted mt-1">Tu análisis financiero personal, privado</p>
        </div>

        <form onSubmit={handleSubmit} className="card p-6 space-y-4">
          <div>
            <label className="text-xs font-medium text-muted">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field mt-1 w-full rounded-xl px-3 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted">Contraseña</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field mt-1 w-full rounded-xl px-3 py-2.5 text-sm"
            />
          </div>

          {error && <p className="text-xs text-negative font-medium">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full rounded-xl py-2.5 text-sm font-semibold disabled:opacity-60"
          >
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>

        <p className="text-xs text-muted text-center mt-6 leading-relaxed">
          No necesitamos tus contraseñas bancarias.
          <br />
          Solo utilizamos los archivos que tú exportas.
        </p>
      </div>
    </div>
  );
}
