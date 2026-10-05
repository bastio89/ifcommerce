import Link from "next/link";

import { ButtonLink } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";

export function FinalCta() {
  return (
    <section className="relative overflow-hidden border-t border-border">
      <div className="glow pointer-events-none absolute inset-0" aria-hidden />
      <div className="relative mx-auto flex max-w-3xl flex-col items-center px-4 py-24 text-center sm:px-6">
        <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          Lass deinen Support entscheiden, bevor jemand liest.
        </h2>
        <p className="mt-4 max-w-xl text-[15px] text-secondary">
          Konto anlegen, API-Key erzeugen, Widget einbinden. Das erste Ticket ist in fünf Minuten klassifiziert.
        </p>
        <ButtonLink href="/signup" size="lg" className="mt-8">
          Jetzt kostenlos starten
        </ButtonLink>
      </div>
    </section>
  );
}

export function Footer({ apiUrl }: { apiUrl: string }) {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 text-sm text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex flex-col gap-2">
          <Logo />
          <span>© {new Date().getFullYear()} DecideCommerce. Made for E-Commerce teams.</span>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-2">
          <a href={`${apiUrl}/docs`} className="hover:text-foreground">
            API-Referenz
          </a>
          <Link href="/impressum" className="hover:text-foreground">
            Impressum
          </Link>
          <Link href="/datenschutz" className="hover:text-foreground">
            Datenschutz
          </Link>
        </nav>
      </div>
    </footer>
  );
}
