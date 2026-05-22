"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import { api, type ReceiptOCR, type ReceiptOCRItem, type UserMe } from "@/lib/api";
import { formatMoney } from "@/lib/format";

export default function ReceiptPage() {
  return <AuthGuard>{(user) => <ReceiptInner user={user} />}</AuthGuard>;
}

function ReceiptInner({ user }: { user: UserMe }) {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<ReceiptOCR | null>(null);
  const [editedAmount, setEditedAmount] = useState("");
  const [editedNote, setEditedNote] = useState("");

  function pickImage() {
    fileRef.current?.click();
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setErr(null);
    setResult(null);
    setPreview(URL.createObjectURL(file));
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("image", file);
      const r = await api.postForm<ReceiptOCR>("/receipt/ocr", fd);
      setResult(r);
      setEditedAmount(String(r.total_amount));
      setEditedNote(r.merchant);
    } catch (e: unknown) {
      setErr((e as { detail?: string }).detail ?? "gagal baca struk");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function save() {
    if (!result) return;
    setBusy(true);
    setErr(null);
    try {
      await api.post("/transactions", {
        type: "out",
        amount: editedAmount,
        category_id: result.suggested_category_id,
        note: editedNote.trim() || null,
        occurred_at: result.occurred_at,
        items: result.items.map((it) => ({
          name: it.name,
          qty: it.qty,
          unit_price: it.unit_price,
          subtotal: it.subtotal,
        })),
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
        <h1 className="text-xl font-bold">Foto Struk (OCR)</h1>
        <p className="text-sm text-slate-500">
          Pakai kamera HP, AI auto-extract merchant + total + tanggal + detail item.
        </p>
      </header>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={onFile}
      />

      {!preview ? (
        <div className="mx-4 mt-4">
          <button
            onClick={pickImage}
            className="flex w-full flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-brand-300 bg-white px-4 py-12 text-brand-700 shadow-sm"
          >
            <span className="text-5xl">📷</span>
            <span className="text-base font-semibold">Ambil / pilih foto struk</span>
            <span className="text-xs text-slate-500">jpg / png / heic, maks 8 MB</span>
          </button>
        </div>
      ) : (
        <div className="mx-4 mt-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={preview}
            alt="preview struk"
            className="mx-auto max-h-72 rounded-2xl object-contain shadow"
          />
          <button
            onClick={pickImage}
            className="mt-2 w-full rounded-xl bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm"
          >
            ganti foto
          </button>
        </div>
      )}

      {busy ? (
        <div className="mx-4 mt-4 rounded-xl bg-white px-4 py-3 text-center text-sm text-slate-500 shadow-sm">
          🔍 lagi baca struk… (~3-5 detik)
        </div>
      ) : null}

      {err ? (
        <div className="mx-4 mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      ) : null}

      {result ? (
        <section className="mx-4 mt-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
              Hasil OCR
            </h2>
            <span
              className={
                "rounded-full px-2 py-0.5 text-xs " +
                (result.is_receipt
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-amber-100 text-amber-700")
              }
            >
              {result.is_receipt ? "struk terbaca" : "bukan struk?"}
            </span>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Merchant / Catatan</label>
            <input
              value={editedNote}
              onChange={(e) => setEditedNote(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-base outline-none focus:border-brand-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Total</label>
            <input
              inputMode="decimal"
              value={editedAmount}
              onChange={(e) => setEditedAmount(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-base font-semibold outline-none focus:border-brand-500"
            />
            <p className="mt-1 text-xs text-slate-400">
              {formatMoney(editedAmount || "0", user.currency)}
            </p>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Kategori (saran AI)</label>
            <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm">
              {result.suggested_category || "Lainnya"}{" "}
              {result.suggested_category_id ? (
                <span className="text-emerald-600">✓</span>
              ) : (
                <span className="text-amber-600">(akan dibuat baru)</span>
              )}
            </p>
          </div>
          {result.items.length > 0 ? (
            <div>
              <label className="mb-1 block text-xs text-slate-500">
                Detail item ({result.items.length})
              </label>
              <ul className="space-y-1.5 rounded-xl bg-slate-50 px-3 py-2">
                {result.items.map((it, i) => (
                  <ItemRow key={i} item={it} currency={user.currency} />
                ))}
              </ul>
              <p className="mt-1 text-xs text-slate-400">
                Item-item ini akan disimpan bareng transaksi.
              </p>
            </div>
          ) : null}
          <button
            onClick={save}
            disabled={busy}
            className="w-full rounded-xl bg-brand-600 px-4 py-3 text-base font-semibold text-white shadow disabled:opacity-60"
          >
            {busy ? "menyimpan…" : "Simpan sebagai pengeluaran"}
          </button>
        </section>
      ) : null}
    </PageWithNav>
  );
}

function ItemRow({ item, currency }: { item: ReceiptOCRItem; currency: string }) {
  const qty = Number(item.qty);
  const showQty = Number.isFinite(qty) && qty !== 1;
  const unit = item.unit_price ? Number(item.unit_price) : null;
  const showUnit = unit !== null && Number.isFinite(unit) && unit > 0;
  return (
    <li className="flex items-start justify-between gap-2 text-sm">
      <div className="min-w-0 flex-1">
        <p className="truncate text-slate-700">{item.name}</p>
        {showQty || showUnit ? (
          <p className="text-xs text-slate-400">
            {showQty ? `${formatQty(item.qty)}×` : ""}
            {showUnit && item.unit_price ? formatMoney(item.unit_price, currency) : ""}
          </p>
        ) : null}
      </div>
      <span className="shrink-0 font-medium text-slate-700">
        {formatMoney(item.subtotal, currency)}
      </span>
    </li>
  );
}

function formatQty(qty: string): string {
  const n = Number(qty);
  if (!Number.isFinite(n)) return qty;
  if (Number.isInteger(n)) return String(n);
  return n.toLocaleString("id-ID", { maximumFractionDigits: 3 });
}
