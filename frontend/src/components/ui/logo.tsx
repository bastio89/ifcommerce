import Link from "next/link";

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="flex items-center gap-2 font-semibold tracking-tight" aria-label="DecideCommerce Startseite">
      <svg viewBox="0 0 32 32" className="size-7" aria-hidden>
        <rect width="32" height="32" rx="8" fill="#16171b" stroke="rgb(255 255 255 / 0.14)" />
        <path d="M9 9h6.5a7 7 0 0 1 0 14H9V9Z" stroke="#f4f5f7" strokeWidth="2.5" strokeLinejoin="round" fill="none" />
        <circle cx="22.5" cy="16" r="3" fill="#7c6cf0" />
      </svg>
      <span className="text-[15px]">DecideCommerce</span>
    </Link>
  );
}
