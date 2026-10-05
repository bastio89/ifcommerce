export function SectionHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description?: string }) {
  return (
    <div className="mx-auto mb-12 max-w-2xl text-center">
      <div className="mb-3 text-xs font-medium uppercase tracking-[0.18em] text-accent-strong">{eyebrow}</div>
      <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{title}</h2>
      {description && <p className="mt-4 text-[15px] leading-relaxed text-secondary">{description}</p>}
    </div>
  );
}
