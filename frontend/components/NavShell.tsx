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

  useEffect(() => {
    api
      .get("/api/auth/me")
      .then((d) => setEmail(d.email))
      .catch(() => setEmail(null))
      .finally(() => setChecked(true));
  }, [pathname]);

  if (pathname === "/login") {
    return <div className="min-h-screen bg-bg">{children}</div>;
  }

  if (!checked) {
    return <div className="min-h-screen bg-bg" />;
  }

  if (!email) {
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
      <aside className="hidden md:flex md:flex-col w-60 border-r border-border px-5 py-6 gap-1">
        <div className="font-display text-lg font-semibold mb-6 px-2">Finanzas</div>
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-3 ${
              pathname === item.href ? "bg-accentSoft text-accent" : "text-muted hover:bg-surface"
            }`}
          >
            <span className="w-4 text-center">{item.icon}</span>
            {item.label}
          </Link>
        ))}
        <div className="mt-auto px-2 pt-4 border-t border-border">
          <div className="text-xs text-muted mb-2 truncate">{email}</div>
          <button onClick={handleLogout} className="text-xs text-negative font-medium">
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="flex-1 pb-20 md:pb-0">
        <div className="max-w-5xl mx-auto px-4 md:px-8 py-6 md:py-8">{children}</div>
      </main>

      {/* Bottom nav mobile */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-surface border-t border-border flex justify-around py-2 z-20">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`flex flex-col items-center text-[10px] px-2 py-1 ${
              pathname === item.href ? "text-accent" : "text-muted"
            }`}
          >
            <span className="text-base">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
