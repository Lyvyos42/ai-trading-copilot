/**
 * MonolithShell — the GOLD MONOLITH workspace frame shared by the Strategy
 * Truth Lab and the Live Terminal: slim side rail, scanline overlay and the
 * status bar. The app's own navbar and market ticker stay above it.
 *
 * Fonts are loaded with next/font so Manrope and JetBrains Mono ship only
 * with these two routes and no other page changes. They are self-hosted
 * (app/fonts, latin variable WOFF2 + OFL licences): next/font/google in
 * Next 14.2.5 crashed the Vercel build while fetching them.
 */
import Link from "next/link";
import localFont from "next/font/local";
import type { ComponentType, CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/utils";
import { RESEARCH_PUBLIC } from "@/lib/visibility";
import { IconBands, IconFlask } from "@/components/icons/GeoIcons";

const manrope = localFont({
  src: "../../app/fonts/manrope-latin-var.woff2",
  weight: "400 800",
  variable: "--font-manrope",
  display: "swap",
});

const jbmono = localFont({
  src: "../../app/fonts/jetbrains-mono-latin-var.woff2",
  weight: "400 700",
  variable: "--font-jbmono",
  display: "swap",
});

type IconType = ComponentType<{ size?: number; strokeWidth?: number; className?: string; style?: CSSProperties }>;

export interface RailSection {
  href: string;
  label: string;
  title: string;
  Icon: IconType;
}

const PAGES: { key: "lab" | "terminal"; href: string; label: string; title: string; Icon: IconType }[] = [
  ...(RESEARCH_PUBLIC ? [{ key: "lab" as const, href: "/lab", label: "LAB", title: "Strategy Truth Lab", Icon: IconFlask }] : []),
  { key: "terminal", href: "/terminal", label: "TERM", title: "Live Terminal", Icon: IconBands },
];

export function MonolithShell({
  active,
  sections = [],
  status = [],
  children,
}: {
  active: "lab" | "terminal";
  /** In-page jump targets, shown in the rail under the two pages. */
  sections?: RailSection[];
  /** Short facts for the status bar (hidden on small screens). */
  status?: string[];
  children: ReactNode;
}) {
  return (
    <div className={cn("monolith flex min-h-[calc(100dvh-var(--chrome-h))]", manrope.variable, jbmono.variable)}>
      <div className="m-scanline" aria-hidden="true" />

      <a
        href="#m-main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-14 focus:top-2 focus:z-50 focus:bg-primary focus:px-3 focus:py-2 focus:text-[11px] focus:font-extrabold focus:uppercase focus:tracking-[0.18em] focus:text-black"
      >
        Skip to content
      </a>

      {/* Side rail — desktop and tablet */}
      <nav
        aria-label="Workspace"
        className="sticky top-[var(--chrome-h)] z-20 hidden h-[calc(100dvh-var(--chrome-h))] w-12 shrink-0 flex-col items-center border-r border-border bg-surface-0 py-2 md:flex"
      >
        {PAGES.map(({ key, href, label, title, Icon }) => {
          const on = key === active;
          return (
            <Link
              key={key}
              href={href}
              title={title}
              aria-label={title}
              aria-current={on ? "page" : undefined}
              className={cn(
                "flex w-full flex-col items-center gap-1 py-3 transition-colors",
                on
                  ? "border-r border-primary bg-primary/5 text-primary shadow-[inset_-4px_0_12px_-6px_hsl(38_78%_55%/0.3)]"
                  : "text-muted-foreground hover:text-primary",
              )}
            >
              <Icon size={18} strokeWidth={on ? 1.8 : 1.4} />
              <span className="text-[9px] font-extrabold uppercase leading-none tracking-[0.04em]">{label}</span>
            </Link>
          );
        })}

        {sections.length > 0 && <div className="my-2 h-px w-6 bg-border-strong" aria-hidden="true" />}

        {sections.map(({ href, label, title, Icon }) => (
          <a
            key={href}
            href={href}
            title={title}
            aria-label={`Jump to ${title}`}
            className="flex w-full flex-col items-center gap-1 py-2.5 text-muted-foreground transition-colors hover:text-primary"
          >
            <Icon size={16} strokeWidth={1.4} />
            <span className="text-[9px] font-extrabold uppercase leading-none tracking-[0.04em]">{label}</span>
          </a>
        ))}
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Page switch — phones */}
        <nav aria-label="Workspace" className="grid grid-cols-2 border-b border-border md:hidden">
          {PAGES.map(({ key, href, title, Icon }) => {
            const on = key === active;
            return (
              <Link
                key={key}
                href={href}
                aria-current={on ? "page" : undefined}
                className={cn(
                  "flex min-h-[44px] items-center justify-center gap-2 border-b text-[11px] font-extrabold uppercase tracking-[0.16em]",
                  on ? "border-primary bg-primary/5 text-primary" : "border-transparent text-muted-foreground",
                )}
              >
                <Icon size={14} />
                {key === "lab" ? "Truth Lab" : "Terminal"}
                <span className="sr-only">{title}</span>
              </Link>
            );
          })}
        </nav>

        <div id="m-main" className="min-w-0 flex-1">
          {children}
        </div>

        {/* Status bar */}
        <footer className="sticky bottom-0 z-20 flex h-[var(--m-status-h)] items-center justify-between gap-4 border-t border-border bg-black px-3 md:px-4">
          <div className="flex min-w-0 items-center gap-4">
            <span className="flex shrink-0 items-center gap-1.5">
              <span className="m-dot" aria-hidden="true" />
              <span className="m-num text-[10px] font-bold uppercase italic tracking-[0.18em] text-primary">Demo data</span>
            </span>
            <span className="hidden min-w-0 items-center gap-4 border-l border-border-strong pl-4 lg:flex">
              {status.map((s) => (
                <span key={s} className="m-num truncate text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  {s}
                </span>
              ))}
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <span className="m-num hidden text-[10px] uppercase tracking-[0.14em] text-muted-foreground sm:inline">
              Rule-based tests
            </span>
            <span className="m-num border border-primary/40 bg-primary/10 px-2 text-[10px] font-bold uppercase leading-[16px] tracking-[0.16em] text-primary">
              Information, not advice.
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
