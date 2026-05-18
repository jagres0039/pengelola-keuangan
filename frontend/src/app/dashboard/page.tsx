"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import { api, type Summary, type UserMe } from "@/lib/api";
import { formatMoney } from "@/lib/format";

export default function DashboardPage() {
  return <AuthGuard>{(user) => <DashboardInner user={user} />}</AuthGuard>;
}

function DashboardInner({ user }: { user: UserMe }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Summary>("/summary")
      .then(setSummary)
      .catch((e: { detail?: string }) => setError(e.detail ?? "gagal load"));
  }, []);

  const monthName = summary
    ? new Date(summary.year, summary.month - 1).toLocaleDateString("id-ID", {
        month: "long",
        year: "numeric",
      })
    : "—";

  return (
    <PageWithNav>
      <header className="safe-top flex items-center justify-between px-4 pb-2 pt-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Halo,</p>
          <h1 className="text-lg font-semibold">
            {user.first_name || user.email || "kamu"}
          </h1>
        </div>
        <Link
          href="/settings"
          className="grid h-10 w-10 place-items-center rounded-full bg-white shadow"
        >
          ⚙️
        </Link>
      </header>

      <section className="mx-4 mt-2 rounded-3xl bg-gradient-to-br from-brand-600 to-brand-800 p-5 text-white shadow-lg">
        <p className="text-xs uppercase tracking-wide opacity-80">Saldo Bulan {monthName}</p>
        <p className="mt-1 text-3xl font-bold">
          {summary ? formatMoney(summary.balance, user.currency) : "—"}
        </p>
        <div className="mt-4 flex justify-between text-sm">
          <div>
            <p className="opacity-80">Pemasukan</p>
            <p className="font-semibold">
              {summary ? formatMoney(summary.total_income, user.currency) : "—"}
            </p>
          </div>
          <div className="text-right">
            <p className="opacity-80">Pengeluaran</p>
            <p className="font-semibold">
              {summary ? formatMoney(summary.total_expense, user.currency) : "—"}
            </p>
          </div>
        </div>
      </section>

      {error ? (
        <div className="mx-4 mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <section className="mx-4 mt-6">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Top pengeluaran
          </h2>
          <Link href="/history" className="text-sm font-medium text-brand-600">
            Lihat semua →
          </Link>
        </div>
        <div className="space-y-2">
          {summary?.expense_by_category.length ? (
            summary.expense_by_category.slice(0, 5).map((c) => (
              <div
                key={c.category_id ?? c.category_name}
                className="flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-sm"
              >
                <span className="text-sm font-medium">{c.category_name}</span>
                <span className="text-sm font-semibold text-rose-600">
                  -{formatMoney(c.total, user.currency)}
                </span>
              </div>
            ))
          ) : (
            <p className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
              Belum ada pengeluaran bulan ini.
            </p>
          )}
        </div>
      </section>

      <section className="mx-4 mt-6 grid grid-cols-2 gap-3">
        <Link
          href="/add?type=in"
          className="flex flex-col items-center justify-center gap-1 rounded-2xl bg-emerald-100 px-4 py-5 text-emerald-700 shadow-sm"
        >
          <span className="text-2xl">💰</span>
          <span className="text-sm font-semibold">Catat Masuk</span>
        </Link>
        <Link
          href="/add?type=out"
          className="flex flex-col items-center justify-center gap-1 rounded-2xl bg-rose-100 px-4 py-5 text-rose-700 shadow-sm"
        >
          <span className="text-2xl">💸</span>
          <span className="text-sm font-semibold">Catat Keluar</span>
        </Link>
      </section>

      <section className="mx-4 mt-4">
        <Link
          href="/receipt"
          className="flex items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-brand-300 bg-white px-4 py-5 text-brand-700 shadow-sm"
        >
          <span className="text-2xl">📷</span>
          <span className="text-sm font-semibold">Foto Struk (OCR)</span>
        </Link>
      </section>
    </PageWithNav>
  );
}
