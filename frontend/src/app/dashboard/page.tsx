"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import { Settings, TrendingUp, TrendingDown, ShoppingBag, Camera } from "lucide-react";
import {
  api,
  type LowBalanceStatus,
  type SalesSummary,
  type SubscriptionStatus,
  type Summary,
  type UserMe,
} from "@/lib/api";
import { formatMoney } from "@/lib/format";

export default function DashboardPage() {
  return <AuthGuard>{(user) => <DashboardInner user={user} />}</AuthGuard>;
}

function DashboardInner({ user }: { user: UserMe }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [lowBalance, setLowBalance] = useState<LowBalanceStatus | null>(null);
  const [sub, setSub] = useState<SubscriptionStatus | null>(null);
  const [salesSummary, setSalesSummary] = useState<SalesSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Summary>("/summary")
      .then(setSummary)
      .catch((e: { detail?: string }) => setError(e.detail ?? "gagal load"));
    api
      .get<LowBalanceStatus>("/summary/low-balance")
      .then(setLowBalance)
      .catch(() => {
        /* non-fatal, just hide banner */
      });
    api
      .get<SubscriptionStatus>("/billing/status")
      .then(setSub)
      .catch(() => {
        /* non-fatal */
      });
    if (user.profile_mode === "pengusaha") {
      api
        .get<SalesSummary>("/sales/summary")
        .then(setSalesSummary)
        .catch(() => {
          /* non-fatal */
        });
    }
  }, [user.profile_mode]);

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
          <Settings size={18} className="text-slate-600" />
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

      {sub && !sub.can_write ? (
        <Link
          href="/billing"
          className="mx-4 mt-4 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-rose-800 shadow-sm"
        >
          <span aria-hidden="true" className="text-xl">🔒</span>
          <div className="flex-1 text-sm">
            <p className="font-semibold">Subscription kadaluarsa — mode read-only</p>
            <p className="mt-0.5 text-xs leading-relaxed text-rose-700">
              Lo masih bisa lihat data lama, tapi gak bisa catat transaksi baru.
              Bayar Rp 5.000 untuk lanjut 30 hari →
            </p>
          </div>
        </Link>
      ) : sub && sub.state === "trial" && sub.days_left <= 3 ? (
        <Link
          href="/billing"
          className="mx-4 mt-4 flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sky-800 shadow-sm"
        >
          <span aria-hidden="true" className="text-xl">⏳</span>
          <div className="flex-1 text-sm">
            <p className="font-semibold">
              Trial tersisa {sub.days_left} hari
            </p>
            <p className="mt-0.5 text-xs leading-relaxed text-sky-700">
              Perpanjang Rp 5.000 untuk lanjut 30 hari →
            </p>
          </div>
        </Link>
      ) : null}

      {lowBalance?.is_low ? (
        <div className="mx-4 mt-4 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-800 shadow-sm">
          <span aria-hidden="true" className="text-xl">⚠️</span>
          <div className="flex-1 text-sm">
            <p className="font-semibold">Saldo bulan ini menipis</p>
            <p className="mt-0.5 text-xs leading-relaxed text-amber-700">
              Saldo {formatMoney(lowBalance.balance, user.currency)} sudah di bawah
              ambang {formatMoney(lowBalance.threshold, user.currency)}.
              <Link href="/settings" className="ml-1 font-medium underline">
                Atur ambang
              </Link>
            </p>
          </div>
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

      <section
        className={
          "mx-4 mt-6 grid gap-3 " +
          (user.profile_mode === "pengusaha"
            ? "grid-cols-3"
            : "grid-cols-2")
        }
      >
        <Link
          href="/add?type=in"
          className="flex flex-col items-center justify-center gap-1 rounded-2xl bg-emerald-100 px-3 py-5 text-emerald-700 shadow-sm"
        >
          <span className="grid h-10 w-10 place-items-center rounded-full bg-emerald-200/50">
            <TrendingUp size={22} className="text-emerald-700" strokeWidth={2.5} />
          </span>
          <span className="text-xs font-semibold sm:text-sm">Catat Masuk</span>
        </Link>
        <Link
          href="/add?type=out"
          className="flex flex-col items-center justify-center gap-1 rounded-2xl bg-rose-100 px-3 py-5 text-rose-700 shadow-sm"
        >
          <span className="grid h-10 w-10 place-items-center rounded-full bg-rose-200/50">
            <TrendingDown size={22} className="text-rose-700" strokeWidth={2.5} />
          </span>
          <span className="text-xs font-semibold sm:text-sm">Catat Keluar</span>
        </Link>
        {user.profile_mode === "pengusaha" ? (
          <Link
            href="/sales"
            className="flex flex-col items-center justify-center gap-1 rounded-2xl bg-amber-100 px-3 py-5 text-amber-700 shadow-sm"
          >
            <span className="grid h-10 w-10 place-items-center rounded-full bg-amber-200/50">
              <ShoppingBag size={22} className="text-amber-700" strokeWidth={2.5} />
            </span>
            <span className="text-xs font-semibold sm:text-sm">Catat Jual</span>
          </Link>
        ) : null}
      </section>

      {user.profile_mode === "pengusaha" && salesSummary ? (
        <section className="mx-4 mt-4 rounded-2xl bg-white p-4 shadow-sm">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
              Pengusaha — bulan ini
            </h2>
            <Link href="/sales" className="text-xs font-medium text-brand-600">
              Lihat semua →
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-emerald-50 px-3 py-3">
              <p className="text-[11px] uppercase tracking-wide text-emerald-700">
                Laba
              </p>
              <p className="mt-0.5 text-base font-bold text-emerald-800">
                {formatMoney(salesSummary.profit, user.currency)}
              </p>
              <p className="text-[10px] text-emerald-700/80">
                omzet{" "}
                {formatMoney(salesSummary.revenue, user.currency)}
              </p>
            </div>
            <div className="rounded-xl bg-indigo-50 px-3 py-3">
              <p className="text-[11px] uppercase tracking-wide text-indigo-700">
                Barang Terjual
              </p>
              <p className="mt-0.5 text-base font-bold text-indigo-800">
                {Number(salesSummary.items_sold).toLocaleString("id-ID")} unit
              </p>
              <p className="text-[10px] text-indigo-700/80">
                {salesSummary.sales_count} transaksi
              </p>
            </div>
          </div>
          {salesSummary.unpaid_count > 0 ? (
            <Link
              href="/sales"
              className="mt-3 flex items-center justify-between rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800"
            >
              <span>
                <span className="font-semibold">
                  {salesSummary.unpaid_count}
                </span>{" "}
                pembeli belum bayar
              </span>
              <span className="font-semibold">
                {formatMoney(salesSummary.unpaid_amount, user.currency)} →
              </span>
            </Link>
          ) : null}
        </section>
      ) : null}

      <section className="mx-4 mt-4">
        <Link
          href="/receipt"
          className="flex items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-brand-300 bg-white px-4 py-5 text-brand-700 shadow-sm"
        >
          <Camera size={22} className="text-brand-600" strokeWidth={2.5} />
          <span className="text-sm font-semibold">Foto Struk (OCR)</span>
        </Link>
      </section>
    </PageWithNav>
  );
}
