import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatNumber(value: number): string {
  return value.toLocaleString("de-DE");
}

export function formatDateTime(date: Date | null): string {
  if (!date) return "–";
  return new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date);
}
