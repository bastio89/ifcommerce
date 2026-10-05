import { ButtonLink } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
      <span className="font-mono text-sm text-muted">404</span>
      <h1 className="text-2xl font-semibold">Diese Seite existiert nicht.</h1>
      <ButtonLink href="/" variant="secondary">
        Zur Startseite
      </ButtonLink>
    </main>
  );
}
