"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import {
  api,
  getToken,
  setToken,
  type ImportApplyResponse,
  type ImportPreviewResponse,
  type LinkCode,
  type ProfileMode,
  type SubscriptionStatus,
  type UserMe,
} from "@/lib/api";
import { formatMoney } from "@/lib/format";

export default function SettingsPage() {
  return <AuthGuard>{(user) => <SettingsInner user={user} />}</AuthGuard>;
}

function SettingsInner({ user }: { user: UserMe }) {
  const router = useRouter();
  const [linkCode, setLinkCode] = useState<LinkCode | null>(null);
  const [busy, setBusy] = useState(false);

  // Low balance threshold form
  const [threshold, setThreshold] = useState<string>(
    String(Math.round(Number(user.low_balance_threshold))),
  );
  const [thBusy, setThBusy] = useState(false);
  const [thMsg, setThMsg] = useState<string | null>(null);
  const [thErr, setThErr] = useState<string | null>(null);

  // Profile mode toggle (standar | pengusaha)
  const [profileMode, setProfileMode] = useState<ProfileMode>(user.profile_mode);
  const [pmBusy, setPmBusy] = useState(false);
  const [pmErr, setPmErr] = useState<string | null>(null);

  const [sub, setSub] = useState<SubscriptionStatus | null>(null);
  useEffect(() => {
    api.get<SubscriptionStatus>("/billing/status").then(setSub).catch(() => {
      /* non-fatal */
    });
  }, []);

  // Excel export / import
  const [exportBusy, setExportBusy] = useState(false);
  const [exportErr, setExportErr] = useState<string | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [importErr, setImportErr] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [applyMsg, setApplyMsg] = useState<string | null>(null);

  async function issueLinkCode() {
    setBusy(true);
    try {
      const c = await api.post<LinkCode>("/auth/link-code");
      setLinkCode(c);
    } catch (e) {
      alert((e as { detail?: string }).detail ?? "gagal generate kode");
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    setToken(null);
    router.replace("/login");
  }

  async function changeProfileMode(next: ProfileMode) {
    if (next === profileMode || pmBusy) return;
    const previous = profileMode;
    setProfileMode(next);
    setPmBusy(true);
    setPmErr(null);
    try {
      await api.patch<UserMe>("/auth/me", { profile_mode: next });
    } catch (e) {
      setProfileMode(previous);
      setPmErr((e as { detail?: string }).detail ?? "gagal ganti mode");
    } finally {
      setPmBusy(false);
    }
  }

  async function saveThreshold() {
    setThBusy(true);
    setThMsg(null);
    setThErr(null);
    try {
      const value = Number(threshold);
      if (!Number.isFinite(value) || value < 0) {
        throw { detail: "ambang harus angka >= 0" };
      }
      await api.patch<UserMe>("/auth/me", { low_balance_threshold: String(value) });
      setThMsg("Ambang disimpan.");
    } catch (e) {
      setThErr((e as { detail?: string }).detail ?? "gagal simpan");
    } finally {
      setThBusy(false);
    }
  }

  async function exportXlsx() {
    setExportBusy(true);
    setExportErr(null);
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const resp = await fetch("/api/export/xlsx", { headers });
      if (!resp.ok) {
        let detail = `request failed (${resp.status})`;
        try {
          const j = await resp.json();
          if (typeof j.detail === "string") detail = j.detail;
        } catch {
          /* ignore */
        }
        throw { detail };
      }
      const blob = await resp.blob();
      const cd = resp.headers.get("content-disposition") || "";
      const match = cd.match(/filename="([^"]+)"/);
      const name = match ? match[1] : "export.xlsx";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setExportErr((e as { detail?: string }).detail ?? "gagal export");
    } finally {
      setExportBusy(false);
    }
  }

  async function onImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImportBusy(true);
    setImportErr(null);
    setApplyMsg(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const resp = await api.postForm<ImportPreviewResponse>(
        "/import/preview",
        form,
      );
      setPreview(resp);
    } catch (err) {
      setImportErr((err as { detail?: string }).detail ?? "gagal preview");
    } finally {
      setImportBusy(false);
    }
  }

  async function confirmImport() {
    if (!preview) return;
    setImportBusy(true);
    setImportErr(null);
    try {
      const result = await api.post<ImportApplyResponse>("/import/apply", {
        plan_id: preview.plan_id,
      });
      setApplyMsg(
        `Sukses: +${result.created} ditambah, ${result.updated} diubah, ${result.deleted} dihapus.`,
      );
      setPreview(null);
    } catch (err) {
      setImportErr((err as { detail?: string }).detail ?? "gagal apply");
    } finally {
      setImportBusy(false);
    }
  }

  return (
    <PageWithNav>
      <header className="safe-top px-4 pb-2 pt-4">
        <h1 className="text-xl font-bold">Setelan</h1>
      </header>

      <section className="mx-4 mt-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Akun
        </h2>
        <div className="text-sm">
          <p className="text-slate-500">Email</p>
          <p className="font-medium">{user.email ?? "—"}</p>
        </div>
        {user.first_name ? (
          <div className="text-sm">
            <p className="text-slate-500">Nama</p>
            <p className="font-medium">{user.first_name}</p>
          </div>
        ) : null}
        <div className="text-sm">
          <p className="text-slate-500">Mata uang</p>
          <p className="font-medium">{user.currency}</p>
        </div>
        <div className="text-sm">
          <p className="text-slate-500">Timezone</p>
          <p className="font-medium">{user.timezone}</p>
        </div>
      </section>

      <section className="mx-4 mt-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Mode Profil
        </h2>
        <p className="text-xs text-slate-500">
          Standar: catat pemasukan & pengeluaran biasa. Pengusaha: tambah fitur
          piutang, hutang, stok, dan laporan keuangan ala bisnis.
        </p>
        <div
          role="radiogroup"
          aria-label="Mode Profil"
          className="grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-1"
        >
          <button
            type="button"
            role="radio"
            aria-checked={profileMode === "standar"}
            disabled={pmBusy}
            onClick={() => changeProfileMode("standar")}
            className={
              "rounded-lg px-4 py-2 text-sm font-semibold transition disabled:opacity-60 " +
              (profileMode === "standar"
                ? "bg-white text-slate-900 shadow"
                : "text-slate-500 hover:text-slate-700")
            }
          >
            Standar
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={profileMode === "pengusaha"}
            disabled={pmBusy}
            onClick={() => changeProfileMode("pengusaha")}
            className={
              "rounded-lg px-4 py-2 text-sm font-semibold transition disabled:opacity-60 " +
              (profileMode === "pengusaha"
                ? "bg-white text-slate-900 shadow"
                : "text-slate-500 hover:text-slate-700")
            }
          >
            Pengusaha
          </button>
        </div>
        {pmErr ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{pmErr}</p>
        ) : null}
      </section>

      {profileMode === "pengusaha" ? (
        <section className="mx-4 mt-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Pengusaha
          </h2>
          <p className="text-xs text-slate-500">
            Fitur tambahan untuk pencatatan keuangan usaha.
          </p>
          <Link
            href="/contacts"
            className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3 text-sm font-medium text-slate-800 hover:bg-slate-100"
          >
            <span>📒 Direktori (Customer & Supplier)</span>
            <span className="text-slate-400">›</span>
          </Link>
          <Link
            href="/accounts"
            className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3 text-sm font-medium text-slate-800 hover:bg-slate-100"
          >
            <span>💼 Akun Kas (Multi-Akun + Transfer)</span>
            <span className="text-slate-400">›</span>
          </Link>
          <Link
            href="/inventory"
            className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3 text-sm font-medium text-slate-800 hover:bg-slate-100"
          >
            <span>📦 Stok Barang (Inventaris)</span>
            <span className="text-slate-400">›</span>
          </Link>
        </section>
      ) : null}

      <section className="mx-4 mt-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Subscription
          </h2>
          {sub ? <SubBadge sub={sub} /> : null}
        </div>
        <p className="text-xs text-slate-500">
          Rp 5.000 / 30 hari. 14 hari pertama gratis. Setelah masa berakhir, akun
          jadi read-only (lihat data lama OK, tapi gak bisa catat baru) sampai
          perpanjang.
        </p>
        <Link
          href="/billing"
          className="block w-full rounded-xl bg-brand-600 px-4 py-3 text-center text-sm font-semibold text-white shadow"
        >
          {sub?.state === "expired"
            ? "Perpanjang sekarang"
            : sub?.has_pending_payment
              ? "Lihat status pembayaran"
              : "Kelola subscription"}
        </Link>
        {user.is_admin ? (
          <Link
            href="/admin/payments"
            className="block w-full rounded-xl bg-slate-100 px-4 py-3 text-center text-sm font-semibold text-slate-700"
          >
            🛡️ Admin: verifikasi pembayaran
          </Link>
        ) : null}
      </section>

      <section className="mx-4 mt-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Pemberitahuan saldo
        </h2>
        <p className="text-xs text-slate-500">
          Banner muncul di Dashboard kalau saldo bulan ini di bawah ambang ini.
        </p>
        <label className="block text-sm">
          <span className="text-slate-500">Ambang (Rp)</span>
          <input
            type="number"
            min={0}
            step={1000}
            inputMode="numeric"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
          />
        </label>
        {thErr ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{thErr}</p>
        ) : null}
        {thMsg ? (
          <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {thMsg}
          </p>
        ) : null}
        <button
          onClick={saveThreshold}
          disabled={thBusy}
          className="w-full rounded-xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white shadow disabled:opacity-60"
        >
          {thBusy ? "menyimpan…" : "Simpan ambang"}
        </button>
      </section>

      <section className="mx-4 mt-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Data (Excel)
        </h2>
        <p className="text-xs text-slate-500">
          Export semua transaksi bulan ini ke .xlsx, atau import file .xlsx hasil
          export. Import bakal nampilin preview dulu sebelum dieksekusi.
        </p>
        {exportErr ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {exportErr}
          </p>
        ) : null}
        {importErr ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {importErr}
          </p>
        ) : null}
        {applyMsg ? (
          <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {applyMsg}
          </p>
        ) : null}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={exportXlsx}
            disabled={exportBusy}
            className="rounded-xl bg-emerald-100 px-4 py-3 text-sm font-semibold text-emerald-700 disabled:opacity-60"
          >
            {exportBusy ? "menyiapkan…" : "📥 Export Excel"}
          </button>
          <label
            className={
              "cursor-pointer rounded-xl bg-blue-100 px-4 py-3 text-center text-sm font-semibold text-blue-700 " +
              (importBusy ? "opacity-60" : "")
            }
          >
            {importBusy ? "memproses…" : "📤 Import Excel"}
            <input
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="hidden"
              onChange={onImportFile}
              disabled={importBusy}
            />
          </label>
        </div>
      </section>

      <section className="mx-4 mt-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Hubungkan ke Telegram
        </h2>
        <p className="text-sm text-slate-600">
          Buka bot{" "}
          <a
            href="https://t.me/pengelolakeuangan0039_bot"
            target="_blank"
            rel="noreferrer"
            className="text-brand-600 underline"
          >
            @pengelolakeuangan0039_bot
          </a>{" "}
          terus kirim <code className="rounded bg-slate-100 px-1">/link KODE</code> di
          bawah ini.
        </p>
        {user.telegram_linked ? (
          <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            ✅ Sudah ditautkan ke chat Telegram.
          </p>
        ) : linkCode ? (
          <div className="rounded-lg bg-brand-50 px-3 py-3 text-center">
            <p className="text-xs text-slate-500">Kirim ke bot:</p>
            <p className="font-mono text-2xl font-bold tracking-widest text-brand-700">
              /link {linkCode.code}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Berlaku sampai{" "}
              {new Date(linkCode.expires_at).toLocaleTimeString("id-ID")}
            </p>
          </div>
        ) : (
          <button
            onClick={issueLinkCode}
            disabled={busy}
            className="w-full rounded-xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white shadow disabled:opacity-60"
          >
            {busy ? "memproses…" : "Generate kode link"}
          </button>
        )}
      </section>

      <section className="mx-4 mt-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Sesi
        </h2>
        <button
          onClick={logout}
          className="w-full rounded-xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700"
        >
          Keluar
        </button>
      </section>

      {preview ? (
        <ImportPreviewModal
          preview={preview}
          currency={user.currency}
          busy={importBusy}
          onCancel={() => setPreview(null)}
          onConfirm={confirmImport}
        />
      ) : null}
    </PageWithNav>
  );
}

function ImportPreviewModal({
  preview,
  currency,
  busy,
  onCancel,
  onConfirm,
}: {
  preview: ImportPreviewResponse;
  currency: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const total =
    preview.to_create.length + preview.to_update.length + preview.to_delete.length;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center">
      <div className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-t-2xl bg-white p-4 shadow-xl sm:rounded-2xl">
        <h3 className="text-lg font-bold">Preview Import</h3>
        <p className="mt-1 text-sm text-slate-600">
          {total} perubahan akan dieksekusi. Cek dulu sebelum konfirmasi.
        </p>

        {preview.errors.length > 0 ? (
          <div className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
            <p className="font-semibold">Beberapa baris gagal diparsing:</p>
            <ul className="ml-4 list-disc">
              {preview.errors.slice(0, 5).map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <PreviewGroup
          title="Akan ditambah"
          color="emerald"
          rows={preview.to_create}
          currency={currency}
        />
        <PreviewGroup
          title="Akan diubah"
          color="amber"
          rows={preview.to_update}
          currency={currency}
        />
        <PreviewGroup
          title="Akan dihapus"
          color="rose"
          rows={preview.to_delete}
          currency={currency}
        />

        <div className="mt-4 flex gap-2">
          <button
            onClick={onCancel}
            disabled={busy}
            className="flex-1 rounded-xl bg-slate-100 px-4 py-3 text-sm font-semibold text-slate-700 disabled:opacity-60"
          >
            Batal
          </button>
          <button
            onClick={onConfirm}
            disabled={busy || total === 0}
            className="flex-1 rounded-xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
          >
            {busy ? "menjalankan…" : "Konfirmasi"}
          </button>
        </div>
      </div>
    </div>
  );
}

function PreviewGroup({
  title,
  color,
  rows,
  currency,
}: {
  title: string;
  color: "emerald" | "amber" | "rose";
  rows: ImportPreviewResponse["to_create"];
  currency: string;
}) {
  if (rows.length === 0) return null;
  const palette = {
    emerald: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    rose: "bg-rose-50 text-rose-700",
  }[color];
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {title} ({rows.length})
      </p>
      <ul className="mt-1 space-y-1">
        {rows.slice(0, 20).map((r, i) => (
          <li
            key={`${title}-${i}`}
            className={"flex items-center justify-between rounded-md px-2 py-1.5 text-xs " + palette}
          >
            <span className="truncate">
              <span className="font-mono mr-1">{r.type}</span>
              {r.category_name}
              {r.note ? ` — ${r.note}` : ""}
            </span>
            <span className="ml-2 shrink-0 font-semibold">
              {formatMoney(r.amount, currency)}
            </span>
          </li>
        ))}
        {rows.length > 20 ? (
          <li className="text-center text-xs text-slate-400">
            …dan {rows.length - 20} lagi
          </li>
        ) : null}
      </ul>
    </div>
  );
}

function SubBadge({ sub }: { sub: SubscriptionStatus }) {
  const tone =
    sub.state === "active"
      ? "bg-emerald-100 text-emerald-700"
      : sub.state === "trial"
        ? "bg-sky-100 text-sky-700"
        : "bg-rose-100 text-rose-700";
  const label =
    sub.state === "active"
      ? `Aktif · ${sub.days_left}h`
      : sub.state === "trial"
        ? `Trial · ${sub.days_left}h`
        : "Expired";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${tone}`}>
      {label}
    </span>
  );
}
