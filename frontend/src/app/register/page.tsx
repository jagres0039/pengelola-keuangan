"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await api.post<{ access_token: string }>("/auth/register", {
        email,
        password,
        first_name: firstName || null,
      });
      setToken(res.access_token);
      router.replace("/dashboard");
    } catch (e: unknown) {
      const msg = (e as { detail?: string }).detail ?? "daftar gagal";
      setErr(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-6">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-bold">Daftar akun baru</h1>
        <p className="text-sm text-slate-500">Gratis. Data lo terisolasi per akun.</p>
      </div>
      <form className="space-y-4" onSubmit={submit}>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Nama</label>
          <input
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-base outline-none focus:border-brand-500"
            placeholder="Nama panggilan"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
          <input
            type="email"
            inputMode="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-base outline-none focus:border-brand-500"
            placeholder="kamu@email.com"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Password</label>
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-base outline-none focus:border-brand-500"
            placeholder="min. 6 karakter"
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
          {busy ? "memproses…" : "Daftar"}
        </button>
        <p className="text-center text-sm text-slate-500">
          Udah punya akun?{" "}
          <Link href="/login" className="font-medium text-brand-600">
            Masuk
          </Link>
        </p>
      </form>
    </main>
  );
}
