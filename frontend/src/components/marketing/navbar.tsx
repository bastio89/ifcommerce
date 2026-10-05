import { ButtonLink } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";

const links = [
  { href: "#demo", label: "Live-Demo" },
  { href: "#so-funktionierts", label: "So funktioniert's" },
  { href: "#preise", label: "Preise" },
  { href: "#integration", label: "Integration" },
  { href: "#faq", label: "FAQ" },
];

export function Navbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/75 backdrop-blur-xl">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Logo />
        <ul className="hidden items-center gap-1 md:flex">
          {links.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="rounded-md px-3 py-2 text-sm text-muted transition-colors hover:text-foreground"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-2">
          <ButtonLink href="/login" variant="ghost" size="sm" className="hidden sm:inline-flex">
            Anmelden
          </ButtonLink>
          <ButtonLink href="/signup" size="sm">
            Kostenlos starten
          </ButtonLink>
        </div>
      </nav>
    </header>
  );
}
