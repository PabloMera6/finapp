import type { Metadata } from "next";
import "./globals.css";
import NavShell from "@/components/NavShell";

export const metadata: Metadata = {
  title: "Finanzas — Panel personal",
  description: "Análisis financiero personal privado",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <NavShell>{children}</NavShell>
      </body>
    </html>
  );
}
