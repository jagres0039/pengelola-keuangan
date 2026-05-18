import type { Metadata, Viewport } from "next";
import "./globals.css";
import { RegisterSW } from "@/components/RegisterSW";

export const metadata: Metadata = {
  title: "Pengelola Keuangan",
  description: "Catat pemasukan & pengeluaran harian, OCR struk, multi-user.",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "Pengelola",
    statusBarStyle: "default",
  },
  icons: {
    icon: "/icons/icon-192.png",
    apple: "/icons/icon-192.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#0284c7",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body className="min-h-dvh bg-slate-50 text-slate-900 antialiased">
        {children}
        <RegisterSW />
      </body>
    </html>
  );
}
