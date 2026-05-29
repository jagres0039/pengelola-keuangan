"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, History, PlusCircle, ScanLine, Settings } from "lucide-react";

const tabs = [
  { href: "/dashboard", label: "Beranda", Icon: Home },
  { href: "/history", label: "Riwayat", Icon: History },
  { href: "/add", label: "Tambah", Icon: PlusCircle },
  { href: "/receipt", label: "Struk", Icon: ScanLine },
  { href: "/settings", label: "Setelan", Icon: Settings },
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
          const Icon = t.Icon;
          return (
            <li key={t.href} className="flex-1">
              <Link
                href={t.href}
                className={
                  "flex flex-col items-center gap-0.5 py-2 text-xs " +
                  (active ? "text-brand-600" : "text-slate-500")
                }
              >
                <Icon
                  size={22}
                  strokeWidth={active ? 2.5 : 2}
                  className="leading-none"
                />
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
