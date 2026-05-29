"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import {
  api,
  type InventoryItem,
  type InventoryMovement,
  type MovementReason,
  type UserMe,
} from "@/lib/api";
import { formatMoney, formatDateTime } from "@/lib/format";

const REASON_LABEL: Record<MovementReason, string> = {
  purchase: "Pembelian",
  sale: "Penjualan",
  adjustment: "Penyesuaian",
  initial: "Stok Awal",
};

const REASON_BADGE: Record<MovementReason, string> = {
  purchase: "bg-emerald-100 text-emerald-700",
  sale: "bg-rose-100 text-rose-700",
  adjustment: "bg-slate-100 text-slate-700",
  initial: "bg-indigo-100 text-indigo-700",
};

export default function InventoryPage() {
  return (
    <AuthGuard>{(user) => <InventoryInner user={user} />}</AuthGuard>
  );
}

function InventoryInner({ user }: { user: UserMe }) {
  const router = useRouter();

  useEffect(() => {
    if (user.profile_mode !== "pengusaha") router.replace("/settings");
  }, [user.profile_mode, router]);

  const [items, setItems] = useState<InventoryItem[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);

  const [showItemForm, setShowItemForm] = useState(false);
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null);
  const [historyItem, setHistoryItem] = useState<InventoryItem | null>(null);
  const [movementFor, setMovementFor] = useState<InventoryItem | null>(null);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("q", search.trim());
      if (includeArchived) params.set("include_archived", "true");
      const qs = params.toString();
      const rows = await api.get<InventoryItem[]>(
        `/inventory${qs ? `?${qs}` : ""}`,
      );
      setItems(rows);
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

  async function onArchive(item: InventoryItem) {
    try {
      const updated = await api.post<InventoryItem>(
        `/inventory/${item.id}/${item.archived ? "unarchive" : "archive"}`,
      );
      setItems((xs) => xs.map((x) => (x.id === updated.id ? updated : x)));
    } catch (e) {
      alert((e as { detail?: string }).detail ?? "gagal");
    }
  }

  async function onDelete(item: InventoryItem) {
    if (
      !confirm(
        `Hapus "${item.name}" beserta seluruh riwayatnya? Aksi ini permanen.`,
      )
    )
      return;
    try {
      await api.delete<void>(`/inventory/${item.id}`);
      setItems((xs) => xs.filter((x) => x.id !== item.id));
    } catch (e) {
      alert((e as { detail?: string }).detail ?? "gagal");
    }
  }

  function onSaved(saved: InventoryItem, wasNew: boolean) {
    setShowItemForm(false);
    setEditingItem(null);
    setItems((xs) =>
      wasNew
        ? [...xs, saved].sort((a, b) => a.name.localeCompare(b.name))
        : xs.map((x) => (x.id === saved.id ? saved : x)),
    );
  }

  function onMovementCreated(updated: InventoryItem) {
    setMovementFor(null);
    void load();
    if (historyItem && historyItem.id === updated.id) {
      setHistoryItem(updated);
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
          <h1 className="text-xl font-bold">Stok Barang</h1>
          <p className="text-sm text-slate-500">Inventaris & pergerakan</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setEditingItem(null);
            setShowItemForm(true);
          }}
          className="rounded-xl bg-brand-600 px-3 py-2 text-sm font-medium text-white shadow-sm active:bg-brand-700"
        >
          + Barang
        </button>
      </header>

      <div className="mx-4 mb-2 flex items-center gap-2">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void load();
          }}
          placeholder="Cari nama / SKU…"
          className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-white"
        >
          Cari
        </button>
      </div>

      <label className="mx-4 mb-2 flex items-center gap-2 text-xs text-slate-600">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
        />
        Tampilkan diarsipkan
      </label>

      {error ? (
        <div className="mx-4 my-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <ul className="mx-4 mt-2 space-y-2 pb-4">
        {busy ? (
          <li className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
            memuat…
          </li>
        ) : items.length === 0 ? (
          <li className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
            belum ada barang
          </li>
        ) : (
          items.map((it) => (
            <li
              key={it.id}
              className={
                "rounded-xl bg-white p-3 shadow-sm " +
                (it.archived ? "opacity-60" : "")
              }
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate font-medium">{it.name}</span>
                    {it.sku ? (
                      <span className="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-[10px] font-mono text-slate-600">
                        {it.sku}
                      </span>
                    ) : null}
                    {it.archived ? (
                      <span className="shrink-0 rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-700">
                        Arsip
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-lg font-bold text-slate-900">
                    {it.stock}{" "}
                    <span className="text-sm font-normal text-slate-500">
                      {it.unit}
                    </span>
                  </p>
                  {it.last_cost ? (
                    <p className="text-[10px] text-slate-500">
                      Harga modal {formatMoney(it.last_cost, user.currency)} /{" "}
                      {it.unit}
                    </p>
                  ) : null}
                </div>
                <div className="flex shrink-0 flex-col gap-1">
                  <button
                    type="button"
                    onClick={() => setMovementFor(it)}
                    className="rounded-lg bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700"
                  >
                    +/- Stok
                  </button>
                  <button
                    type="button"
                    onClick={() => setHistoryItem(it)}
                    className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700"
                  >
                    Riwayat
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditingItem(it);
                      setShowItemForm(true);
                    }}
                    className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => void onArchive(it)}
                    className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700"
                  >
                    {it.archived ? "Pulihkan" : "Arsip"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void onDelete(it)}
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

      {showItemForm ? (
        <ItemFormModal
          item={editingItem}
          onClose={() => {
            setShowItemForm(false);
            setEditingItem(null);
          }}
          onSaved={onSaved}
        />
      ) : null}

      {movementFor ? (
        <MovementModal
          item={movementFor}
          onClose={() => setMovementFor(null)}
          onCreated={onMovementCreated}
        />
      ) : null}

      {historyItem ? (
        <HistoryDrawer
          item={historyItem}
          currency={user.currency}
          onClose={() => setHistoryItem(null)}
        />
      ) : null}
    </PageWithNav>
  );
}

function ItemFormModal({
  item,
  onClose,
  onSaved,
}: {
  item: InventoryItem | null;
  onClose: () => void;
  onSaved: (saved: InventoryItem, wasNew: boolean) => void;
}) {
  const isEdit = item !== null;
  const [name, setName] = useState(item?.name ?? "");
  const [sku, setSku] = useState(item?.sku ?? "");
  const [unit, setUnit] = useState(item?.unit ?? "pcs");
  const [initialStock, setInitialStock] = useState("0");
  const [initialCost, setInitialCost] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("nama wajib diisi");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (isEdit && item) {
        const saved = await api.patch<InventoryItem>(`/inventory/${item.id}`, {
          name: name.trim(),
          sku: sku.trim() || undefined,
          unit: unit.trim() || "pcs",
        });
        onSaved(saved, false);
      } else {
        const payload: Record<string, string> = {
          name: name.trim(),
          unit: unit.trim() || "pcs",
        };
        if (sku.trim()) payload.sku = sku.trim();
        if (initialStock && parseFloat(initialStock) > 0)
          payload.initial_stock = initialStock;
        if (initialCost && parseFloat(initialCost) > 0)
          payload.initial_cost = initialCost;
        const saved = await api.post<InventoryItem>("/inventory", payload);
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
            {isEdit ? "Edit Barang" : "Tambah Barang"}
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
              maxLength={128}
              required
              autoFocus
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-medium text-slate-700">SKU</label>
              <input
                type="text"
                value={sku}
                onChange={(e) => setSku(e.target.value)}
                maxLength={64}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                placeholder="opsional"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700">Satuan</label>
              <input
                type="text"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                maxLength={16}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                placeholder="pcs"
              />
            </div>
          </div>
          {!isEdit ? (
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-medium text-slate-700">
                  Stok awal
                </label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={initialStock}
                  onChange={(e) => setInitialStock(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700">
                  Harga modal
                </label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={initialCost}
                  onChange={(e) => setInitialCost(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  placeholder="opsional"
                />
              </div>
            </div>
          ) : null}
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

function MovementModal({
  item,
  onClose,
  onCreated,
}: {
  item: InventoryItem;
  onClose: () => void;
  onCreated: (updated: InventoryItem) => void;
}) {
  const [reason, setReason] = useState<MovementReason>("purchase");
  const [qty, setQty] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isInflow = reason === "purchase" || reason === "initial";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const raw = parseFloat(qty.replace(/[^0-9.]/g, ""));
    if (!Number.isFinite(raw) || raw <= 0) {
      setError("jumlah tidak valid");
      return;
    }
    setBusy(true);
    setError(null);
    const delta = isInflow ? raw : -raw;
    const payload: Record<string, string | number> = {
      qty_delta: String(delta),
      reason,
    };
    if (unitCost.trim()) payload.unit_cost = unitCost.trim();
    if (note.trim()) payload.note = note.trim();
    try {
      await api.post(`/inventory/${item.id}/movements`, payload);
      const updated = await api.get<InventoryItem>(`/inventory/${item.id}`);
      onCreated(updated);
    } catch (e) {
      setError((e as { detail?: string }).detail ?? "gagal");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center">
      <div className="w-full max-w-md rounded-t-2xl bg-white p-4 shadow-xl sm:rounded-2xl">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-bold">Pergerakan Stok</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm text-slate-500"
          >
            ✕
          </button>
        </div>
        <p className="mb-3 text-xs text-slate-500">
          {item.name} — stok sekarang {item.stock} {item.unit}
        </p>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="text-xs font-medium text-slate-700">
              Jenis pergerakan
            </label>
            <div
              role="radiogroup"
              className="mt-1 grid grid-cols-4 gap-1 rounded-xl bg-slate-100 p-1 text-xs"
            >
              {(
                ["purchase", "sale", "adjustment", "initial"] as MovementReason[]
              ).map((r) => (
                <button
                  key={r}
                  type="button"
                  role="radio"
                  aria-checked={reason === r}
                  onClick={() => setReason(r)}
                  className={
                    "rounded-lg px-2 py-2 font-medium " +
                    (reason === r
                      ? "bg-white text-brand-700 shadow-sm"
                      : "text-slate-600")
                  }
                >
                  {REASON_LABEL[r]}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[10px] text-slate-500">
              {isInflow ? "→ stok bertambah" : "→ stok berkurang"}
            </p>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700">Jumlah</label>
            <input
              type="text"
              inputMode="decimal"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              required
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>
          {(reason === "purchase" || reason === "initial") ? (
            <div>
              <label className="text-xs font-medium text-slate-700">
                Harga modal / unit (opsional)
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={unitCost}
                onChange={(e) => setUnitCost(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </div>
          ) : null}
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
              {busy ? "menyimpan…" : "Simpan"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function HistoryDrawer({
  item,
  currency,
  onClose,
}: {
  item: InventoryItem;
  currency: string;
  onClose: () => void;
}) {
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    api
      .get<InventoryMovement[]>(`/inventory/${item.id}/movements`)
      .then(setMovements)
      .catch(() => setMovements([]))
      .finally(() => setBusy(false));
  }, [item.id]);

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center">
      <div className="w-full max-w-md rounded-t-2xl bg-white p-4 shadow-xl sm:rounded-2xl">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-bold">Riwayat — {item.name}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm text-slate-500"
          >
            ✕
          </button>
        </div>
        <ul className="max-h-[60vh] space-y-2 overflow-y-auto">
          {busy ? (
            <li className="rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-400">
              memuat…
            </li>
          ) : movements.length === 0 ? (
            <li className="rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-400">
              belum ada pergerakan
            </li>
          ) : (
            movements.map((m) => {
              const delta = parseFloat(m.qty_delta);
              const positive = delta >= 0;
              return (
                <li key={m.id} className="rounded-xl border border-slate-200 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span
                        className={
                          "rounded-full px-2 py-0.5 text-[10px] font-medium " +
                          REASON_BADGE[m.reason]
                        }
                      >
                        {REASON_LABEL[m.reason]}
                      </span>
                      <p className="mt-1 text-xs text-slate-500">
                        {formatDateTime(m.occurred_at)}
                      </p>
                      {m.note ? (
                        <p className="text-xs text-slate-600">{m.note}</p>
                      ) : null}
                    </div>
                    <div className="text-right">
                      <p
                        className={
                          "text-sm font-semibold " +
                          (positive ? "text-emerald-700" : "text-rose-700")
                        }
                      >
                        {positive ? "+" : ""}
                        {m.qty_delta}
                      </p>
                      {m.unit_cost ? (
                        <p className="text-[10px] text-slate-500">
                          @ {formatMoney(m.unit_cost, currency)}
                        </p>
                      ) : null}
                    </div>
                  </div>
                </li>
              );
            })
          )}
        </ul>
      </div>
    </div>
  );
}
