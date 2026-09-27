"use client";

/**
 * TELEGRAM SIGNAL RECORD - every IEB signal posted to the public channel, and its result.
 *
 * Data: GET /api/v1/ieb/telegram-record (backend/app/ieb/routes.py). Only signals that were actually
 * posted are counted; nothing is removed afterwards; an exit whose price is unknown is shown and not
 * counted. R is measured at the module's own prices, before any broker's costs.
 */
import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { cn } from "@/lib/utils";

type Rate = { k: number; n: number; rate: number | null; lo: number | null; hi: number | null; adequate: boolean };
type MeanCI = { n: number; mean: number | null; lo: number | null; hi: number | null; adequate: boolean };
type Group = { signals: number; resolved: number; tp1_before_stop: number | null; tp1_n: number; mean_r: number | null; r_lo: number | null; r_hi: number | null; r_n: number };
type Sig = { signal_id: string; module_id: string; module_version: string; generated_at: string; symbol: string; direction: string;
  entry_reference: number; stop_reference: number | null; tp1: number | null; resolved: boolean; exit_reason: string | null;
  r_multiple: number | null; exit_timestamp: string | null; telegram_url: string | null; result_url: string | null };
type Rec = { channel: string; posted: number; open: number; results: Record<string, number>; tp1_before_stop: Rate; r: MeanCI;
  total_r: number; by_module: Record<string, Group>; cumulative: { t: string; r: number; cum_r: number }[]; signals: Sig[];
  definitions: Record<string, string> };

const pct = (x: number | null | undefined) => (x == null ? "-" : `${Math.round(x * 100)}%`);
const rr = (x: number | null | undefined) => (x == null ? "-" : `${x >= 0 ? "+" : ""}${x.toFixed(2)}`);
const px = (x: number | null | undefined) => (x == null ? "-" : Number(x.toPrecision(6)).toString());
const utc = (iso: string | null) => (iso ? iso.replace("T", " ").slice(0, 16) + " UTC" : "-");

function Tile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "bull" | "bear" }) {
  return (
    <div className="terminal-panel p-4">
      <div className="terminal-label mb-1">{label}</div>
      <div className={cn("text-2xl font-mono font-bold tabular-nums", tone === "bull" && "text-bull", tone === "bear" && "text-bear")}>{value}</div>
      {sub && <div className="text-[12px] font-mono text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}

function CumulativeChart({ pts }: { pts: Rec["cumulative"] }) {
  if (pts.length < 2) {
    return <p className="text-sm font-mono text-muted-foreground">The curve appears once two posted signals have a known result.</p>;
  }
  const W = 800, H = 200, pad = 24;
  const ys = [0, ...pts.map((p) => p.cum_r)];
  const lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1;
  const x = (i: number) => pad + (i * (W - 2 * pad)) / (pts.length - 1);
  const y = (v: number) => H - pad - ((v - lo) * (H - 2 * pad)) / span;
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.cum_r).toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1].cum_r;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
      aria-label={`Cumulative result of posted signals, in R before costs: ${rr(last)} R after ${pts.length} known results`}>
      <line x1={pad} x2={W - pad} y1={y(0)} y2={y(0)} stroke="hsl(var(--border))" strokeDasharray="4 4" />
      <path d={d} fill="none" stroke={last >= 0 ? "hsl(var(--bull))" : "hsl(var(--bear))"} strokeWidth="2" />
      <text x={W - pad} y={y(last) - 8} textAnchor="end" className="fill-current text-[12px] font-mono">{rr(last)} R</text>
    </svg>
  );
}

export default function TelegramRecordPage() {
  const [rec, setRec] = useState<Rec | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await fetch(`${API_URL}/api/v1/ieb/telegram-record`, { cache: "no-store" });
      if (!r.ok) throw new Error(`answered ${r.status}`);
      setRec(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);
  useEffect(() => { load(); const id = setInterval(load, 60000); return () => clearInterval(id); }, [load]);

  const tp = rec?.tp1_before_stop;
  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-4">
      <header className="space-y-2">
        <h1 className="text-xl sm:text-2xl font-mono font-bold tracking-wide">TELEGRAM SIGNAL RECORD</h1>
        <p className="text-sm text-foreground/75 max-w-3xl leading-relaxed">
          Every IEB signal posted to the public channel before its result was known, and every result - wins, losses and
          unknown exits alike. Only posted signals are counted and nothing is removed afterwards. R is measured at the
          module&apos;s own prices, before your broker&apos;s costs.
        </p>
        <a href={rec?.channel || "https://t.me/NeuralICC"} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center min-h-[44px] px-4 rounded border border-primary/40 text-primary font-mono text-sm hover:bg-primary/10">
          Open the channel @NeuralICC ↗
        </a>
      </header>

      {error && (
        <div role="alert" className="terminal-panel p-4 flex flex-wrap items-center gap-3">
          <span className="text-sm font-mono text-bear">Could not load the record: {error}</span>
          <button onClick={load} className="min-h-[44px] px-4 rounded border border-border font-mono text-sm hover:bg-white/5">Retry</button>
        </div>
      )}
      {!rec && !error && <div className="terminal-panel h-40 animate-pulse" aria-busy="true" />}

      {rec && (
        <>
          <section className="grid gap-3 grid-cols-2 lg:grid-cols-4" aria-label="Totals">
            <Tile label="Signals posted" value={String(rec.posted)} sub={`${rec.open} still open`} />
            <Tile label="Results" value={`${rec.results.target ?? 0} / ${rec.results.stop ?? 0}`}
              sub={`target / stop · ${rec.results.other ?? 0} module exit · ${rec.results.unknown ?? 0} unknown`} />
            <Tile label="TP1 before stop" value={tp?.n ? pct(tp.rate) : "-"}
              sub={tp?.n ? `${tp.k} of ${tp.n} · 95% ${pct(tp.lo)}-${pct(tp.hi)}${tp.adequate ? "" : " · insufficient sample"}` : "no target/stop results yet"} />
            <Tile label="Total result" value={`${rr(rec.total_r)} R`} tone={rec.total_r > 0 ? "bull" : rec.total_r < 0 ? "bear" : undefined}
              sub={rec.r.n ? `mean ${rr(rec.r.mean)} R over ${rec.r.n}${rec.r.lo != null ? ` · 95% ${rr(rec.r.lo)}..${rr(rec.r.hi)}` : ""}` : "no known results yet"} />
          </section>

          <section className="terminal-panel p-4 sm:p-5">
            <h2 className="terminal-label mb-3">Cumulative result (R, before costs)</h2>
            <CumulativeChart pts={rec.cumulative} />
          </section>

          {Object.keys(rec.by_module).length > 0 && (
            <section className="terminal-panel p-4 sm:p-5">
              <h2 className="terminal-label mb-3">By module</h2>
              <div className="overflow-x-auto -mx-4 sm:mx-0">
                <table className="w-full min-w-[560px] text-[13px] font-mono">
                  <thead><tr className="text-left terminal-label">
                    <th className="py-2 px-2 font-semibold">Module</th><th className="px-2 font-semibold text-right">Posted</th>
                    <th className="px-2 font-semibold text-right">Known results</th><th className="px-2 font-semibold text-right">TP1 first</th>
                    <th className="px-2 font-semibold text-right">Mean R (95%)</th></tr></thead>
                  <tbody>
                    {Object.entries(rec.by_module).map(([m, g]) => (
                      <tr key={m} className="border-t border-border/40">
                        <td className="py-2 px-2">{m}</td><td className="px-2 text-right">{g.signals}</td><td className="px-2 text-right">{g.r_n}</td>
                        <td className="px-2 text-right">{pct(g.tp1_before_stop)} <span className="text-muted-foreground">/{g.tp1_n}</span></td>
                        <td className="px-2 text-right">{rr(g.mean_r)} <span className="text-muted-foreground">{g.r_lo == null ? "" : `${rr(g.r_lo)}..${rr(g.r_hi)}`}</span></td>
                      </tr>))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section className="terminal-panel p-4 sm:p-5">
            <h2 className="terminal-label mb-3">Every posted signal</h2>
            {rec.signals.length === 0 ? (
              <p className="text-sm font-mono text-muted-foreground">
                No signals posted yet. The channel posts each IEB signal as it is made - the first ones come after the market opens.
              </p>
            ) : (
              <div className="overflow-x-auto -mx-4 sm:mx-0">
                <table className="w-full min-w-[860px] text-[12px] font-mono">
                  <thead><tr className="text-left terminal-label">
                    <th className="py-2 px-2 font-semibold">Posted signal</th><th className="px-2 font-semibold">Module</th>
                    <th className="px-2 font-semibold">Symbol</th><th className="px-2 font-semibold">Side</th>
                    <th className="px-2 font-semibold text-right">Entry</th><th className="px-2 font-semibold text-right">Stop</th>
                    <th className="px-2 font-semibold text-right">TP1</th><th className="px-2 font-semibold">Result</th></tr></thead>
                  <tbody>
                    {rec.signals.map((s) => (
                      <tr key={s.signal_id} className="border-t border-border/40" title={`signal ${s.signal_id} · version ${s.module_version}`}>
                        <td className="py-1.5 px-2 whitespace-nowrap">
                          {s.telegram_url ? <a href={s.telegram_url} target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:underline">{utc(s.generated_at)} ↗</a> : utc(s.generated_at)}
                        </td>
                        <td className="px-2">{s.module_id}</td><td className="px-2">{s.symbol}</td>
                        <td className={cn("px-2 font-bold", s.direction === "LONG" ? "text-bull" : "text-bear")}>{s.direction}</td>
                        <td className="px-2 text-right">{px(s.entry_reference)}</td><td className="px-2 text-right">{px(s.stop_reference)}</td>
                        <td className="px-2 text-right">{px(s.tp1)}</td>
                        <td className="px-2 whitespace-nowrap">
                          {!s.resolved ? <span className="text-muted-foreground">open</span>
                            : s.exit_reason === "unknown" ? <span className="text-muted-foreground">exit unknown (not counted)</span>
                            : <span className={cn((s.r_multiple ?? 0) >= 0 ? "text-bull" : "text-bear")}>{s.exit_reason} {rr(s.r_multiple)} R</span>}
                          {s.result_url && <a href={s.result_url} target="_blank" rel="noopener noreferrer" className="ml-2 text-muted-foreground hover:underline">post ↗</a>}
                        </td>
                      </tr>))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <p className="text-[12px] text-muted-foreground max-w-3xl">
            {rec.definitions.r}. TP1 before stop: {rec.definitions.tp1_before_stop}. Unknown: {rec.definitions.unknown}.
            Information, not advice.
          </p>
        </>
      )}
    </main>
  );
}
