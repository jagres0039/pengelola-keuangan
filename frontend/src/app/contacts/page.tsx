"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { PageWithNav } from "@/components/BottomNav";
import {
  api,
  type Contact,
  type ContactCreatePayload,
  type ContactKind,
  type UserMe,
} from "@/lib/api";

const KIND_LABEL: Record<ContactKind, string> = {
  customer: "Customer",
  supplier: "Supplier",
  both: "Customer & Supplier",
};

const KIND_BADGE: Record<ContactKind, string> = {
  customer: "bg-emerald-100 text-emerald-700",
  supplier: "bg-amber-100 text-amber-700",
  both: "bg-indigo-100 text-indigo-700",
};

export default function ContactsPage() {
  return (
    <AuthGuard>
      {(user) => <ContactsInner user={user} />}
    </AuthGuard>
  );
}

type Filter = "all" | ContactKind;

function ContactsInner({ user }: { user: UserMe }) {
  const router = useRouter();

  useEffect(() => {
    if (user.profile_mode !== "pengusaha") {
      router.replace("/settings");
    }
  }, [user.profile_mode, router]);

  const [rows, setRows] = useState<Contact[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editing, setEditing] = useState<Contact | null>(null);
  const [showForm, setShowForm] = useState(false);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filter !== "all") params.set("kind", filter);
      if (search.trim()) params.set("q", search.trim());
      if (includeArchived) params.set("include_archived", "true");
      const qs = params.toString();
      const r = await api.get<Contact[]>(`/contacts${qs ? `?${qs}` : ""}`);
      setRows(r);
    } catch (e) {
      setError((e as { detail?: string }).detail ?? "gagal load");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (user.profile_mode === "pengusaha") {
      void load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, includeArchived, user.profile_mode]);

  function startCreate() {
    setEditing(null);
    setShowForm(true);
  }

  function startEdit(c: Contact) {
    setEditing(c);
    setShowForm(true);
  }

  async function onArchive(c: Contact) {
    try {
      const updated = await api.post<Contact>(
        `/contacts/${c.id}/${c.archived ? "unarchive" : "archive"}`,
      );
      setRows((rs) => rs.map((r) => (r.id === updated.id ? updated : r)));
    } catch (e) {
      alert((e as { detail?: string }).detail ?? "gagal");
    }
  }

  async function onDelete(c: Contact) {
    if (!confirm(`Hapus kontak "${c.name}"? Aksi ini permanen.`)) return;
    try {
      await api.delete<void>(`/contacts/${c.id}`);
      setRows((rs) => rs.filter((r) => r.id !== c.id));
    } catch (e) {
      alert((e as { detail?: string }).detail ?? "gagal hapus");
    }
  }

  function onSaved(saved: Contact, wasNew: boolean) {
    setShowForm(false);
    setEditing(null);
    setRows((rs) => {
      if (wasNew) return [saved, ...rs].sort((a, b) => a.name.localeCompare(b.name));
      return rs.map((r) => (r.id === saved.id ? saved : r));
    });
  }

  if (user.profile_mode !== "pengusaha") {
    return (
      <PageWithNav>
        <p className="px-4 py-6 text-sm text-slate-500">
          Mode profil bukan Pengusaha. Redirect…
        </p>
      </PageWithNav>
    );
  }

  return (
    <PageWithNav>
      <header className="safe-top flex items-center justify-between px-4 pb-2 pt-4">
        <div>
          <h1 className="text-xl font-bold">Direktori</h1>
          <p className="text-sm text-slate-500">Customer & Supplier</p>
        </div>
        <button
          type="button"
          onClick={startCreate}
          className="rounded-xl bg-brand-600 px-3 py-2 text-sm font-medium text-white shadow-sm active:bg-brand-700"
        >
          + Tambah
        </button>
      </header>

      <div className="mx-4 mb-2 flex gap-1 rounded-xl bg-slate-100 p-1 text-xs">
        {(["all", "customer", "supplier", "both"] as const).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={
              "flex-1 rounded-lg px-2 py-1.5 font-medium " +
              (filter === f
                ? "bg-white text-brand-700 shadow-sm"
                : "text-slate-600")
            }
          >
            {f === "all" ? "Semua" : KIND_LABEL[f]}
          </button>
        ))}
      </div>

      <div className="mx-4 mb-2 flex items-center gap-2">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void load();
          }}
          placeholder="Cari nama…"
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
        ) : rows.length === 0 ? (
          <li className="rounded-xl bg-white px-4 py-6 text-center text-sm text-slate-400 shadow-sm">
            belum ada kontak
          </li>
        ) : (
          rows.map((c) => (
            <li
              key={c.id}
              className={
                "rounded-xl bg-white p-3 shadow-sm " +
                (c.archived ? "opacity-60" : "")
              }
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{c.name}</span>
                    <span
                      className={
                        "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium " +
                        KIND_BADGE[c.kind]
                      }
                    >
                      {KIND_LABEL[c.kind]}
                    </span>
                    {c.archived ? (
                      <span className="shrink-0 rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-700">
                        Arsip
                      </span>
                    ) : null}
                  </div>
                  {c.phone ? (
                    <a
                      href={`tel:${c.phone}`}
                      className="block text-xs text-brand-600 hover:underline"
                    >
                      {c.phone}
                    </a>
                  ) : null}
                  {c.address ? (
                    <p className="text-xs text-slate-500">{c.address}</p>
                  ) : null}
                  {c.notes ? (
                    <p className="mt-1 text-xs text-slate-600">{c.notes}</p>
                  ) : null}
                </div>
                <div className="flex shrink-0 flex-col gap-1">
                  <button
                    type="button"
                    onClick={() => startEdit(c)}
                    className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => void onArchive(c)}
                    className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700"
                  >
                    {c.archived ? "Pulihkan" : "Arsipkan"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void onDelete(c)}
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

      {showForm ? (
        <ContactFormModal
          contact={editing}
          onClose={() => {
            setShowForm(false);
            setEditing(null);
          }}
          onSaved={onSaved}
        />
      ) : null}
    </PageWithNav>
  );
}

function ContactFormModal({
  contact,
  onClose,
  onSaved,
}: {
  contact: Contact | null;
  onClose: () => void;
  onSaved: (saved: Contact, wasNew: boolean) => void;
}) {
  const isEdit = contact !== null;
  const [name, setName] = useState(contact?.name ?? "");
  const [kind, setKind] = useState<ContactKind>(contact?.kind ?? "customer");
  const [phone, setPhone] = useState(contact?.phone ?? "");
  const [address, setAddress] = useState(contact?.address ?? "");
  const [notes, setNotes] = useState(contact?.notes ?? "");
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
    const payload: ContactCreatePayload = {
      name: name.trim(),
      kind,
      phone: phone.trim() || undefined,
      address: address.trim() || undefined,
      notes: notes.trim() || undefined,
    };
    try {
      if (isEdit && contact) {
        const saved = await api.patch<Contact>(`/contacts/${contact.id}`, payload);
        onSaved(saved, false);
      } else {
        const saved = await api.post<Contact>("/contacts", payload);
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
            {isEdit ? "Edit Kontak" : "Tambah Kontak"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm text-slate-500"
            aria-label="Tutup"
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
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              autoFocus
            />
          </div>

          <div>
            <label className="text-xs font-medium text-slate-700">Tipe</label>
            <div
              role="radiogroup"
              aria-label="Tipe kontak"
              className="mt-1 grid grid-cols-3 gap-1 rounded-xl bg-slate-100 p-1 text-xs"
            >
              {(["customer", "supplier", "both"] as const).map((k) => (
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
                  {KIND_LABEL[k]}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-slate-700">Telepon / WA</label>
            <input
              type="tel"
              inputMode="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              maxLength={32}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="081234567890"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-slate-700">Alamat</label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              maxLength={255}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-slate-700">Catatan</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={500}
              rows={2}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>

          {error ? (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
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
