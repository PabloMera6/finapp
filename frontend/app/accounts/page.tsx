"use client";

import { useEffect, useState } from "react";
import { api, formatCurrency } from "@/lib/api";

type Acc = {
  id: string;
  institution: string;
  account_name: string;
  currency: string;
  transaction_count: number;
  calculated_balance: number | null;
  last_import_at: string | null;
};

const INSTITUTION_LABEL: Record<string, string> = {
  imagin: "imagin",
  myinvestor: "MyInvestor",
  trade_republic: "Trade Republic",
};

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Acc[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingAccountTransactions, setDeletingAccountTransactions] =
    useState<string | null>(null);
  const [deletingAccount, setDeletingAccount] = useState<string | null>(null);

  useEffect(() => {
    api
      .get("/api/accounts")
      .then(setAccounts)
      .finally(() => setLoading(false));
  }, []);

  async function deleteAccountTransactions(
  accountId: string,
  accountName: string,
  transactionCount: number,
) {
  if (transactionCount === 0) {
    return;
  }

  const confirmed = window.confirm(
    `¿Seguro que quieres borrar TODOS los movimientos de "${accountName}"?\n\n` +
      `Se eliminarán ${transactionCount} movimientos y sus registros de importación.\n\n` +
      `La cuenta NO se eliminará.\n\n` +
      `Esta acción no se puede deshacer.`,
  );

  if (!confirmed) {
    return;
  }

  try {
    setDeletingAccountTransactions(accountId);

    const result = await api.del(
      `/api/accounts/${accountId}/transactions`,
    );

    const deletedCount = result?.deleted_count ?? transactionCount;

    setAccounts((current) =>
      current.map((account) =>
        account.id === accountId
          ? {
              ...account,
              transaction_count: 0,
              calculated_balance: null,
              last_import_at: null,
            }
          : account,
      ),
    );

    window.alert(
      `Se han eliminado ${deletedCount} movimientos de "${accountName}".`,
    );
  } catch (error) {
    console.error("Error eliminando movimientos:", error);

    window.alert(
      "No se han podido eliminar los movimientos. " +
        "Comprueba que el servidor está funcionando e inténtalo de nuevo.",
    );
  } finally {
    setDeletingAccountTransactions(null);
  }
}

  async function deleteAccount(accountId: string, accountName: string, transactionCount: number) {
    const confirmed = window.confirm(
      `¿Seguro que quieres eliminar la cuenta "${accountName}" por completo?\n\n` +
        (transactionCount > 0
          ? `Se eliminarán también sus ${transactionCount} movimientos y registros de importación.\n\n`
          : "") +
        `Esta acción no se puede deshacer.`,
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingAccount(accountId);
      await api.del(`/api/accounts/${accountId}`);
      setAccounts((current) => current.filter((account) => account.id !== accountId));
      window.alert(`La cuenta "${accountName}" se ha eliminado.`);
    } catch (error) {
      console.error("Error eliminando la cuenta:", error);
      window.alert(
        "No se ha podido eliminar la cuenta. Comprueba que el servidor está funcionando e inténtalo de nuevo.",
      );
    } finally {
      setDeletingAccount(null);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted">Cargando...</p>;
  }

  return (
    <div className="space-y-4">
      <h1 className="font-display text-xl font-semibold">Cuentas</h1>

      {accounts.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          Aún no has importado ninguna cuenta.{" "}
          <a
            href="/import"
            className="text-accent font-medium"
          >
            Importar ahora
          </a>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4">
          {accounts.map((a) => {
            const isDeleting = deletingAccountTransactions === a.id;
            const isDeletingAccount = deletingAccount === a.id;
            const anyActionInFlight = isDeleting || isDeletingAccount;

            return (
              <div
                key={a.id}
                className="card p-4"
              >
                <div className="text-xs text-muted">
                  {INSTITUTION_LABEL[a.institution] || a.institution}
                </div>

                <div className="font-display font-semibold text-lg mt-1">
                  {a.account_name}
                </div>

                <div className="mt-3 text-sm">
                  <span className="text-muted">
                    Saldo calculado:{" "}
                  </span>

                  <span className="font-medium">
                    {a.calculated_balance !== null
                      ? formatCurrency(a.calculated_balance)
                      : "—"}
                  </span>
                </div>

                <div className="text-xs text-muted mt-1">
                  {a.transaction_count}{" "}
                  {a.transaction_count === 1
                    ? "movimiento"
                    : "movimientos"}
                </div>

                {a.last_import_at && (
                  <div className="text-xs text-muted">
                    Última importación:{" "}
                    {new Date(a.last_import_at).toLocaleDateString(
                      "es-ES",
                    )}
                  </div>
                )}

                <div className="mt-4 pt-4 border-t border-border flex justify-end gap-4">
                  <button
                    type="button"
                    onClick={() =>
                      deleteAccountTransactions(
                        a.id,
                        a.account_name,
                        a.transaction_count,
                      )
                    }
                    disabled={
                      anyActionInFlight ||
                      a.transaction_count === 0
                    }
                    className="text-sm text-red-600 hover:text-red-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {isDeleting
                      ? "Borrando..."
                      : a.transaction_count === 0
                        ? "Sin movimientos"
                        : "Borrar movimientos"}
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      deleteAccount(a.id, a.account_name, a.transaction_count)
                    }
                    disabled={anyActionInFlight}
                    className="text-sm font-medium text-red-700 hover:text-red-800 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {isDeletingAccount ? "Eliminando..." : "Eliminar cuenta"}
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