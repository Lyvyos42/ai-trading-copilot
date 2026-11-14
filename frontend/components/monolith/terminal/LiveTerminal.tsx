"use client";

/**
 * Live Terminal — six panels around the noise-area chart.
 *
 * Every panel reads through `terminalApi` (lib/terminal-api.ts). Until the
 * backend exists the answers are mocks; the page labels itself "Demo data".
 *
 * Copy rule for this screen: it reports rules firing and measured records.
 * It never forecasts direction - the big-move panel is timing only.
 */
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { cn } from "@/lib/utils";
import {
  minuteToClock,
  terminalApi,
  TERMINAL_SYMBOLS,
  type ActivityLevel,
  type CalendarEvent,
  type NoiseBandsResponse,
  type PositioningRow,
  type SignalRecord,
  type TerminalSymbol,
} from "@/lib/terminal-api";
import { fmt, Panel, PanelError, signed, Skeleton, VerdictBadge } from "@/components/monolith/primitives";
import { NoiseBandChart } from "@/components/monolith/terminal/NoiseBandChart";
import { IconArrowRight, IconCheck, IconTrendDown, IconTrendUp } from "@/components/icons/GeoIcons";

const SWR_OPTS = { revalidateOnFocus: false } as const;

function until(fromMinute: number, toMinute: number): string {
  const d = Math.max(0, toMinute - fromMinute);
  const h = Math.floor(d / 60);
  const m = d % 60;
  return h ? `in ${h}h ${String(m).padStart(2, "0")}m` : `in ${m}m`;
}

export function LiveTerminal() {
  return (
    <div>
      <header className="grid gap-x-8 gap-y-2 border-b border-border px-3 py-3 md:px-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0">
          <h1 className="text-[20px] font-extrabold italic leading-6 tracking-[-0.04em] text-primary">
            LIVE TERMINAL
            <span className="font-light not-italic text-muted-foreground">.VALIDATED_ONLY</span>
          </h1>
          <p className="mt-1 max-w-[96ch] text-[13px] leading-5 text-muted-foreground">
            Signals that passed a sealed test, shown live with their record.{" "}
            <span className="text-foreground">Rule-based. No forecast of direction.</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="m-chip m-chip-gold">Demo data</span>
          <span className="m-chip">
            Mock session <span className="m-num">13:40</span> New York
          </span>
        </div>
      </header>

      <div className="grid lg:grid-cols-[minmax(0,1fr)_400px] min-[1700px]:grid-cols-[minmax(0,1fr)_420px_400px]">
        <div className="flex min-w-0 flex-col border-border lg:border-r">
          <ChartPanel />
          <CalendarPanel />
        </div>

        <div className="flex min-w-0 flex-col border-border min-[1700px]:border-r">
          <SignalsPanel />
          <WindowsPanel />
        </div>

        <div className="grid min-w-0 md:grid-cols-2 lg:col-span-2 min-[1700px]:col-span-1 min-[1700px]:grid-cols-1 min-[1700px]:grid-rows-[auto_1fr]">
          <PositioningPanel />
          <OddsPanel />
        </div>
      </div>
    </div>
  );
}

// ─── Noise-area chart ─────────────────────────────────────────────────────────

function ChartPanel() {
  const [symbol, setSymbol] = useState<TerminalSymbol>("USTEC");
  const { data, error, mutate } = useSWR(["terminal/noise-bands", symbol], () => terminalApi.terminal.noiseBands(symbol), {
    ...SWR_OPTS,
    keepPreviousData: true,
  });

  const decimals = symbol === "USTEC" ? 1 : 2;
  const last = data ? data.points[data.now_minute] : null;
  const price = last?.price ?? null;
  const chg = data && price != null ? ((price - data.open) / data.open) * 100 : null;

  return (
    <section
      id="chart"
      aria-labelledby="chart-title"
      className="flex min-w-0 flex-1 scroll-mt-[calc(var(--chrome-h)+8px)] flex-col border-b border-border"
    >
      <div className="m-head flex-wrap gap-y-1.5 py-1.5">
        <div className="flex min-w-0 items-center gap-3">
          <h2 id="chart-title" className="m-title">
            Noise area
          </h2>
          <div role="group" aria-label="Symbol" className="flex">
            {TERMINAL_SYMBOLS.map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={s === symbol}
                onClick={() => setSymbol(s)}
                className={cn(
                  "min-h-[32px] px-2.5 text-[10px] font-extrabold uppercase tracking-[0.12em] transition-colors md:min-h-[22px] md:px-2",
                  s === symbol
                    ? "bg-primary text-black"
                    : "bg-surface-4 text-muted-foreground hover:text-primary",
                )}
              >
                {s}
              </button>
            ))}
          </div>
          <span className="m-chip m-chip-gold hidden sm:inline-flex">
            <span className="m-num">14</span>-day band
          </span>
        </div>
        <div className="text-right" aria-live="off">
          {data && price != null && chg != null ? (
            <>
              <div className={cn("m-num text-[14px] font-bold leading-4", chg >= 0 ? "text-primary" : "text-bear")}>
                {fmt(price, decimals)}
              </div>
              <div className={cn("m-num text-[10px] leading-[14px]", chg >= 0 ? "text-primary" : "text-bear")}>
                {signed(chg, 2)} % <span className="text-muted-foreground">from open</span>
              </div>
            </>
          ) : (
            <div className="h-[30px] w-20 animate-pulse bg-surface-3" />
          )}
        </div>
      </div>

      <div className="flex min-h-[300px] flex-1 flex-col md:min-h-[380px] min-[1700px]:min-h-[440px]">
        {error && !data ? (
          <PanelError what="the noise-area bands" onRetry={() => void mutate()} />
        ) : !data ? (
          <div className="m-gridbg flex-1" role="status" aria-label="Loading chart" />
        ) : (
          <NoiseBandChart data={data} />
        )}
      </div>

      {data ? <ChartState data={data} decimals={decimals} /> : <Skeleton rows={2} />}

      <p className="border-t border-border px-3 py-1.5 text-[12px] leading-[18px] text-muted-foreground">
        Band = average absolute move from the <span className="m-num">09:30</span> New York open at each minute, last{" "}
        <span className="m-num">14</span> sessions. Long above the upper band, short below the lower, checked on the
        half hour. Stop trails the band or VWAP. Flat at <span className="m-num">16:00</span>.
      </p>
    </section>
  );
}

function ChartState({ data, decimals }: { data: NoiseBandsResponse; decimals: number }) {
  const st = data.state;
  const now = data.now_minute;
  const last = data.points[now];
  const inPos = st.position !== "FLAT";

  const cells: { label: string; value: React.ReactNode; sub?: string; tone?: string }[] = [
    {
      label: "State",
      value: (
        <span className="inline-flex items-center gap-1.5">
          {st.position === "LONG" && <IconTrendUp size={12} strokeWidth={2} />}
          {st.position === "SHORT" && <IconTrendDown size={12} strokeWidth={2} />}
          {st.position}
        </span>
      ),
      sub: inPos ? `since ${minuteToClock(st.since_minute ?? 0)}` : "inside the band",
      tone: st.position === "LONG" ? "text-primary" : st.position === "SHORT" ? "text-bear" : "text-foreground",
    },
    {
      label: "Entry",
      value: inPos && st.entry != null ? fmt(st.entry, decimals) : "none",
      sub: inPos ? `${minuteToClock(st.since_minute ?? 0)} check` : "no check has fired",
    },
    {
      label: "Trailing stop",
      value: inPos && st.stop != null ? fmt(st.stop, decimals) : "none",
      sub: inPos ? (st.stop_basis === "VWAP" ? "at VWAP" : "at the band") : "no position",
    },
    {
      label: "Band now",
      value: `${fmt(last.lower, decimals)}`,
      sub: `to ${fmt(last.upper, decimals)}`,
    },
    {
      label: "Next check",
      value: st.next_check_minute != null ? minuteToClock(st.next_check_minute) : "none",
      sub: st.next_check_minute != null ? until(now, st.next_check_minute) : "session ending",
    },
    {
      label: "Flat at",
      value: minuteToClock(st.flat_minute),
      sub: until(now, st.flat_minute),
    },
  ];

  return (
    <dl className="grid grid-cols-2 gap-px border-t border-border bg-border sm:grid-cols-3 xl:grid-cols-6">
      {cells.map((c) => (
        <div key={c.label} className="min-w-0 bg-surface-1 px-3 py-2">
          <dt className="m-label truncate">{c.label}</dt>
          <dd className={cn("m-num mt-0.5 text-[13px] font-bold leading-[18px]", c.tone ?? "text-foreground")}>
            {c.value}
          </dd>
          {c.sub && <dd className="m-num truncate text-[11px] leading-4 text-muted-foreground">{c.sub}</dd>}
        </div>
      ))}
    </dl>
  );
}

// ─── Economic calendar ────────────────────────────────────────────────────────

const IMPACT_PIPS: Record<CalendarEvent["impact"], number> = { LOW: 1, MED: 2, HIGH: 3 };

function Pips({ n, of = 3 }: { n: number; of?: number }) {
  return (
    <span className="flex items-center gap-[2px]" aria-hidden="true">
      {Array.from({ length: of }).map((_, i) => (
        <i key={i} className={cn("block h-[7px] w-[4px]", i < n ? "bg-primary" : "bg-surface-4")} />
      ))}
    </span>
  );
}

function CalendarPanel() {
  const { data, error, mutate } = useSWR("terminal/calendar", () => terminalApi.terminal.calendar(), SWR_OPTS);
  return (
    <Panel
      id="calendar"
      title="Calendar"
      className="border-b border-border"
      right={<span className="m-label">Today, New York time</span>}
    >
      {error ? (
        <PanelError what="the calendar" onRetry={() => void mutate()} />
      ) : !data ? (
        <Skeleton rows={3} />
      ) : (
        // Six events: 6 × 1, 3 × 2, 2 × 3 or 1 × 6.
        <ul className="grid auto-rows-fr grid-cols-1 gap-px bg-border sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
          {data.events.map((e) => {
            const next = e.status === "NEXT";
            return (
              <li key={e.id} className={cn("relative flex min-w-0 flex-col px-3 py-2", next ? "bg-surface-2" : "bg-surface-1")}>
                {next && <span className="absolute inset-x-0 top-0 h-[2px] bg-primary" aria-hidden="true" />}
                <div className="flex items-center justify-between gap-2">
                  <span className={cn("m-num text-[13px] font-bold leading-[18px]", next ? "text-primary" : "text-foreground")}>
                    {e.time}
                  </span>
                  {e.status === "DONE" ? (
                    <span className="flex items-center gap-1 text-[10px] font-extrabold uppercase tracking-[0.1em] text-muted-foreground">
                      <IconCheck size={10} strokeWidth={2} /> Out
                    </span>
                  ) : next ? (
                    <span className="m-chip m-chip-gold">Next</span>
                  ) : (
                    <span className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-muted-foreground">Later</span>
                  )}
                </div>
                <p className="mt-1 text-[12px] font-semibold leading-4 text-foreground">
                  <span className="m-num mr-1.5 text-muted-foreground">{e.currency}</span>
                  {e.title}
                </p>
                <div className="mt-1 flex items-center gap-1.5">
                  <Pips n={IMPACT_PIPS[e.impact]} />
                  <span className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-muted-foreground">
                    {e.impact === "MED" ? "Medium" : e.impact === "HIGH" ? "High" : "Low"} impact
                  </span>
                </div>
                <dl className="mt-auto grid grid-cols-3 pt-2">
                  {([["Act", e.actual], ["Fcst", e.forecast], ["Prev", e.previous]] as const).map(([k, v]) => (
                    <div key={k} className="min-w-0">
                      <dt className="text-[9px] font-bold uppercase leading-3 tracking-[0.1em] text-muted-foreground">{k}</dt>
                      <dd className={cn("m-num whitespace-nowrap text-[11px] leading-4", k === "Act" && v ? "font-bold text-foreground" : "text-muted-foreground")}>
                        {v ?? "n/a"}
                      </dd>
                    </div>
                  ))}
                </dl>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}

// ─── Validated signals ────────────────────────────────────────────────────────

function StateChip({ state }: { state: SignalRecord["state"] }) {
  const cls =
    state === "LONG"
      ? "border-primary bg-primary text-black"
      : state === "SHORT"
        ? "border-bear bg-bear text-black"
        : state === "ARMED"
          ? "border-warn/50 bg-warn/[0.06] text-warn"
          : "border-border-strong text-muted-foreground";
  return (
    <span className={cn("inline-flex shrink-0 items-center gap-1 border px-1.5 text-[10px] font-extrabold uppercase leading-[16px] tracking-[0.1em]", cls)}>
      {state === "LONG" && <IconTrendUp size={10} strokeWidth={2.2} />}
      {state === "SHORT" && <IconTrendDown size={10} strokeWidth={2.2} />}
      {state}
    </span>
  );
}

function unitValue(v: number, unit: string, withSign = true): string {
  const d = unit === "pips" ? 0 : Math.abs(v) < 0.1 ? 3 : 2;
  return `${withSign ? signed(v, d) : v.toFixed(d)} ${unit}`;
}

function SignalsPanel() {
  const { data, error, mutate } = useSWR("terminal/signals", () => terminalApi.terminal.signals(), SWR_OPTS);
  return (
    <Panel
      id="signals"
      title="Validated signals"
      className="border-b border-border"
      right={<span className="m-label">{data?.is_mock ? "Example record" : "Live record"}</span>}
    >
      {error ? (
        <PanelError what="the signals" onRetry={() => void mutate()} />
      ) : !data ? (
        <Skeleton rows={6} />
      ) : (
        <>
          <ul className="divide-y divide-border">
            {data.signals.map((s) => (
              <li key={s.id} className="px-3 py-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="truncate text-[13px] font-bold leading-[18px] text-foreground">{s.name}</h3>
                    <div className="m-num text-[11px] leading-4 text-muted-foreground">
                      {s.symbol} · {s.timeframe}
                    </div>
                  </div>
                  <VerdictBadge verdict={s.verdict} className="shrink-0" />
                </div>

                <div className="mt-1.5 flex items-start gap-2">
                  <StateChip state={s.state} />
                  <p className="min-w-0 text-[12px] leading-[18px] text-muted-foreground">{s.state_note}</p>
                </div>

                <dl className="mt-2 grid grid-cols-4 gap-px border border-border bg-border">
                  {[
                    { k: "Live since", v: s.live.since.slice(5), sub: s.live.since.slice(0, 4) },
                    { k: "Signals", v: String(s.live.signals), sub: `${s.live.winners} won` },
                    { k: "Avg live", v: unitValue(s.live.avg, s.unit), sub: "per signal", tone: s.live.avg >= 0 ? "text-primary" : "text-bear" },
                    { k: "Avg tested", v: unitValue(s.tested_avg, s.unit), sub: s.tested_period },
                  ].map((c) => (
                    <div key={c.k} className="min-w-0 bg-surface-1 px-2 py-1.5">
                      <dt className="truncate text-[9px] font-bold uppercase leading-3 tracking-[0.1em] text-muted-foreground">{c.k}</dt>
                      <dd className={cn("m-num mt-0.5 truncate text-[12px] font-bold leading-4", c.tone ?? "text-foreground")}>{c.v}</dd>
                      <dd className="m-num truncate text-[10px] leading-[14px] text-muted-foreground">{c.sub}</dd>
                    </div>
                  ))}
                </dl>

                <div className="mt-1.5 flex flex-wrap items-center gap-x-1.5 gap-y-1">
                  <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-muted-foreground">Closed</span>
                  {s.live.results.map((r, i) => (
                    <span
                      key={i}
                      className={cn(
                        "m-num border px-1 text-[10px] font-bold leading-[14px]",
                        r >= 0 ? "border-primary/40 bg-primary/5 text-primary" : "border-bear/40 bg-bear/5 text-bear",
                      )}
                    >
                      {signed(r, s.unit === "pips" ? 0 : 2)}
                    </span>
                  ))}
                  {s.lab_example_id && (
                    <Link
                      href={`/lab?example=${s.lab_example_id}`}
                      className="ml-auto flex items-center gap-1 text-[10px] font-extrabold uppercase tracking-[0.12em] text-primary hover:underline"
                    >
                      See the test <IconArrowRight size={10} strokeWidth={2} />
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <p className="border-t border-border px-3 py-1.5 text-[12px] leading-[18px] text-muted-foreground">
            {data.is_mock
              ? "Example figures, not real results: the live record feed is not connected yet."
              : "Live records are short and shown as they are, losses included."}
          </p>
        </>
      )}
    </Panel>
  );
}

// ─── Big-move windows ─────────────────────────────────────────────────────────

const LEVEL_BAR: Record<ActivityLevel, string> = {
  HIGH: "bg-primary",
  ELEVATED: "bg-[hsl(var(--m-gold-dim))]",
  NORMAL: "bg-[#6a6a6a]",
  QUIET: "bg-[#595959]",
};

function WindowsPanel() {
  const { data, error, mutate } = useSWR("terminal/activity-windows", () => terminalApi.terminal.activityWindows(), SWR_OPTS);
  const max = data ? Math.max(...data.slots.map((s) => s.range_ratio)) : 1;
  return (
    <Panel
      id="windows"
      title="Big-move windows"
      className="flex-1 border-b border-border"
      bodyClassName="flex flex-col"
      right={<span className="m-label">Next <span className="m-num">8</span> h</span>}
    >
      {error ? (
        <PanelError what="the activity windows" onRetry={() => void mutate()} />
      ) : !data ? (
        <Skeleton rows={5} />
      ) : (
        <>
          <div className="px-3 pt-3">
            <div
              role="img"
              aria-label={`Expected activity in 30-minute slots for the next ${data.horizon_hours} hours. ${data.windows
                .map((w) => `${w.level} from ${w.start} to ${w.end}: ${w.reason}.`)
                .join(" ")}`}
              className="relative grid h-[64px] items-end gap-[2px] border-b border-border-strong"
              style={{ gridTemplateColumns: `repeat(${data.slots.length}, minmax(0, 1fr))` }}
            >
              <span
                className="pointer-events-none absolute inset-x-0 border-t border-dashed border-muted-foreground/60"
                style={{ bottom: `${(1 / max) * 100}%` }}
              />
              {data.slots.map((s) => (
                <div
                  key={s.start}
                  title={`${s.start}  ${s.level}  ${s.range_ratio.toFixed(1)}x normal range`}
                  className={cn("relative", LEVEL_BAR[s.level])}
                  style={{ height: `${Math.max(6, (s.range_ratio / max) * 100)}%` }}
                />
              ))}
            </div>
            <div
              className="grid gap-[2px] pt-1"
              style={{ gridTemplateColumns: `repeat(${data.slots.length}, minmax(0, 1fr))` }}
              aria-hidden="true"
            >
              {data.slots.map((s, i) => (
                <span key={s.start} className="m-num overflow-visible whitespace-nowrap text-[10px] leading-4 text-muted-foreground">
                  {i % 4 === 1 ? s.start : ""}
                </span>
              ))}
            </div>
            <div className="mt-1 flex items-center gap-2 text-[10px] leading-4 text-muted-foreground">
              <span className="block w-4 border-t border-dashed border-muted-foreground/60" aria-hidden="true" />
              <span className="font-bold uppercase tracking-[0.1em]">Normal range for the slot</span>
            </div>
          </div>

          <ul className="mt-2 divide-y divide-border border-t border-border">
            {data.windows.map((w) => (
              <li key={w.start} className="grid grid-cols-[92px_minmax(0,1fr)] gap-x-3 px-3 py-2">
                <div>
                  <div className="m-num text-[12px] font-bold leading-[18px] text-foreground">
                    {w.start}-{w.end}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5">
                    <Pips n={w.level === "HIGH" ? 3 : 2} />
                    <span className={cn("text-[10px] font-extrabold uppercase tracking-[0.1em]", w.level === "HIGH" ? "text-primary" : "text-foreground")}>
                      {w.level}
                    </span>
                  </div>
                </div>
                <div className="min-w-0">
                  <p className="text-[12px] font-semibold leading-[18px] text-foreground">{w.reason}</p>
                  <p className="text-[11px] leading-4 text-muted-foreground">{w.scope}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-auto border-t border-border px-3 py-1.5 text-[12px] leading-[18px] text-muted-foreground">
            <span className="font-bold text-foreground">Timing only.</span> When a larger move is likely, not which way.
          </p>
        </>
      )}
    </Panel>
  );
}

// ─── Crypto crowd positioning ─────────────────────────────────────────────────

function ZSpark({ row, threshold }: { row: PositioningRow; threshold: number }) {
  const W = 300;
  const H = 40;
  const lim = Math.max(2.5, ...row.z_history.map((v) => Math.abs(v))) * 1.05;
  const x = (i: number) => (i / (row.z_history.length - 1)) * W;
  const y = (v: number) => H / 2 - (v / lim) * (H / 2);
  const d = row.z_history.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("");
  const lastV = row.z_history[row.z_history.length - 1];
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className="block h-10 w-full bg-black"
      role="img"
      aria-label={`${row.symbol} z-score over 90 days, now ${signed(row.z, 2)}. Extreme beyond plus or minus ${threshold}.`}
    >
      <line x1="0" x2={W} y1={y(threshold)} y2={y(threshold)} stroke="#FF8C42" strokeOpacity="0.7" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
      <line x1="0" x2={W} y1={y(-threshold)} y2={y(-threshold)} stroke="#FF8C42" strokeOpacity="0.7" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
      <line x1="0" x2={W} y1={y(0)} y2={y(0)} stroke="#333" vectorEffect="non-scaling-stroke" />
      <path d={d} fill="none" stroke="#E6A532" strokeWidth="1.25" vectorEffect="non-scaling-stroke" />
      <rect x={W - 3} y={y(lastV) - 3} width="3" height="6" fill="#E6A532" />
    </svg>
  );
}

function PositioningPanel() {
  const { data, error, mutate } = useSWR("terminal/positioning", () => terminalApi.terminal.positioning(), SWR_OPTS);
  return (
    <Panel
      id="positioning"
      title="Crowd positioning"
      className="border-b border-border md:border-r min-[1700px]:border-r-0"
      bodyClassName="flex flex-col"
      right={<span className="m-label">Crypto, all accounts</span>}
    >
      {error ? (
        <PanelError what="crowd positioning" onRetry={() => void mutate()} />
      ) : !data ? (
        <Skeleton rows={5} />
      ) : (
        <>
          <ul className="divide-y divide-border">
            {data.rows.map((r) => (
              <li key={r.symbol} className="px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-[12px] font-extrabold leading-[18px] tracking-[0.14em] text-primary">{r.symbol}</h3>
                  {r.extreme ? (
                    <span className="inline-flex items-center gap-1 border border-warn/50 bg-warn/[0.06] px-1.5 text-[10px] font-extrabold uppercase leading-[16px] tracking-[0.1em] text-warn">
                      {r.extreme === "LONG" ? <IconTrendUp size={10} strokeWidth={2.2} /> : <IconTrendDown size={10} strokeWidth={2.2} />}
                      Crowd extreme {r.extreme}
                    </span>
                  ) : (
                    <span className="m-chip">Within range</span>
                  )}
                </div>

                <div className="mt-1.5 flex justify-between text-[10px] font-bold uppercase leading-4 tracking-[0.1em]">
                  <span className="text-foreground">
                    Long <span className="m-num">{r.long_pct.toFixed(1)} %</span>
                  </span>
                  <span className="text-muted-foreground">
                    Short <span className="m-num">{(100 - r.long_pct).toFixed(1)} %</span>
                  </span>
                </div>
                <div className="relative mt-0.5 flex h-2 bg-surface-4" aria-hidden="true">
                  <div className="bg-primary" style={{ width: `${r.long_pct}%` }} />
                  <span className="absolute inset-y-[-2px] left-1/2 w-px bg-foreground" />
                </div>

                <dl className="mt-2 grid grid-cols-3 gap-px border border-border bg-border">
                  {[
                    { k: "Long / short", v: r.ratio.toFixed(2) },
                    { k: "z vs 90 days", v: signed(r.z, 2), tone: r.extreme ? "text-warn" : undefined },
                    { k: "Extreme at", v: `±${data.threshold.toFixed(2)}` },
                  ].map((c) => (
                    <div key={c.k} className="min-w-0 bg-surface-1 px-2 py-1.5">
                      <dt className="truncate text-[9px] font-bold uppercase leading-3 tracking-[0.1em] text-muted-foreground">{c.k}</dt>
                      <dd className={cn("m-num mt-0.5 text-[12px] font-bold leading-4", c.tone ?? "text-foreground")}>{c.v}</dd>
                    </div>
                  ))}
                </dl>
                <div className="mt-1.5 border border-border">
                  <ZSpark row={r} threshold={data.threshold} />
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border px-3 py-1.5 text-[12px] leading-[18px] text-muted-foreground">
            <span>Fading the crowd was tested:</span>
            <VerdictBadge verdict="NEAR MISS" />
            <Link
              href="/lab?example=crowd-fade"
              className="ml-auto flex items-center gap-1 text-[10px] font-extrabold uppercase tracking-[0.12em] text-primary hover:underline"
            >
              See the test <IconArrowRight size={10} strokeWidth={2} />
            </Link>
          </p>
        </>
      )}
    </Panel>
  );
}

// ─── Prediction-market odds ───────────────────────────────────────────────────

function OddsPanel() {
  const { data, error, mutate } = useSWR("terminal/odds", () => terminalApi.terminal.odds(), SWR_OPTS);
  return (
    <Panel
      id="odds"
      title="Market odds"
      className="border-b border-border"
      bodyClassName="flex flex-col"
      right={<span className="m-label">Prediction markets</span>}
    >
      {error ? (
        <PanelError what="the odds" onRetry={() => void mutate()} />
      ) : !data ? (
        <Skeleton rows={6} />
      ) : (
        <>
          <table className="w-full flex-1 border-separate border-spacing-0 text-left">
            <caption className="sr-only">Prediction-market odds, with the change over seven days</caption>
            <thead>
              <tr>
                {["Market", "Odds", "7 d"].map((h, i) => (
                  <th
                    key={h}
                    scope="col"
                    className={cn(
                      "border-b border-border px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-[0.14em] text-muted-foreground",
                      i > 0 && "text-right",
                    )}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.id} className="transition-colors hover:bg-surface-2">
                  <th scope="row" className="border-b border-border px-3 py-1.5 text-left font-normal">
                    <span className="flex items-baseline gap-2">
                      <span className="m-num w-[38px] shrink-0 text-[10px] font-bold uppercase tracking-[0.08em] text-primary">
                        {r.category}
                      </span>
                      <span className="min-w-0 text-[12px] leading-[18px] text-foreground">{r.question}</span>
                    </span>
                  </th>
                  <td className="border-b border-border px-3 py-1.5">
                    <span className="flex items-center justify-end gap-2">
                      <span className="hidden h-[6px] w-14 bg-surface-4 sm:block" aria-hidden="true">
                        <span className="block h-full bg-primary" style={{ width: `${r.probability}%` }} />
                      </span>
                      <span className="m-num w-[38px] text-right text-[12px] font-bold text-foreground">{r.probability} %</span>
                    </span>
                  </td>
                  <td
                    className={cn(
                      "m-num whitespace-nowrap border-b border-border px-3 py-1.5 text-right text-[11px] font-bold",
                      r.change_7d > 0 ? "text-primary" : r.change_7d < 0 ? "text-bear" : "text-muted-foreground",
                    )}
                  >
                    {r.change_7d === 0 ? "0" : signed(r.change_7d, 0)} pp
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-auto px-3 py-1.5 text-[12px] leading-[18px] text-muted-foreground">
            <span className="font-bold text-foreground">Information only.</span> Odds are what those markets quote, not a
            forecast by this app.
          </p>
        </>
      )}
    </Panel>
  );
}
