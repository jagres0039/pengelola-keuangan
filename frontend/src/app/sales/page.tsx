"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import {
  api,
  type Account,
  type Contact,
  type InventoryItem,
  type Sale,
  type SaleCreatePayload,
  type SaleItemInput,
  type SaleMarkPaidPayload,
  type SalePaymentMethod,
  type SalePaymentStatus,
  type SalesSummary,
  type UserMe,
} from "@/lib/api";
import { formatMoney, formatDateTime } from "@/lib/format";

const METHOD_LABEL: Record<SalePaymentMethod, string> = {
  cash: "Cash",
  debit: "Debit",
  credit: "Kredit",
  unpaid: "Hutang",
};

const METHOD_BADGE: Record<SalePaymentMethod, string> = {
  cash: "bg-emerald-100 text-emerald-700",
  debit: "bg-sky-100 text-sky-700",
  credit: "bg-indigo-100 text-indigo-700",
  unpaid: "bg-amber-100 text-amber-700",
};

const STATUS_LABEL: Record<SalePaymentStatus, string> = {
  paid: "Lunas",
  unpaid: "Belum Bayar",
  partial: "Sebagian",
};

const STATUS_BADGE: Record<SalePaymentStatus, string> = {
  paid: "bg-emerald-100 text-emerald-700",
  unpaid: "bg-rose-100 text-rose-700",
  partial: "bg-amber-100 text-amber-700",
};

type FilterMode = "all" | "unpaid" | "paid";

export default function SalesPage() {
  return <AuthGuard>{(user) => <SalesInner user={user} />}</AuthGuard>;
}

function SalesInner({ user }: { user: UserMe }) {
  const router = useRouter();

  useEffect(() => {
    if (user.profile_mode !== "pengusaha") router.replace("/settings");
  }, [user.profile_mode, router]);

  const [sales, setSales] = useState<Sale[]>([]);
  const [summary, setSummary] = useState<SalesSummary | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterMode>("all");
  const [expanded, setExpanded] = useState<number | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [payingSale, setPayingSale] = useState<Sale | null>(null);

  async function loadAll() {
    setBusy(true);
    setError(null);
    try {
      const path =
        "/sales" +
        (filter === "all"
          ? ""
          : filter === "unpaid"
            ? "?status=unpaid"
            : "?status=paid");
      const [salesData, summaryData, contactsData, itemsData, accountsData] =
        await Promise.all([
          api.get<Sale[]>(path),
          api.get<SalesSummary>("/sales/summary"),
          api.get<Contact[]>("/contacts").catch(() => [] as Contact[]),
          api.get<InventoryItem[]>("/inventory").catch(() => [] as InventoryItem[]),
          api.get<Account[]>("/accounts").catch(() => [] as Account[]),
        ]);
      setSales(salesData);
      setSummary(summaryData);
      setContacts(contactsData);
      setItems(itemsData);
      setAccounts(accountsData);
    } catch (e) {
      setError((e as { detail?: string }).detail ?? "gagal load");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (user.profile_mode === "pengusaha") void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.profile_mode, filter]);

  async function onCreated(_created: Sale) {
    setShowForm(false);
    await loadAll();
  }

  async function onMarkedPaid(_updated: Sale) {
    setPayingSale(null);
    await loadAll();
  }

  async function onDelete(s: Sale) {
    if (
      !confirm(
        `Hapus penjualan #${s.id}? Stok akan dikembalikan dan transaksi pemasukan terkait juga dihapus.`,
      )
    )
      return;
    try {
      await api.delete<void>(`/sales/${s.id}`);
      await loadAll();
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

  return (
    <PageWithNav>
      <header className="safe-top flex items-center justify-between px-4 pb-2 pt-4">
        <div>
          <h1 className="text-xl font-bold">Penjualan</h1>
          <p className="text-sm text-slate-500">Catat penjualan ke pembeli</p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="rounded-xl bg-brand-600 px-3 py-2 text-sm font-medium text-white shadow-sm active:bg-brand-700"
        >
          + Jual
        </button>
      </header>

      {summary ? (
        <section className="mx-4 mt-2 rounded-2xl bg-gradient-to-br from-emerald-600 to-emerald-800 p-4 text-white shadow-sm">
          <p className="text-xs uppercase tracking-wide opacity-80">
            Laba bulan ini
          </p>
          <p className="mt-1 text-2xl font-bold">
            {formatMoney(summary.profit, user.currency)}
          </p>
          <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
            <div>
              <p className="opacity-80">Omzet</p>
              <p className="font-semibold">
                {formatMoney(summary.revenue, user.currency)}
              </p>
            </div>
            <div>
              <p className="opacity-80">Barang Terjual</p>
              <p className="font-semibold">
                {Number(summary.items_sold).toLocaleString("id-ID")} unit
              </p>
            </div>
            <div>
              <p className="opacity-80">Modal</p>
              <p className="font-semibold">
                {formatMoney(summary.cost, user.currency)}
              </p>
            </div>
            <div>
              <p className="opacity-80">Hutang Pembeli</p>
              <p className="font-semibold">
                {formatMoney(summary.unpaid_amount, user.currency)}{" "}
                {summary.unpaid_count > 0 ? (
                  <span className="ml-1 opacity-80">
                    ({summary.unpaid_count})
                  </span>
                ) : null}
              </p>
            </div>
          </div>
        </section>
      ) : null}

      <section className="mx-4 mt-3 flex gap-2 text-xs">
        {(["all", "unpaid", "paid"] as FilterMode[]).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={
              "rounded-full px-3 py-1 font-medium transition " +
              (filter === f
                ? "bg-brand-600 text-white"
                : "bg-white text-slate-600 shadow-sm")
            }
          >
            {f === "all" ? "Semua" : f === "unpaid" ? "Belum Lunas" : "Lunas"}
          </button>
        ))}
      </section>

      {error ? (
        <div className="mx-4 my-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <ul className="mx-4 mt-3 space-y-2">
        {busy ? (
          <li className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
            memuat…
          </li>
        ) : sales.length === 0 ? (
          <li className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
            belum ada penjualan
          </li>
        ) : (
          sales.map((s) => {
            const isOpen = expanded === s.id;
            return (
              <li key={s.id} className="rounded-xl bg-white shadow-sm">
                <button
                  type="button"
                  onClick={() => setExpanded(isOpen ? null : s.id)}
                  className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-semibold">
                        {s.contact_name || "Pembeli umum"}
                      </p>
                      <span
                        className={
                          "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase " +
                          STATUS_BADGE[s.payment_status]
                        }
                      >
                        {STATUS_LABEL[s.payment_status]}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-slate-500">
                      {formatDateTime(s.occurred_at)} ·{" "}
                      <span
                        className={
                          "inline-block rounded px-1.5 py-0.5 text-[10px] font-medium " +
                          METHOD_BADGE[s.payment_method]
                        }
                      >
                        {METHOD_LABEL[s.payment_method]}
                      </span>{" "}
                      · {s.items.length} item
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold">
                      {formatMoney(s.total_amount, user.currency)}
                    </p>
                    <p className="text-[11px] text-emerald-600">
                      laba {formatMoney(s.profit, user.currency)}
                    </p>
                  </div>
                </button>
                {isOpen ? (
                  <div className="border-t border-slate-100 px-4 py-3 text-sm">
                    <ul className="space-y-1">
                      {s.items.map((it) => (
                        <li
                          key={it.id}
                          className="flex items-start justify-between gap-2"
                        >
                          <div className="min-w-0 flex-1">
                            <p className="truncate">{it.name}</p>
                            <p className="text-[11px] text-slate-500">
                              {Number(it.qty).toLocaleString("id-ID")} ×{" "}
                              {formatMoney(it.unit_price, user.currency)}
                              {Number(it.unit_cost) > 0 ? (
                                <>
                                  {" "}
                                  · modal{" "}
                                  {formatMoney(it.unit_cost, user.currency)}
                                </>
                              ) : null}
                            </p>
                          </div>
                          <div className="text-right text-xs">
                            <p>{formatMoney(it.subtotal, user.currency)}</p>
                            <p className="text-emerald-600">
                              +{formatMoney(it.profit, user.currency)}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                    {s.note ? (
                      <p className="mt-2 rounded bg-slate-50 px-2 py-1 text-xs text-slate-600">
                        {s.note}
                      </p>
                    ) : null}
                    {s.payment_status !== "paid" ? (
                      <p className="mt-2 text-xs text-amber-700">
                        Sisa hutang:{" "}
                        <span className="font-semibold">
                          {formatMoney(
                            String(
                              Number(s.total_amount) - Number(s.paid_amount),
                            ),
                            user.currency,
                          )}
                        </span>
                      </p>
                    ) : null}
                    <div className="mt-3 flex gap-2">
                      {s.payment_status !== "paid" ? (
                        <button
                          type="button"
                          onClick={() => setPayingSale(s)}
                          className="flex-1 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white"
                        >
                          Tandai Lunas
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => onDelete(s)}
                        className="flex-1 rounded-lg bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700"
                      >
                        Hapus
                      </button>
                    </div>
                  </div>
                ) : null}
              </li>
            );
          })
        )}
      </ul>

      {showForm ? (
        <SaleForm
          user={user}
          contacts={contacts}
          items={items}
          accounts={accounts}
          onCancel={() => setShowForm(false)}
          onSaved={onCreated}
        />
      ) : null}
      {payingSale ? (
        <PayForm
          sale={payingSale}
          accounts={accounts}
          onCancel={() => setPayingSale(null)}
          onPaid={onMarkedPaid}
        />
      ) : null}
    </PageWithNav>
  );
}

type Draft = {
  inventory_item_id: number | null;
  name: string;
  qty: string;
  unit_price: string;
  unit_cost: string;
};

function emptyDraft(): Draft {
  return {
    inventory_item_id: null,
    name: "",
    qty: "1",
    unit_price: "",
    unit_cost: "",
  };
}

function SaleForm({
  user,
  contacts,
  items,
  accounts,
  onCancel,
  onSaved,
}: {
  user: UserMe;
  contacts: Contact[];
  items: InventoryItem[];
  accounts: Account[];
  onCancel: () => void;
  onSaved: (s: Sale) => void;
}) {
  const customers = useMemo(
    () => contacts.filter((c) => c.kind === "customer" || c.kind === "both"),
    [contacts],
  );
  const activeItems = useMemo(
    () => items.filter((i) => !i.archived),
    [items],
  );
  const activeAccounts = useMemo(
    () => accounts.filter((a) => !a.archived),
    [accounts],
  );

  const [contactId, setContactId] = useState<number | "">("");
  const [paymentMethod, setPaymentMethod] = useState<SalePaymentMethod>("cash");
  const [accountId, setAccountId] = useState<number | "">(
    activeAccounts[0]?.id ?? "",
  );
  const [drafts, setDrafts] = useState<Draft[]>([emptyDraft()]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const total = useMemo(() => {
    let sum = 0;
    for (const d of drafts) {
      const q = Number(d.qty || 0);
      const p = Number(d.unit_price || 0);
      if (Number.isFinite(q) && Number.isFinite(p)) sum += q * p;
    }
    return sum;
  }, [drafts]);

  function patchDraft(idx: number, p: Partial<Draft>) {
    setDrafts((ds) => ds.map((d, i) => (i === idx ? { ...d, ...p } : d)));
  }

  function pickInventory(idx: number, idStr: string) {
    if (idStr === "") {
      patchDraft(idx, { inventory_item_id: null });
      return;
    }
    const id = Number(idStr);
    const inv = activeItems.find((x) => x.id === id);
    if (!inv) return;
    patchDraft(idx, {
      inventory_item_id: id,
      name: inv.name,
      unit_cost: inv.last_cost ?? "",
    });
  }

  function addRow() {
    setDrafts((ds) => [...ds, emptyDraft()]);
  }

  function removeRow(idx: number) {
    setDrafts((ds) => (ds.length === 1 ? ds : ds.filter((_, i) => i !== idx)));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const cleanItems: SaleItemInput[] = drafts
      .map<SaleItemInput>((d) => ({
        inventory_item_id: d.inventory_item_id ?? null,
        name: d.name.trim(),
        qty: d.qty || "0",
        unit_price: d.unit_price || "0",
        unit_cost: d.unit_cost ? d.unit_cost : undefined,
      }))
      .filter((it) => it.name && Number(it.qty) > 0);
    if (cleanItems.length === 0) {
      setErr("isi minimal 1 barang dengan jumlah > 0");
      return;
    }
    if (
      paymentMethod !== "unpaid" &&
      activeAccounts.length > 0 &&
      !accountId
    ) {
      setErr("pilih akun kas tujuan");
      return;
    }
    const payload: SaleCreatePayload = {
      contact_id: contactId === "" ? null : contactId,
      payment_method: paymentMethod,
      account_id:
        paymentMethod === "unpaid" || !accountId ? null : Number(accountId),
      items: cleanItems,
      note: note.trim() || undefined,
    };
    setBusy(true);
    try {
      const created = await api.post<Sale>("/sales", payload);
      onSaved(created);
    } catch (e) {
      setErr((e as { detail?: string }).detail ?? "gagal simpan");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 px-2 pb-2 pt-10 sm:items-center sm:p-4">
      <form
        onSubmit={submit}
        className="flex max-h-[90vh] w-full max-w-md flex-col overflow-hidden rounded-2xl bg-white shadow-xl"
      >
        <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="text-base font-semibold">Catat Penjualan</h2>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full p-1 text-slate-500 hover:bg-slate-100"
            aria-label="tutup"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3">
          <div>
            <label className="text-xs font-semibold uppercase text-slate-500">
              Pembeli
            </label>
            <select
              value={contactId}
              onChange={(e) =>
                setContactId(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
            >
              <option value="">— Pembeli umum (tanpa kontak) —</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            {customers.length === 0 ? (
              <p className="mt-1 text-[11px] text-slate-500">
                Belum ada kontak pembeli.{" "}
                <a href="/contacts" className="text-brand-600 underline">
                  Tambah pembeli →
                </a>
              </p>
            ) : null}
          </div>

          <div>
            <label className="text-xs font-semibold uppercase text-slate-500">
              Barang
            </label>
            <ul className="mt-1 space-y-2">
              {drafts.map((d, idx) => (
                <li
                  key={idx}
                  className="rounded-lg border border-slate-200 bg-slate-50 p-2"
                >
                  <div className="flex items-center gap-2">
                    <select
                      value={d.inventory_item_id ?? ""}
                      onChange={(e) => pickInventory(idx, e.target.value)}
                      className="flex-1 rounded border border-slate-200 bg-white px-2 py-1.5 text-xs"
                    >
                      <option value="">— Barang lain (manual) —</option>
                      {activeItems.map((it) => (
                        <option key={it.id} value={it.id}>
                          {it.name} (stok {Number(it.stock)})
                        </option>
                      ))}
                    </select>
                    {drafts.length > 1 ? (
                      <button
                        type="button"
                        onClick={() => removeRow(idx)}
                        aria-label="hapus baris"
                        className="rounded p-1 text-rose-500 hover:bg-rose-100"
                      >
                        ✕
                      </button>
                    ) : null}
                  </div>
                  <input
                    type="text"
                    value={d.name}
                    onChange={(e) => patchDraft(idx, { name: e.target.value })}
                    placeholder="Nama barang"
                    className="mt-2 w-full rounded border border-slate-200 bg-white px-2 py-1.5 text-xs"
                  />
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    <label className="block text-[10px] text-slate-500">
                      Qty
                      <input
                        type="number"
                        inputMode="decimal"
                        min="0"
                        step="any"
                        value={d.qty}
                        onChange={(e) =>
                          patchDraft(idx, { qty: e.target.value })
                        }
                        className="mt-0.5 w-full rounded border border-slate-200 bg-white px-2 py-1 text-xs"
                      />
                    </label>
                    <label className="block text-[10px] text-slate-500">
                      Harga jual
                      <input
                        type="number"
                        inputMode="decimal"
                        min="0"
                        step="any"
                        value={d.unit_price}
                        onChange={(e) =>
                          patchDraft(idx, { unit_price: e.target.value })
                        }
                        className="mt-0.5 w-full rounded border border-slate-200 bg-white px-2 py-1 text-xs"
                      />
                    </label>
                    <label className="block text-[10px] text-slate-500">
                      Modal
                      <input
                        type="number"
                        inputMode="decimal"
                        min="0"
                        step="any"
                        value={d.unit_cost}
                        onChange={(e) =>
                          patchDraft(idx, { unit_cost: e.target.value })
                        }
                        placeholder="auto"
                        className="mt-0.5 w-full rounded border border-slate-200 bg-white px-2 py-1 text-xs"
                      />
                    </label>
                  </div>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={addRow}
              className="mt-2 w-full rounded-lg border border-dashed border-slate-300 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              + Tambah Barang
            </button>
          </div>

          <div>
            <label className="text-xs font-semibold uppercase text-slate-500">
              Pembayaran
            </label>
            <div className="mt-1 grid grid-cols-4 gap-1.5">
              {(["cash", "debit", "credit", "unpaid"] as SalePaymentMethod[]).map(
                (m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setPaymentMethod(m)}
                    className={
                      "rounded-lg px-2 py-2 text-xs font-semibold transition " +
                      (paymentMethod === m
                        ? "bg-brand-600 text-white"
                        : "bg-slate-100 text-slate-600")
                    }
                  >
                    {METHOD_LABEL[m]}
                  </button>
                ),
              )}
            </div>
            {paymentMethod === "unpaid" ? (
              <p className="mt-1 text-[11px] text-amber-700">
                Penjualan ini akan masuk daftar hutang pembeli. Tandai lunas
                nanti pas dibayar.
              </p>
            ) : null}
          </div>

          {paymentMethod !== "unpaid" && activeAccounts.length > 0 ? (
            <div>
              <label className="text-xs font-semibold uppercase text-slate-500">
                Akun Kas Tujuan
              </label>
              <select
                value={accountId}
                onChange={(e) =>
                  setAccountId(
                    e.target.value === "" ? "" : Number(e.target.value),
                  )
                }
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
              >
                <option value="">— Pilih akun —</option>
                {activeAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({formatMoney(a.balance, user.currency)})
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <div>
            <label className="text-xs font-semibold uppercase text-slate-500">
              Catatan (opsional)
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              placeholder="Misal: pengiriman, diskon, dll"
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
            />
          </div>
        </div>

        <footer className="border-t border-slate-100 px-4 py-3">
          {err ? (
            <p className="mb-2 rounded bg-red-50 px-2 py-1 text-xs text-red-700">
              {err}
            </p>
          ) : null}
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-slate-500">Total</span>
            <span className="text-base font-bold">
              {formatMoney(String(total), user.currency)}
            </span>
          </div>
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white shadow-sm active:bg-brand-700 disabled:opacity-60"
          >
            {busy ? "Menyimpan…" : "Simpan Penjualan"}
          </button>
        </footer>
      </form>
    </div>
  );
}

function PayForm({
  sale,
  accounts,
  onCancel,
  onPaid,
}: {
  sale: Sale;
  accounts: Account[];
  onCancel: () => void;
  onPaid: (s: Sale) => void;
}) {
  const activeAccounts = accounts.filter((a) => !a.archived);
  const remaining = (Number(sale.total_amount) - Number(sale.paid_amount)).toFixed(2);
  const [accountId, setAccountId] = useState<number | "">(
    activeAccounts[0]?.id ?? "",
  );
  const [method, setMethod] = useState<SalePaymentMethod>("cash");
  const [amount, setAmount] = useState<string>(remaining);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const num = Number(amount);
    if (!Number.isFinite(num) || num <= 0) {
      setErr("nominal harus > 0");
      return;
    }
    const payload: SaleMarkPaidPayload = {
      account_id: accountId === "" ? null : Number(accountId),
      paid_amount: num >= Number(remaining) ? undefined : amount,
      payment_method: method,
    };
    setBusy(true);
    try {
      const updated = await api.post<Sale>(`/sales/${sale.id}/pay`, payload);
      onPaid(updated);
    } catch (e) {
      setErr((e as { detail?: string }).detail ?? "gagal");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 px-2 pb-2 pt-10 sm:items-center sm:p-4">
      <form
        onSubmit={submit}
        className="w-full max-w-md rounded-2xl bg-white shadow-xl"
      >
        <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="text-base font-semibold">
            Tandai Lunas #{sale.id}
          </h2>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full p-1 text-slate-500 hover:bg-slate-100"
          >
            ✕
          </button>
        </header>
        <div className="space-y-3 px-4 py-3">
          <p className="text-xs text-slate-600">
            Sisa hutang: <span className="font-semibold">{remaining}</span>
          </p>
          <div>
            <label className="text-xs font-semibold uppercase text-slate-500">
              Metode
            </label>
            <div className="mt-1 grid grid-cols-3 gap-1.5">
              {(["cash", "debit", "credit"] as SalePaymentMethod[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMethod(m)}
                  className={
                    "rounded-lg px-2 py-2 text-xs font-semibold transition " +
                    (method === m
                      ? "bg-brand-600 text-white"
                      : "bg-slate-100 text-slate-600")
                  }
                >
                  {METHOD_LABEL[m]}
                </button>
              ))}
            </div>
          </div>
          {activeAccounts.length > 0 ? (
            <div>
              <label className="text-xs font-semibold uppercase text-slate-500">
                Akun Kas
              </label>
              <select
                value={accountId}
                onChange={(e) =>
                  setAccountId(
                    e.target.value === "" ? "" : Number(e.target.value),
                  )
                }
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
              >
                <option value="">— Pilih akun —</option>
                {activeAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          <div>
            <label className="text-xs font-semibold uppercase text-slate-500">
              Nominal
            </label>
            <input
              type="number"
              inputMode="decimal"
              min="0"
              step="any"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
            />
          </div>
          {err ? (
            <p className="rounded bg-red-50 px-2 py-1 text-xs text-red-700">
              {err}
            </p>
          ) : null}
        </div>
        <footer className="border-t border-slate-100 px-4 py-3">
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white shadow-sm disabled:opacity-60"
          >
            {busy ? "Memproses…" : "Tandai Lunas"}
          </button>
        </footer>
      </form>
    </div>
  );
}
