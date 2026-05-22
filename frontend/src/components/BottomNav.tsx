"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/dashboard", label: "Beranda", icon: "🏠" },
  { href: "/history", label: "Riwayat", icon: "📜" },
  { href: "/add", label: "Tambah", icon: "➕" },
  { href: "/receipt", label: "Struk", icon: "📷" },
  { href: "/settings", label: "Setelan", icon: "⚙️" },
];

export function BottomNav() {
  const pathname = usePathname();
  return (
    <nav className="safe-bottom fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 backdrop-blur">
      <ul className="mx-auto flex max-w-md items-stretch justify-between px-2 pt-1">
        {tabs.map((t) => {
          const active =
            pathname === t.href ||
            (t.href !== "/dashboard" && pathname.startsWith(t.href));
          return (
            <li key={t.href} className="flex-1">
              <Link
                href={t.href}
                className={
                  "flex flex-col items-center gap-0.5 py-2 text-xs " +
                  (active ? "text-brand-600" : "text-slate-500")
                }
              >
                <span className="text-xl leading-none">{t.icon}</span>
                <span>{t.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function PageWithNav({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto min-h-dvh max-w-md pb-24">
      {children}
      <BottomNav />
    </div>
  );
}
