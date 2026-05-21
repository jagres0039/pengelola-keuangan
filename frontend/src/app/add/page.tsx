"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import { api, type Account, type Category, type UserMe } from "@/lib/api";

export default function AddPage() {
  return (
    <AuthGuard>
      {(user) => (
        <Suspense fallback={<div className="p-4 text-slate-400">memuat…</div>}>
          <AddInner user={user} />
        </Suspense>
      )}
    </AuthGuard>
  );
}

function AddInner({ user }: { user: UserMe }) {
  const router = useRouter();
  const search = useSearchParams();
  const initialType =
    search.get("type") === "in" ? "in" : ("out" as "in" | "out");
  const [type, setType] = useState<"in" | "out">(initialType);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [catId, setCatId] = useState<number | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const isPengusaha = user.profile_mode === "pengusaha";

  useEffect(() => {
    api
      .get<Category[]>(`/categories?type=${type}`)
      .then((cats) => {
        setCategories(cats);
        setCatId((prev) => prev ?? cats[0]?.id ?? null);
      })
      .catch((e: { detail?: string }) => setErr(e.detail ?? "gagal load kategori"));
  }, [type]);

  useEffect(() => {
    if (!isPengusaha) return;
    api
      .get<Account[]>("/accounts")
      .then((accs) => setAccounts(accs))
      .catch(() => {
        /* non-fatal: account selector optional */
      });
  }, [isPengusaha]);

  function setTypeReset(t: "in" | "out") {
    setType(t);
    setCatId(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const amt = amount.replace(/[^\d.]/g, "");
      if (!amt || Number(amt) <= 0) throw { detail: "jumlah harus > 0" };
      await api.post("/transactions", {
        type,
        amount: amt,
        category_id: catId,
        account_id: isPengusaha ? accountId : null,
        note: note.trim() || null,
      });
      router.replace("/dashboard");
    } catch (e: unknown) {
      setErr((e as { detail?: string }).detail ?? "gagal simpan");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageWithNav>
      <header className="safe-top px-4 pb-2 pt-4">
        <h1 className="text-xl font-bold">Catat Transaksi</h1>
      </header>
      <div className="mx-4 mt-2 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => setTypeReset("in")}
          className={
            "rounded-xl px-4 py-3 text-sm font-semibold shadow-sm " +
            (type === "in"
              ? "bg-emerald-500 text-white"
              : "bg-white text-emerald-700")
          }
        >
          💰 Pemasukan
        </button>
        <button
          type="button"
          onClick={() => setTypeReset("out")}
          className={
            "rounded-xl px-4 py-3 text-sm font-semibold shadow-sm " +
            (type === "out"
              ? "bg-rose-500 text-white"
              : "bg-white text-rose-700")
          }
        >
          💸 Pengeluaran
        </button>
      </div>

      <form className="mx-4 mt-4 space-y-4" onSubmit={submit}>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Jumlah</label>
          <input
            type="text"
            inputMode="decimal"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="35000"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-lg font-semibold outline-none focus:border-brand-500"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Kategori</label>
          <div className="flex flex-wrap gap-2">
            {categories.map((c) => (
              <button
                type="button"
                key={c.id}
                onClick={() => setCatId(c.id)}
                className={
                  "rounded-full px-3 py-1.5 text-sm shadow-sm " +
                  (catId === c.id
                    ? "bg-brand-600 text-white"
                    : "bg-white text-slate-700")
                }
              >
                {c.emoji ? `${c.emoji} ` : ""}
                {c.name}
              </button>
            ))}
          </div>
        </div>

        {isPengusaha && accounts.length > 0 ? (
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Akun Kas (opsional)
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setAccountId(null)}
                className={
                  "rounded-full px-3 py-1.5 text-sm shadow-sm " +
                  (accountId === null
                    ? "bg-slate-800 text-white"
                    : "bg-white text-slate-700")
                }
              >
                — Tanpa akun —
              </button>
              {accounts.map((a) => (
                <button
                  type="button"
                  key={a.id}
                  onClick={() => setAccountId(a.id)}
                  className={
                    "rounded-full px-3 py-1.5 text-sm shadow-sm " +
                    (accountId === a.id
                      ? "bg-brand-600 text-white"
                      : "bg-white text-slate-700")
                  }
                >
                  {a.name}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Catatan (opsional)</label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="mis. makan siang"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-base outline-none focus:border-brand-500"
          />
        </div>

        {err ? (
          <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>
        ) : null}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-xl bg-brand-600 px-4 py-3 text-base font-semibold text-white shadow disabled:opacity-60"
        >
          {busy ? "menyimpan…" : "Simpan"}
        </button>
      </form>
    </PageWithNav>
  );
}
