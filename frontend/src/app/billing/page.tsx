"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import {
  api,
  type Payment,
  type SubscriptionStatus,
  type UserMe,
} from "@/lib/api";
import { formatMoney } from "@/lib/format";

export default function BillingPage() {
  return <AuthGuard>{(user) => <BillingInner user={user} />}</AuthGuard>;
}

type FormState = {
  amount: string;
  method: string;
  proofNote: string;
};

function BillingInner({ user }: { user: UserMe }) {
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<FormState>({
    amount: "",
    method: "bank_transfer",
    proofNote: "",
  });

  async function refresh() {
    try {
      const [st, ps] = await Promise.all([
        api.get<SubscriptionStatus>("/billing/status"),
        api.get<Payment[]>("/billing/payments"),
      ]);
      setStatus(st);
      setPayments(ps);
      if (st.monthly_price && !form.amount) {
        setForm((f) => ({ ...f, amount: st.monthly_price.replace(/\.00$/, "") }));
      }
    } catch (e: unknown) {
      setErr((e as { detail?: string }).detail ?? "gagal load status");
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submit() {
    if (!status) return;
    setBusy(true);
    setErr(null);
    setInfo(null);
    try {
      await api.post<Payment>("/billing/payments", {
        amount: form.amount,
        method: form.method,
        proof_note: form.proofNote.trim() || null,
      });
      setInfo(
        "Konfirmasi pembayaran terkirim. Tunggu admin verifikasi (biasanya < 24 jam).",
      );
      setForm({ amount: status.monthly_price.replace(/\.00$/, ""), method: form.method, proofNote: "" });
      await refresh();
    } catch (e: unknown) {
      setErr((e as { detail?: string }).detail ?? "gagal kirim");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageWithNav>
      <header className="safe-top flex items-center justify-between px-4 pb-2 pt-4">
        <h1 className="text-lg font-semibold">Subscription</h1>
        <Link href="/settings" className="text-sm text-brand-600">
          ← Setelan
        </Link>
      </header>

      <section className="mx-4 mt-2 rounded-2xl bg-white p-4 shadow-sm">
        {status === null ? (
          <p className="text-sm text-slate-400">memuat…</p>
        ) : (
          <StatusCard status={status} currency={user.currency} />
        )}
      </section>

      {err ? (
        <div className="mx-4 mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      ) : null}
      {info ? (
        <div className="mx-4 mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {info}
        </div>
      ) : null}

      {status && !status.has_pending_payment ? (
        <section className="mx-4 mt-4 rounded-2xl bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Instruksi pembayaran
          </h2>
          <pre className="mt-2 whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
            {status.billing_instructions}
          </pre>
          <p className="mt-2 text-xs text-slate-500">
            Transfer ke salah satu rekening di atas sebesar{" "}
            <strong>{formatMoney(status.monthly_price, status.currency)}</strong>{" "}
            untuk perpanjang 30 hari. Setelah transfer, isi form di bawah & admin
            akan verifikasi.
          </p>

          <div className="mt-4 space-y-3">
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">Nominal (Rp)</span>
              <input
                inputMode="numeric"
                value={form.amount}
                onChange={(e) =>
                  setForm((f) => ({ ...f, amount: e.target.value.replace(/[^\d.]/g, "") }))
                }
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                placeholder="5000"
              />
            </label>
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">Metode</span>
              <select
                value={form.method}
                onChange={(e) => setForm((f) => ({ ...f, method: e.target.value }))}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
              >
                <option value="bank_transfer">Transfer bank</option>
                <option value="dana">DANA</option>
                <option value="ovo">OVO</option>
                <option value="gopay">GoPay</option>
                <option value="qris">QRIS</option>
                <option value="lainnya">Lainnya</option>
              </select>
            </label>
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">
                Catatan / bukti (opsional)
              </span>
              <textarea
                value={form.proofNote}
                onChange={(e) => setForm((f) => ({ ...f, proofNote: e.target.value }))}
                placeholder="mis. transfer BCA 14:32, ref 1234567"
                rows={2}
                className="mt-1 w-full resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
            <button
              type="button"
              disabled={busy || !form.amount}
              onClick={submit}
              className="w-full rounded-xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white shadow active:scale-95 disabled:opacity-60"
            >
              {busy ? "mengirim…" : "Konfirmasi pembayaran"}
            </button>
          </div>
        </section>
      ) : null}

      {status?.has_pending_payment ? (
        <section className="mx-4 mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 shadow-sm">
          <p className="font-semibold">Pembayaran sedang diverifikasi</p>
          <p className="mt-1 text-xs leading-relaxed text-amber-700">
            Mohon tunggu konfirmasi admin (biasanya &lt; 24 jam). Lo bakal dapet
            akses penuh setelah disetujui.
          </p>
        </section>
      ) : null}

      <section className="mx-4 mb-6 mt-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Riwayat pembayaran
        </h2>
        <div className="mt-2 space-y-2">
          {payments.length === 0 ? (
            <p className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
              Belum ada pembayaran.
            </p>
          ) : (
            payments.map((p) => <PaymentRow key={p.id} payment={p} currency={user.currency} />)
          )}
        </div>
      </section>
    </PageWithNav>
  );
}

function StatusCard({ status, currency }: { status: SubscriptionStatus; currency: string }) {
  const tone =
    status.state === "active"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : status.state === "trial"
        ? "bg-sky-50 text-sky-700 border-sky-200"
        : "bg-rose-50 text-rose-700 border-rose-200";
  const label =
    status.state === "active"
      ? "Aktif"
      : status.state === "trial"
        ? `Trial — sisa ${status.days_left} hari`
        : "Kadaluarsa";
  const expiresAt = status.expires_at ? new Date(status.expires_at) : null;
  return (
    <div>
      <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium ${tone}`}>
        {label}
      </span>
      <p className="mt-3 text-sm text-slate-700">
        Harga: <strong>{formatMoney(status.monthly_price, currency)}</strong> / 30 hari
      </p>
      {expiresAt ? (
        <p className="mt-1 text-xs text-slate-500">
          {status.state === "expired" ? "Berakhir " : "Berlaku sampai "}
          {expiresAt.toLocaleString("id-ID", {
            day: "numeric",
            month: "long",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      ) : null}
      {!status.can_write ? (
        <p className="mt-2 rounded-lg bg-rose-50 px-2.5 py-1.5 text-xs text-rose-700">
          Akses tulis dinonaktifkan. Lo masih bisa lihat data lama, tapi tidak bisa catat transaksi baru sampai bayar.
        </p>
      ) : null}
    </div>
  );
}

function PaymentRow({ payment, currency }: { payment: Payment; currency: string }) {
  const created = new Date(payment.created_at);
  const tone =
    payment.status === "approved"
      ? "text-emerald-700"
      : payment.status === "rejected"
        ? "text-rose-700"
        : "text-amber-700";
  return (
    <div className="rounded-xl bg-white px-4 py-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-700">
            {formatMoney(payment.amount, currency)} · {payment.method}
          </p>
          <p className="text-xs text-slate-400">
            {created.toLocaleString("id-ID", {
              day: "numeric",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>
        <span className={`shrink-0 text-xs font-semibold uppercase ${tone}`}>
          {payment.status}
        </span>
      </div>
      {payment.proof_note ? (
        <p className="mt-1 text-xs text-slate-500">{payment.proof_note}</p>
      ) : null}
      {payment.rejection_reason ? (
        <p className="mt-1 text-xs text-rose-600">Alasan tolak: {payment.rejection_reason}</p>
      ) : null}
      {payment.period_end ? (
        <p className="mt-1 text-xs text-emerald-700">
          Akses aktif sampai{" "}
          {new Date(payment.period_end).toLocaleDateString("id-ID", {
            day: "numeric",
            month: "long",
            year: "numeric",
          })}
        </p>
      ) : null}
    </div>
  );
}
