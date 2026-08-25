"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/", label: "Resumen", icon: "◆" },
  { href: "/transactions", label: "Movimientos", icon: "≡" },
  { href: "/import", label: "Importar", icon: "↑" },
  { href: "/bizums", label: "Bizums", icon: "B" },
  { href: "/accounts", label: "Cuentas", icon: "●" },
  { href: "/compare", label: "Comparar", icon: "⇄" },
  { href: "/analytics", label: "Análisis", icon: "◔" },
];

export default function NavShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [verifying, setVerifying] = useState(true);

  useEffect(() => {
    let cancelled = false;

    setVerifying(true);

    api
      .get("/api/auth/me")
      .then((d) => {
        if (!cancelled) setEmail(d.email);
      })
      .catch(() => {
        if (!cancelled) setEmail(null);
      })
      .finally(() => {
        if (!cancelled) {
          setChecked(true);
          setVerifying(false);
        }
      });

    return () => {
      cancelled = true;
    };
    // Se revalida en cada cambio de ruta (p. ej. justo tras el login, cuando
    // la cookie de sesión acaba de establecerse). "verifying" evita que,
    // mientras esa revalidación está en curso, se use el resultado
    // desactualizado de la comprobación anterior para redirigir a /login.
  }, [pathname]);

  if (pathname === "/login") {
    return <div className="min-h-screen bg-bg">{children}</div>;
  }

  if (!checked) {
    return <div className="min-h-screen bg-bg" />;
  }

  if (!email) {
    if (verifying) {
      // Todavía estamos confirmando la sesión para esta ruta (p. ej.
      // justo después de iniciar sesión). Esperamos en vez de redirigir
      // con datos obsoletos, que era la causa del "doble login".
      return <div className="min-h-screen bg-bg" />;
    }

    if (typeof window !== "undefined") router.replace("/login");
    return <div className="min-h-screen bg-bg" />;
  }

  const handleLogout = async () => {
    await api.post("/api/auth/logout");
    router.replace("/login");
  };

  return (
    <div className="min-h-screen bg-bg text-ink flex">
      {/* Sidebar desktop */}
      <aside className="hidden md:flex md:flex-col w-64 border-r border-border bg-surfaceAlt/60 px-5 py-6 gap-1">
        <div className="flex items-center gap-2.5 mb-8 px-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accentDeep flex items-center justify-center shadow-pop">
            <span className="text-white text-sm font-display font-bold">F</span>
          </div>
          <div className="font-display text-lg font-semibold tracking-tight">Finanzas</div>
        </div>
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`relative px-3 py-2.5 rounded-xl text-sm font-medium flex items-center gap-3 transition-colors ${
                active ? "bg-accentSoft text-accentDeep" : "text-muted hover:bg-surface hover:text-ink"
              }`}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-full bg-accent" />
              )}
              <span className="w-4 text-center">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
        <div className="mt-auto px-2 pt-4 border-t border-border">
          <div className="text-xs text-muted mb-2 truncate">{email}</div>
          <button onClick={handleLogout} className="text-xs text-negative font-semibold hover:underline">
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="flex-1 pb-24 md:pb-0">
        <div className="max-w-5xl mx-auto px-4 md:px-8 py-6 md:py-8">{children}</div>
      </main>

      {/* Bottom nav mobile */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-surface/95 backdrop-blur border-t border-border flex justify-around py-2 z-20 shadow-cardHover">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center gap-0.5 text-[10px] px-2 py-1 rounded-lg transition-colors ${
                active ? "text-accent" : "text-muted"
              }`}
            >
              <span className={`text-base ${active ? "scale-110" : ""} transition-transform`}>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
