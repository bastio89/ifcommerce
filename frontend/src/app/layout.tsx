import type { Metadata, Viewport } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "DecideCommerce – Semantische If-Statements für deinen Support",
    template: "%s · DecideCommerce",
  },
  description:
    "DecideCommerce klassifiziert Support-Tickets und E-Mails deines Online-Shops in Echtzeit: Kategorie, Dringlichkeit, Storno-Wunsch und Bestellnummer – DSGVO-konform anonymisiert.",
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#08090a",
  colorScheme: "dark",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-dvh font-sans">{children}</body>
    </html>
  );
}
