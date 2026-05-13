"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import { api, setToken, type LinkCode, type UserMe } from "@/lib/api";

export default function SettingsPage() {
  return <AuthGuard>{(user) => <SettingsInner user={user} />}</AuthGuard>;
}

function SettingsInner({ user }: { user: UserMe }) {
  const router = useRouter();
  const [linkCode, setLinkCode] = useState<LinkCode | null>(null);
  const [busy, setBusy] = useState(false);

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
    </PageWithNav>
  );
}
