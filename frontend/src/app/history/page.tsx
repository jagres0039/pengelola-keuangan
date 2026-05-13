"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import { api, type Transaction, type UserMe } from "@/lib/api";
import { formatDateTime, formatMoney } from "@/lib/format";

export default function HistoryPage() {
  return <AuthGuard>{(user) => <HistoryInner user={user} />}</AuthGuard>;
}

function HistoryInner({ user }: { user: UserMe }) {
  const [rows, setRows] = useState<Transaction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);

  async function load() {
    setBusy(true);
    try {
      const r = await api.get<Transaction[]>("/transactions?limit=100");
      setRows(r);
    } catch (e) {
      setError((e as { detail?: string }).detail ?? "gagal load");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function del(id: number) {
    if (!confirm("Hapus transaksi ini?")) return;
    try {
      await api.delete<void>(`/transactions/${id}`);
      setRows((rs) => rs.filter((r) => r.id !== id));
    } catch (e) {
      alert((e as { detail?: string }).detail ?? "gagal hapus");
    }
  }

  return (
    <PageWithNav>
      <header className="safe-top px-4 pb-2 pt-4">
        <h1 className="text-xl font-bold">Riwayat</h1>
        <p className="text-sm text-slate-500">{rows.length} transaksi</p>
      </header>

      {error ? (
        <div className="mx-4 my-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <ul className="mx-4 mt-2 space-y-2">
        {busy ? (
          <li className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
            memuat…
          </li>
        ) : rows.length === 0 ? (
          <li className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
            belum ada transaksi
          </li>
        ) : (
          rows.map((tx) => (
            <li
              key={tx.id}
              className="flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-sm"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className={
                      "rounded-full px-2 py-0.5 text-xs font-medium " +
                      (tx.type === "in"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-rose-100 text-rose-700")
                    }
                  >
                    {tx.category_name || "Tanpa kategori"}
                  </span>
                  <span className="truncate text-xs text-slate-500">
                    {formatDateTime(tx.occurred_at)}
                  </span>
                </div>
                {tx.note ? (
                  <p className="mt-0.5 truncate text-sm text-slate-700">{tx.note}</p>
                ) : null}
              </div>
              <div className="ml-3 flex items-center gap-2">
                <span
                  className={
                    "text-sm font-semibold " +
                    (tx.type === "in" ? "text-emerald-600" : "text-rose-600")
                  }
                >
                  {tx.type === "in" ? "+" : "-"}
                  {formatMoney(tx.amount, user.currency)}
                </span>
                <button
                  onClick={() => del(tx.id)}
                  className="rounded-full p-1 text-slate-400 hover:text-rose-600"
                  aria-label="hapus"
                >
                  ×
                </button>
              </div>
            </li>
          ))
        )}
      </ul>
    </PageWithNav>
  );
}
