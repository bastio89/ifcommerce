import { Logo } from "@/components/ui/logo";

export function LegalLayout({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <Logo />
      <h1 className="mt-10 mb-6 text-3xl font-semibold tracking-tight">{title}</h1>
      <div className="flex flex-col gap-4 text-[15px] leading-relaxed text-secondary [&_h2]:mt-6 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-foreground">
        {children}
      </div>
    </div>
  );
}
