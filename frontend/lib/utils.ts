import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPrice(price: number, ticker?: string): string {
  const abs = Math.abs(price);
  let decimals = 2;
  if (abs < 0.001) decimals = 6;
  else if (abs < 0.1) decimals = 5;
  else if (abs < 10) decimals = 5;
  else if (abs < 100) decimals = 3;
  else decimals = 2;

  if (ticker) {
    const t = ticker.toUpperCase().replace(/[/\-=X]/g, "");
    const jpyPairs = ["USDJPY","EURJPY","GBPJPY","CADJPY","CHFJPY","AUDJPY","NZDJPY"];
    if (jpyPairs.includes(t)) decimals = 3;
    else if (t.length === 6 && !t.startsWith("XA") && !t.startsWith("US5") && !t.startsWith("US3")) {
      decimals = 5;
    }
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(price);
}

export function formatPct(pct: number, decimals = 1): string {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(decimals)}%`;
}

export function formatPnl(pnl: number): string {
  const sign = pnl >= 0 ? "+" : "";
  return `${sign}${formatPrice(pnl)}`;
}

export function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function directionColor(direction: string): string {
  if (direction === "LONG") return "text-bull";
  if (direction === "SHORT") return "text-bear";
  return "text-neutral";
}

export function directionBg(direction: string): string {
  if (direction === "LONG") return "bg-bull/10 text-bull border-bull/20";
  if (direction === "SHORT") return "bg-bear/10 text-bear border-bear/20";
  return "bg-warn/10 text-warn border-warn/20";
}
