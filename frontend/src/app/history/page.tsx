"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import { api, type Transaction, type TransactionItem, type UserMe } from "@/lib/api";
import { formatDateTime, formatMoney } from "@/lib/format";

export default function HistoryPage() {
  return <AuthGuard>{(user) => <HistoryInner user={user} />}</AuthGuard>;
}

function HistoryInner({ user }: { user: UserMe }) {
  const [rows, setRows] = useState<Transaction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

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

  function toggle(id: number) {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
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
          rows.map((tx) => {
            const isOpen = !!expanded[tx.id];
            const hasItems = (tx.items?.length ?? 0) > 0;
            return (
              <li key={tx.id} className="rounded-xl bg-white shadow-sm">
                <button
                  type="button"
                  onClick={() => toggle(tx.id)}
                  className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
                  aria-expanded={isOpen}
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
                      {hasItems ? (
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                          {tx.items.length} item
                        </span>
                      ) : null}
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
                    <span
                      aria-hidden="true"
                      className={
                        "inline-block text-slate-400 transition-transform " +
                        (isOpen ? "rotate-90" : "")
                      }
                    >
                      ›
                    </span>
                  </div>
                </button>

                {isOpen ? (
                  <div className="border-t border-slate-100 px-4 py-3">
                    {hasItems ? (
                      <ItemsList items={tx.items} currency={user.currency} />
                    ) : (
                      <p className="text-xs text-slate-400">
                        Tidak ada detail item (transaksi manual).
                      </p>
                    )}
                    <div className="mt-3 flex justify-end">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          del(tx.id);
                        }}
                        className="rounded-md px-3 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50"
                      >
                        Hapus transaksi
                      </button>
                    </div>
                  </div>
                ) : null}
              </li>
            );
          })
        )}
      </ul>
    </PageWithNav>
  );
}

function ItemsList({ items, currency }: { items: TransactionItem[]; currency: string }) {
  return (
    <ul className="space-y-1.5">
      {items.map((it) => {
        const qty = Number(it.qty);
        const showQty = Number.isFinite(qty) && qty !== 1;
        const unit = it.unit_price ? Number(it.unit_price) : null;
        const showUnit = unit !== null && Number.isFinite(unit) && unit > 0;
        return (
          <li key={it.id} className="flex items-start justify-between gap-3 text-sm">
            <div className="min-w-0 flex-1">
              <p className="truncate text-slate-700">{it.name}</p>
              {showQty || showUnit ? (
                <p className="text-xs text-slate-400">
                  {showQty ? `${formatQty(it.qty)}×` : ""}
                  {showUnit ? formatMoney(it.unit_price as string, currency) : ""}
                </p>
              ) : null}
            </div>
            <span className="shrink-0 text-sm font-medium text-slate-700">
              {formatMoney(it.subtotal, currency)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function formatQty(qty: string): string {
  const n = Number(qty);
  if (!Number.isFinite(n)) return qty;
  if (Number.isInteger(n)) return String(n);
  return n.toLocaleString("id-ID", { maximumFractionDigits: 3 });
}
