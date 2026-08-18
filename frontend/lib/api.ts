const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res.text();
}

export const api = {
  get: (path: string) => request(path),
  post: (path: string, body?: unknown) =>
    request(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body) }),
  patch: (path: string, body?: unknown) => request(path, { method: "PATCH", body: JSON.stringify(body) }),
  del: (path: string) => request(path, { method: "DELETE" }),
};

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(amount);
}

export function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}
