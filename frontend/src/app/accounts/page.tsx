"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import {
  api,
  type Account,
  type AccountKind,
  type Transfer,
  type UserMe,
} from "@/lib/api";
import { formatMoney } from "@/lib/format";

const KIND_LABEL: Record<AccountKind, string> = {
  cash: "Kas Tunai",
  bank: "Bank",
  ewallet: "E-Wallet",
  other: "Lainnya",
};

const KIND_ICON: Record<AccountKind, string> = {
  cash: "💵",
  bank: "🏦",
  ewallet: "📱",
  other: "📦",
};

export default function AccountsPage() {
  return (
    <AuthGuard>{(user) => <AccountsInner user={user} />}</AuthGuard>
  );
}

function AccountsInner({ user }: { user: UserMe }) {
  const router = useRouter();

  useEffect(() => {
    if (user.profile_mode !== "pengusaha") router.replace("/settings");
  }, [user.profile_mode, router]);

  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [includeArchived, setIncludeArchived] = useState(false);

  const [editingAcc, setEditingAcc] = useState<Account | null>(null);
  const [showAccForm, setShowAccForm] = useState(false);
  const [showTransfer, setShowTransfer] = useState(false);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const [accs, trs] = await Promise.all([
        api.get<Account[]>(
          `/accounts${includeArchived ? "?include_archived=true" : ""}`,
        ),
        api.get<Transfer[]>("/transfers"),
      ]);
      setAccounts(accs);
      setTransfers(trs);
    } catch (e) {
      setError((e as { detail?: string }).detail ?? "gagal load");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (user.profile_mode === "pengusaha") void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.profile_mode, includeArchived]);

  function onAccSaved(saved: Account, wasNew: boolean) {
    setShowAccForm(false);
    setEditingAcc(null);
    setAccounts((a) =>
      wasNew ? [...a, saved] : a.map((x) => (x.id === saved.id ? saved : x)),
    );
  }

  async function onAccArchive(a: Account) {
    try {
      const updated = await api.post<Account>(
        `/accounts/${a.id}/${a.archived ? "unarchive" : "archive"}`,
      );
      setAccounts((acs) => acs.map((x) => (x.id === updated.id ? updated : x)));
    } catch (e) {
      alert((e as { detail?: string }).detail ?? "gagal");
    }
  }

  async function onAccDelete(a: Account) {
    if (!confirm(`Hapus akun "${a.name}"? Tidak bisa kalau masih ada transaksi/transfer.`)) return;
    try {
      await api.delete<void>(`/accounts/${a.id}`);
      setAccounts((acs) => acs.filter((x) => x.id !== a.id));
    } catch (e) {
      alert((e as { detail?: string }).detail ?? "gagal hapus");
    }
  }

  function onTransferCreated(t: Transfer) {
    setShowTransfer(false);
    setTransfers((ts) => [t, ...ts]);
    void load();
  }

  async function onTransferDelete(id: number) {
    if (!confirm("Hapus transfer ini? Saldo akan dikoreksi.")) return;
    try {
      await api.delete<void>(`/transfers/${id}`);
      setTransfers((ts) => ts.filter((t) => t.id !== id));
      void load();
    } catch (e) {
      alert((e as { detail?: string }).detail ?? "gagal hapus");
    }
  }

  if (user.profile_mode !== "pengusaha") {
    return (
      <PageWithNav>
        <p className="px-4 py-6 text-sm text-slate-500">Redirect…</p>
      </PageWithNav>
    );
  }

  const activeAccounts = accounts.filter((a) => !a.archived);

  return (
    <PageWithNav>
      <header className="safe-top flex items-center justify-between px-4 pb-2 pt-4">
        <div>
          <h1 className="text-xl font-bold">Akun Kas</h1>
          <p className="text-sm text-slate-500">Kas tunai, bank, e-wallet</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setEditingAcc(null);
            setShowAccForm(true);
          }}
          className="rounded-xl bg-brand-600 px-3 py-2 text-sm font-medium text-white shadow-sm active:bg-brand-700"
        >
          + Akun
        </button>
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
        ) : accounts.length === 0 ? (
          <li className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
            belum ada akun
          </li>
        ) : (
          accounts.map((a) => (
            <li
              key={a.id}
              className={
                "rounded-xl bg-white p-3 shadow-sm " +
                (a.archived ? "opacity-60" : "")
              }
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{KIND_ICON[a.kind]}</span>
                    <span className="truncate font-medium">{a.name}</span>
                    <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                      {KIND_LABEL[a.kind]}
                    </span>
                    {a.archived ? (
                      <span className="shrink-0 rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-700">
                        Arsip
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-lg font-bold text-slate-900">
                    {formatMoney(a.balance, user.currency)}
                  </p>
                  <p className="text-[10px] text-slate-400">
                    Saldo awal {formatMoney(a.opening_balance, user.currency)}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingAcc(a);
                      setShowAccForm(true);
                    }}
                    className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => void onAccArchive(a)}
                    className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700"
                  >
                    {a.archived ? "Pulihkan" : "Arsipkan"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void onAccDelete(a)}
                    className="rounded-lg bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700"
                  >
                    Hapus
                  </button>
                </div>
              </div>
            </li>
          ))
        )}
      </ul>

      <label className="mx-4 mt-2 flex items-center gap-2 text-xs text-slate-600">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
        />
        Tampilkan akun diarsipkan
      </label>

      <section className="mx-4 mt-6">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Transfer Antar Akun
          </h2>
          <button
            type="button"
            disabled={activeAccounts.length < 2}
            onClick={() => setShowTransfer(true)}
            className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            + Transfer
          </button>
        </div>
        <ul className="mt-2 space-y-2 pb-4">
          {transfers.length === 0 ? (
            <li className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
              belum ada transfer
            </li>
          ) : (
            transfers.map((t) => (
              <li key={t.id} className="rounded-xl bg-white p-3 shadow-sm">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-800">
                      {t.from_account_name} → {t.to_account_name}
                    </p>
                    <p className="text-sm font-bold text-slate-900">
                      {formatMoney(t.amount, user.currency)}
                    </p>
                    {t.note ? (
                      <p className="text-xs text-slate-500">{t.note}</p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => void onTransferDelete(t.id)}
                    className="rounded-lg bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700"
                  >
                    Hapus
                  </button>
                </div>
              </li>
            ))
          )}
        </ul>
      </section>

      {showAccForm ? (
        <AccountFormModal
          account={editingAcc}
          onClose={() => {
            setShowAccForm(false);
            setEditingAcc(null);
          }}
          onSaved={onAccSaved}
        />
      ) : null}

      {showTransfer ? (
        <TransferModal
          accounts={activeAccounts}
          onClose={() => setShowTransfer(false)}
          onCreated={onTransferCreated}
        />
      ) : null}
    </PageWithNav>
  );
}

function AccountFormModal({
  account,
  onClose,
  onSaved,
}: {
  account: Account | null;
  onClose: () => void;
  onSaved: (saved: Account, wasNew: boolean) => void;
}) {
  const isEdit = account !== null;
  const [name, setName] = useState(account?.name ?? "");
  const [kind, setKind] = useState<AccountKind>(account?.kind ?? "cash");
  const [opening, setOpening] = useState(account?.opening_balance ?? "0");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("nama wajib diisi");
      return;
    }
    const opVal = (opening || "0").replace(/[^0-9.]/g, "");
    if (Number.isNaN(parseFloat(opVal))) {
      setError("saldo awal tidak valid");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (isEdit && account) {
        const saved = await api.patch<Account>(`/accounts/${account.id}`, {
          name: name.trim(),
          kind,
          opening_balance: opVal,
        });
        onSaved(saved, false);
      } else {
        const saved = await api.post<Account>("/accounts", {
          name: name.trim(),
          kind,
          opening_balance: opVal,
        });
        onSaved(saved, true);
      }
    } catch (e) {
      setError((e as { detail?: string }).detail ?? "gagal simpan");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center">
      <div className="w-full max-w-md rounded-t-2xl bg-white p-4 shadow-xl sm:rounded-2xl">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-bold">
            {isEdit ? "Edit Akun" : "Tambah Akun"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm text-slate-500"
          >
            ✕
          </button>
        </div>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="text-xs font-medium text-slate-700">Nama *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={64}
              required
              autoFocus
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700">Jenis</label>
            <div
              role="radiogroup"
              className="mt-1 grid grid-cols-4 gap-1 rounded-xl bg-slate-100 p-1 text-xs"
            >
              {(["cash", "bank", "ewallet", "other"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  role="radio"
                  aria-checked={kind === k}
                  onClick={() => setKind(k)}
                  className={
                    "rounded-lg px-2 py-2 font-medium " +
                    (kind === k
                      ? "bg-white text-brand-700 shadow-sm"
                      : "text-slate-600")
                  }
                >
                  {KIND_ICON[k]} {KIND_LABEL[k]}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700">
              Saldo awal
            </label>
            <input
              type="text"
              inputMode="decimal"
              value={opening}
              onChange={(e) => setOpening(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="0"
            />
          </div>
          {error ? (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          ) : null}
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-xl bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={busy}
              className="flex-1 rounded-xl bg-brand-600 px-3 py-2 text-sm font-medium text-white shadow-sm active:bg-brand-700 disabled:opacity-60"
            >
              {busy ? "menyimpan…" : "Simpan"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function TransferModal({
  accounts,
  onClose,
  onCreated,
}: {
  accounts: Account[];
  onClose: () => void;
  onCreated: (t: Transfer) => void;
}) {
  const [fromId, setFromId] = useState<number>(accounts[0]?.id ?? 0);
  const [toId, setToId] = useState<number>(accounts[1]?.id ?? 0);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (fromId === toId) {
      setError("akun asal & tujuan harus beda");
      return;
    }
    const amt = parseFloat(amount.replace(/[^0-9.]/g, ""));
    if (!Number.isFinite(amt) || amt <= 0) {
      setError("jumlah tidak valid");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const t = await api.post<Transfer>("/transfers", {
        from_account_id: fromId,
        to_account_id: toId,
        amount: String(amt),
        note: note.trim() || undefined,
      });
      onCreated(t);
    } catch (e) {
      setError((e as { detail?: string }).detail ?? "gagal");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center">
      <div className="w-full max-w-md rounded-t-2xl bg-white p-4 shadow-xl sm:rounded-2xl">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-bold">Transfer Antar Akun</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm text-slate-500"
          >
            ✕
          </button>
        </div>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="text-xs font-medium text-slate-700">Dari</label>
            <select
              value={fromId}
              onChange={(e) => setFromId(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700">Ke</label>
            <select
              value={toId}
              onChange={(e) => setToId(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700">Jumlah</label>
            <input
              type="text"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              required
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700">Catatan</label>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={255}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>
          {error ? (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          ) : null}
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-xl bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={busy}
              className="flex-1 rounded-xl bg-brand-600 px-3 py-2 text-sm font-medium text-white shadow-sm active:bg-brand-700 disabled:opacity-60"
            >
              {busy ? "menyimpan…" : "Transfer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
