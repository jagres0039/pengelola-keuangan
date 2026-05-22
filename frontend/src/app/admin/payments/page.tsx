"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { api, type AdminPayment, type UserMe } from "@/lib/api";
import { formatMoney } from "@/lib/format";

export default function AdminPaymentsPage() {
  return <AuthGuard>{(user) => <AdminInner user={user} />}</AuthGuard>;
}

function AdminInner({ user }: { user: UserMe }) {
  const router = useRouter();
  const [items, setItems] = useState<AdminPayment[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    if (!user.is_admin) {
      router.replace("/dashboard");
    }
  }, [user.is_admin, router]);

  async function refresh() {
    setErr(null);
    try {
      const data = await api.get<AdminPayment[]>("/admin/payments/pending");
      setItems(data);
    } catch (e: unknown) {
      setErr((e as { detail?: string }).detail ?? "gagal load");
    }
  }

  useEffect(() => {
    if (user.is_admin) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.is_admin]);

  async function approve(id: number) {
    setBusyId(id);
    setErr(null);
    setInfo(null);
    try {
      await api.post(`/admin/payments/${id}/approve`);
      setInfo(`Payment #${id} disetujui.`);
      await refresh();
    } catch (e: unknown) {
      setErr((e as { detail?: string }).detail ?? "gagal approve");
    } finally {
      setBusyId(null);
    }
  }

  async function reject(id: number) {
    const reason = window.prompt("Alasan penolakan:");
    if (!reason || !reason.trim()) return;
    setBusyId(id);
    setErr(null);
    setInfo(null);
    try {
      await api.post(`/admin/payments/${id}/reject`, { reason: reason.trim() });
      setInfo(`Payment #${id} ditolak.`);
      await refresh();
    } catch (e: unknown) {
      setErr((e as { detail?: string }).detail ?? "gagal reject");
    } finally {
      setBusyId(null);
    }
  }

  if (!user.is_admin) {
    return null;
  }

  return (
    <div className="mx-auto min-h-dvh max-w-md pb-8">
      <header className="safe-top flex items-center justify-between px-4 pb-2 pt-4">
        <h1 className="text-lg font-semibold">Admin · Verifikasi pembayaran</h1>
        <Link href="/settings" className="text-sm text-brand-600">
          ← Setelan
        </Link>
      </header>

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

      <section className="mx-4 mt-4 space-y-3">
        {items.length === 0 ? (
          <p className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
            Belum ada pembayaran pending.
          </p>
        ) : (
          items.map((p) => {
            const created = new Date(p.created_at);
            return (
              <div key={p.id} className="rounded-2xl bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-800">
                      #{p.id} · {formatMoney(p.amount, "IDR")}
                    </p>
                    <p className="text-xs text-slate-500">
                      {p.user_first_name || p.user_email || `user #${p.user_id}`}
                    </p>
                    <p className="text-xs text-slate-400">{p.method}</p>
                  </div>
                  <p className="shrink-0 text-xs text-slate-400">
                    {created.toLocaleString("id-ID", {
                      day: "numeric",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
                {p.proof_note ? (
                  <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    {p.proof_note}
                  </p>
                ) : null}
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    disabled={busyId === p.id}
                    onClick={() => approve(p.id)}
                    className="flex-1 rounded-xl bg-emerald-600 px-3 py-2 text-sm font-semibold text-white shadow disabled:opacity-60"
                  >
                    {busyId === p.id ? "memproses…" : "Setujui"}
                  </button>
                  <button
                    type="button"
                    disabled={busyId === p.id}
                    onClick={() => reject(p.id)}
                    className="flex-1 rounded-xl bg-rose-100 px-3 py-2 text-sm font-semibold text-rose-700 disabled:opacity-60"
                  >
                    Tolak
                  </button>
                </div>
              </div>
            );
          })
        )}
      </section>
    </div>
  );
}
