/**
 * MONOLITH primitives shared by the Truth Lab and the Live Terminal.
 */
import type { ComponentType, CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { VerdictLabel } from "@/lib/terminal-api";
import {
  IconVerdictFail,
  IconVerdictNear,
  IconVerdictPass,
  IconVerdictReal,
} from "@/components/icons/GeoIcons";

type IconType = ComponentType<{ size?: number; strokeWidth?: number; className?: string; style?: CSSProperties }>;

/**
 * One entry per verdict. Colour is never the only cue: each verdict has its
 * own icon shape and always carries its label in words.
 */
export const VERDICT_META: Record<
  VerdictLabel,
  { Icon: IconType; text: string; border: string; bg: string; bar: string; gloss: string }
> = {
  PASS: {
    Icon: IconVerdictPass,
    text: "text-primary",
    border: "border-primary/50",
    bg: "bg-primary/[0.07]",
    bar: "bg-primary",
    gloss: "Held up on the sealed years, after the luck correction and the direction check.",
  },
  "NEAR MISS": {
    Icon: IconVerdictNear,
    text: "text-warn",
    border: "border-warn/50",
    bg: "bg-warn/[0.06]",
    bar: "bg-warn",
    gloss: "Positive on the sealed years, but not strong enough to rule out luck.",
  },
  "REAL BUT NOT TRADABLE": {
    Icon: IconVerdictReal,
    text: "text-foreground",
    border: "border-foreground/40",
    bg: "bg-foreground/[0.04]",
    bar: "bg-foreground",
    gloss: "The pattern exists in the data. A trade built on it does not make money.",
  },
  FAILED: {
    Icon: IconVerdictFail,
    text: "text-bear",
    border: "border-bear/50",
    bg: "bg-bear/[0.06]",
    bar: "bg-bear",
    gloss: "No edge on the sealed years.",
  },
};

export function VerdictBadge({ verdict, className }: { verdict: VerdictLabel; className?: string }) {
  const m = VERDICT_META[verdict];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border px-1.5 py-0.5 text-[10px] font-extrabold uppercase leading-[14px] tracking-[0.1em]",
        m.text,
        m.border,
        m.bg,
        className,
      )}
    >
      <m.Icon size={12} strokeWidth={1.6} className="shrink-0" />
      {verdict}
    </span>
  );
}

/** A workspace panel: header bar with a gold-ticked title, then content. */
export function Panel({
  id,
  title,
  step,
  right,
  children,
  className,
  bodyClassName,
}: {
  id?: string;
  title: string;
  /** Optional step number shown before the title, e.g. "01". */
  step?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <section
      id={id}
      aria-labelledby={headingId}
      className={cn("flex min-w-0 scroll-mt-[calc(var(--chrome-h)+8px)] flex-col", className)}
    >
      <div className="m-head">
        <h2 id={headingId} className="m-title">
          {step && <span className="m-num text-primary">{step}</span>}
          {title}
        </h2>
        {right && <div className="flex min-w-0 items-center gap-2">{right}</div>}
      </div>
      <div className={cn("min-w-0 flex-1", bodyClassName)}>{children}</div>
    </section>
  );
}

/** Label over value, the terminal's basic data cell. */
export function Cell({
  label,
  children,
  className,
  valueClassName,
}: {
  label: string;
  children: ReactNode;
  className?: string;
  valueClassName?: string;
}) {
  return (
    <div className={cn("min-w-0 px-3 py-2", className)}>
      <div className="m-label truncate">{label}</div>
      <div className={cn("m-num mt-0.5 text-[12px] font-bold leading-[18px] text-foreground", valueClassName)}>{children}</div>
    </div>
  );
}

/** Loading placeholder: quiet bars, no spinner. */
export function Skeleton({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2 p-3", className)} role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-4 animate-pulse bg-surface-3"
          style={{ width: `${88 - ((i * 17) % 40)}%` }}
        />
      ))}
    </div>
  );
}

/** Failure state with a retry, used by every data panel. */
export function PanelError({ onRetry, what }: { onRetry: () => void; what: string }) {
  return (
    <div className="flex flex-col items-start gap-2 p-3" role="alert">
      <p className="text-[13px] leading-5 text-foreground">
        Could not load {what}. The data service did not answer.
      </p>
      <button type="button" className="m-btn m-btn-ghost m-btn-sm" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

/** Signed number with an explicit + so the sign never depends on colour. */
export function signed(v: number, decimals = 2): string {
  const s = Math.abs(v).toFixed(decimals);
  return `${v > 0 ? "+" : v < 0 ? "-" : ""}${s}`;
}

export function fmt(v: number, decimals = 2): string {
  return v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
