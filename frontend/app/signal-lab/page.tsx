"use client";

/**
 * SIGNAL LAB - every signal module, every version, measured the same way.
 *
 * Data (public, read-only, computed server-side from the canonical records):
 *   GET /api/v1/ieb/status          IEB bridge health per instance
 *   GET /api/v1/lab/modules         registry + research card + promotion check per module version
 *   GET /api/v1/lab/score           Consensus Score research for the Copilot generators
 *   GET /api/v1/ieb/signals/recent  newest IEB signals with their outcomes
 *
 * Nothing on this page is typed in by hand: every number is the server's measurement, and a
 * number that has not been measured is shown as "-" or "insufficient sample", never estimated.
 */
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { API_URL } from "@/lib/api";
import { cn } from "@/lib/utils";

// ─── types (mirror backend/app/ieb/routes.py + research.py) ─────────────────
type Rate = { k: number; n: number; rate: number | null; lo: number | null; hi: number | null; adequate: boolean };
type MeanCI = { n: number; mean: number | null; lo: number | null; hi: number | null; median: number | null;
  half_width?: number; adequate: boolean; win_rate?: number | null; avg_win?: number | null;
  avg_loss?: number | null; breakeven_win_rate?: number | null };
type Card = {
  signals: number; resolved: number; unknown_exits: number;
  tp1_before_stop: Rate; direction_correct_at_exit: Rate; r: MeanCI;
  mfe_r: { n: number; mean: number | null }; mae_r: { n: number; mean: number | null };
  median_holding_minutes: number | null; score_distribution: Record<string, number | string>; costs: string;
};
type Group = { signals: number; resolved: number; tp1_before_stop: number | null; tp1_n: number;
  mean_r: number | null; r_lo: number | null; r_hi: number | null; r_n: number };
type Finding = { label: string; why: string; flags: string[]; limitations: string[] };
type Req = { rule: string; met: boolean | null; detail?: string };
type Promotion = { next: string | null; requirements: Req[]; note?: string };
type Registry = { module_name?: string; module_type?: string; status?: string; description?: string | null;
  timeframes?: string[]; symbols?: string[]; signal_logic_reference?: string | null;
  score_definition?: string | null; outcome_definition?: string | null } | null;
type VersionEntry = { version: string; registry: Registry; card: Card; breakdowns: Record<string, Record<string, Group>>;
  finding: Finding; promotion: Promotion; direction_disagrees_with_votes?: number };
type Row = { module_id: string; version: string; status: string | null; signals: number; resolved: number;
  tp1_before_stop: number | null; tp1_n: number; mean_r: number | null; r_lo: number | null; r_hi: number | null;
  r_n: number; finding: string; next_step: string | null };
type LabModules = { generated_at: string; modules: Record<string, { module_id: string; source: string;
  versions: Record<string, VersionEntry> }>; comparison: Row[]; pipeline: string[];
  pipeline_rules: Record<string, string>; sample_rules: { rate_half_width: number; mean_r_half_width: number;
  n_for_10pt_rate_at_p_0_5: number } };
type Band = Rate & { band: string };
type ScoreVersion = { n: number; bands: Band[]; below_50: number; n_needed_per_band_for_10pt_interval: number;
  discrimination: { auc: number | null; lo?: number; hi?: number; n_win: number; n_loss: number; verdict: string } };
type LabScore = { score_definition: string; outcome_definition: string;
  modules: Record<string, { name: string; excluded_direction_against_votes: number; versions: Record<string, ScoreVersion> }> };
type Instance = { instance_id: string; state: string; version: string | null; last_heartbeat: string | null;
  last_signal_received: string | null; last_successful_request: string | null; last_error: string | null;
  backlog: Record<string, number>; modules_active: string[] };
type IebSignal = { signal_id: string; module_id: string; module_version: string; generated_at: string; symbol: string;
  direction: string; entry_reference: number; stop_reference: number | null; tp1: number | null;
  historical_outcome_rate: number | null; outcome_rate_sample: number | null; source: string;
  resolved: boolean; exit_reason: string | null; r_multiple: number | null; on_telegram: boolean };

// ─── formatting ──────────────────────────────────────────────────────────────
const pct = (x: number | null | undefined, d = 0) => (x == null ? "-" : `${(x * 100).toFixed(d)}%`);
const rr = (x: number | null | undefined) => (x == null ? "-" : `${x >= 0 ? "+" : ""}${x.toFixed(2)}`);
const px = (x: number | null | undefined) => (x == null ? "-" : Number(x.toPrecision(6)).toString());
const shortV = (v: string) => (v.length > 14 ? v.slice(0, 12) + "…" : v);
function ago(iso: string | null): string {
  if (!iso) return "never";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 90) return `${Math.round(s)}s ago`;
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 172800) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}
const utc = (iso: string) => iso.replace("T", " ").slice(0, 16) + " UTC";

const STATUS_ORDER = ["LIVE", "BETA", "SHADOW", "RESEARCH", "PAUSED", "DISABLED", "RETIRED"];
const STATUS_STYLE: Record<string, string> = {
  LIVE: "text-bull border-bull/40 bg-bull/10",
  BETA: "text-primary border-primary/40 bg-primary/10",
  SHADOW: "text-sky-300 border-sky-400/30 bg-sky-400/10",
  RESEARCH: "text-violet-300 border-violet-400/30 bg-violet-400/10",
  PAUSED: "text-amber-300 border-amber-400/30 bg-amber-400/10",
  DISABLED: "text-muted-foreground border-border bg-transparent",
  RETIRED: "text-muted-foreground border-border bg-transparent line-through",
};
const FINDING_STYLE: Record<string, string> = {
  NEGATIVE: "text-bear",
  WEAK: "text-amber-300",
  POSITIVE_BEFORE_COSTS: "text-bull",
  INSUFFICIENT_SAMPLE: "text-muted-foreground",
  UNRESOLVED: "text-foreground/80",
};
const STATE_STYLE: Record<string, { cls: string; text: string }> = {
  CONNECTED: { cls: "text-bull border-bull/40 bg-bull/10", text: "Heartbeat received in the last 3 minutes, no recent errors." },
  DEGRADED: { cls: "text-amber-300 border-amber-400/40 bg-amber-400/10", text: "Connected, but with a recent error or a delivery backlog." },
  OFFLINE: { cls: "text-muted-foreground border-border", text: "No heartbeat in the last 3 minutes - IEB is off, or its PC is." },
  UNAUTHENTICATED: { cls: "text-bear border-bear/40 bg-bear/10", text: "The last request carrying this instance id failed its signature check." },
  PAUSED: { cls: "text-sky-300 border-sky-400/30 bg-sky-400/10", text: "Switched off on purpose in IEB. Signals made meanwhile are sent when it is switched back on." },
};

function Badge({ children, cls }: { children: React.ReactNode; cls: string }) {
  return <span className={cn("inline-block text-[11px] font-mono font-bold tracking-wider px-1.5 py-0.5 rounded border", cls)}>{children}</span>;
}

function Panel({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="terminal-panel p-4 sm:p-5">
      <h2 className="terminal-label mb-1">{title}</h2>
      {sub && <p className="text-[13px] text-foreground/70 mb-4 max-w-3xl leading-relaxed">{sub}</p>}
      {children}
    </section>
  );
}

// ─── sections ────────────────────────────────────────────────────────────────
function BridgeStatus({ instances }: { instances: Instance[] }) {
  if (!instances.length) {
    return (
      <Panel title="IEB connection" sub="The local engine pushes its signal record here, signed; Copilot never connects into the PC.">
        <p className="text-sm font-mono text-muted-foreground">No IEB instance has connected yet.</p>
      </Panel>
    );
  }
  return (
    <Panel title="IEB connection" sub="The local engine pushes its signal record here, signed; Copilot never connects into the PC.">
      <div className="grid gap-3">
        {instances.map((i) => {
          const st = STATE_STYLE[i.state] ?? STATE_STYLE.OFFLINE;
          const backlog = Object.values(i.backlog || {}).reduce((a, b) => a + (Number(b) || 0), 0);
          return (
            <div key={i.instance_id} className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge cls={st.cls}>{i.state}</Badge>
                <span className="font-mono text-sm">{i.instance_id}</span>
                <span className="text-[13px] text-foreground/70">{st.text}</span>
              </div>
              <dl className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[13px] font-mono">
                <div><dt className="terminal-label">Heartbeat</dt><dd>{ago(i.last_heartbeat)}</dd></div>
                <div><dt className="terminal-label">Last signal received</dt><dd>{ago(i.last_signal_received)}</dd></div>
                <div><dt className="terminal-label">Waiting to send</dt><dd>{backlog}</dd></div>
                <div><dt className="terminal-label">Modules switched on</dt><dd>{i.modules_active?.length ?? 0}</dd></div>
              </dl>
              {i.last_error && <p className="text-[12px] font-mono text-muted-foreground break-words">Last error: {i.last_error}</p>}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function ResearchCard({ e }: { e: VersionEntry }) {
  const c = e.card;
  const reg = e.registry;
  return (
    <div className="grid gap-4 lg:grid-cols-2 text-[13px]">
      <div className="space-y-3">
        {reg?.description && <p className="text-foreground/80 leading-relaxed">{reg.description}</p>}
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 font-mono">
          <div><dt className="terminal-label">TP1 before stop</dt>
            <dd>{pct(c.tp1_before_stop.rate)} <span className="text-muted-foreground">({c.tp1_before_stop.k}/{c.tp1_before_stop.n}; 95% {pct(c.tp1_before_stop.lo)}–{pct(c.tp1_before_stop.hi)})</span></dd></div>
          <div><dt className="terminal-label">Direction right at exit</dt>
            <dd>{pct(c.direction_correct_at_exit.rate)} <span className="text-muted-foreground">(n {c.direction_correct_at_exit.n})</span></dd></div>
          <div><dt className="terminal-label">Mean R (before costs)</dt>
            <dd>{rr(c.r.mean)} <span className="text-muted-foreground">(95% {rr(c.r.lo)}..{rr(c.r.hi)}, n {c.r.n})</span></dd></div>
          <div><dt className="terminal-label">Median R</dt><dd>{rr(c.r.median)}</dd></div>
          <div><dt className="terminal-label">Avg win / avg loss</dt><dd>{rr(c.r.avg_win)} / {c.r.avg_loss == null ? "-" : `-${c.r.avg_loss.toFixed(2)}`} R</dd></div>
          <div><dt className="terminal-label">Break-even win rate</dt><dd>{pct(c.r.breakeven_win_rate)} <span className="text-muted-foreground">(actual {pct(c.r.win_rate)})</span></dd></div>
          <div><dt className="terminal-label">MFE / MAE (mean R)</dt><dd>{rr(c.mfe_r.mean)} / {rr(c.mae_r.mean)} <span className="text-muted-foreground">(n {c.mfe_r.n})</span></dd></div>
          <div><dt className="terminal-label">Median holding</dt><dd>{c.median_holding_minutes == null ? "-" : `${Math.round(c.median_holding_minutes)} min`}</dd></div>
          <div><dt className="terminal-label">Unknown exits</dt><dd>{c.unknown_exits} <span className="text-muted-foreground">(excluded)</span></dd></div>
          {e.direction_disagrees_with_votes != null && (
            <div><dt className="terminal-label">Against the vote</dt><dd>{e.direction_disagrees_with_votes}</dd></div>)}
        </dl>
        <div>
          <div className="terminal-label mb-1">Finding</div>
          <p className={cn("font-mono font-bold", FINDING_STYLE[e.finding.label])}>{e.finding.label.replace(/_/g, " ")}</p>
          <p className="text-foreground/70">{e.finding.why}</p>
          {e.finding.flags.length > 0 && <p className="font-mono text-amber-300 mt-1">{e.finding.flags.join(" · ")}</p>}
          <p className="text-muted-foreground mt-1">Limitation: {e.finding.limitations.join("; ")}. Costs: {c.costs}.</p>
        </div>
        <div>
          <div className="terminal-label mb-1">Promotion{e.promotion.next ? ` → ${e.promotion.next.replace("_", " ")}` : ""}</div>
          {e.promotion.note && <p className="text-foreground/70">{e.promotion.note}</p>}
          <ul className="space-y-1">
            {e.promotion.requirements.map((r) => (
              <li key={r.rule} className="flex gap-2">
                <span className={cn("font-mono shrink-0 w-12", r.met === true ? "text-bull" : r.met === false ? "text-bear" : "text-muted-foreground")}>
                  {r.met === true ? "MET" : r.met === false ? "NOT YET" : "OWNER"}
                </span>
                <span className="text-foreground/80">{r.rule}{r.detail ? <span className="text-muted-foreground"> - {r.detail}</span> : null}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="space-y-3">
        {(["symbol", "session", "timeframe", "weekday"] as const).map((dim) => {
          const g = e.breakdowns[dim] || {};
          const keys = Object.keys(g);
          if (!keys.length || (keys.length === 1 && keys[0] === "unknown")) return null;
          return (
            <div key={dim}>
              <div className="terminal-label mb-1">By {dim}</div>
              <div className="overflow-x-auto">
                <table className="w-full font-mono text-[12px]">
                  <thead><tr className="text-muted-foreground text-left">
                    <th className="font-normal pr-3">{dim}</th><th className="font-normal pr-3">n</th>
                    <th className="font-normal pr-3">TP1 first</th><th className="font-normal">mean R (95%)</th></tr></thead>
                  <tbody>
                    {keys.map((k) => (
                      <tr key={k} className="border-t border-border/30">
                        <td className="pr-3 py-0.5">{k}</td><td className="pr-3">{g[k].resolved}</td>
                        <td className="pr-3">{pct(g[k].tp1_before_stop)} <span className="text-muted-foreground">/{g[k].tp1_n}</span></td>
                        <td>{rr(g[k].mean_r)} <span className="text-muted-foreground">{g[k].r_lo == null ? "" : `${rr(g[k].r_lo)}..${rr(g[k].r_hi)}`}</span></td>
                      </tr>))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
        {reg && (
          <dl className="space-y-1 text-[12px]">
            {reg.signal_logic_reference && <div><dt className="terminal-label inline">Logic: </dt><dd className="inline font-mono text-foreground/70 break-all">{reg.signal_logic_reference}</dd></div>}
            {reg.score_definition && <div><dt className="terminal-label inline">Score: </dt><dd className="inline text-foreground/70">{reg.score_definition}</dd></div>}
            {reg.outcome_definition && <div><dt className="terminal-label inline">Outcome: </dt><dd className="inline text-foreground/70">{reg.outcome_definition}</dd></div>}
          </dl>
        )}
      </div>
    </div>
  );
}

function Comparison({ lab }: { lab: LabModules }) {
  const [showEmpty, setShowEmpty] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const rows = useMemo(() => lab.comparison
    .filter((r) => showEmpty || r.signals > 0)
    .sort((a, b) => (STATUS_ORDER.indexOf(a.status ?? "") - STATUS_ORDER.indexOf(b.status ?? "")) || b.resolved - a.resolved),
  [lab, showEmpty]);
  const hidden = lab.comparison.length - lab.comparison.filter((r) => r.signals > 0).length;
  return (
    <Panel title="Module comparison"
      sub={`One row per module version, measured on its own record. R is the move to the exit divided by the distance to the stop, before costs. A rate is treated as measured once its 95% interval is within ±${lab.sample_rules.rate_half_width * 100} points (about ${lab.sample_rules.n_for_10pt_rate_at_p_0_5} outcomes), mean R once within ±${lab.sample_rules.mean_r_half_width} R. Select a row for its research card.`}>
      <label className="flex items-center gap-2 text-[13px] mb-3 cursor-pointer w-fit min-h-[44px]">
        <input type="checkbox" checked={showEmpty} onChange={(e) => setShowEmpty(e.target.checked)} className="h-4 w-4 accent-[hsl(var(--primary))]" />
        Show versions with no signals yet ({hidden})
      </label>
      <div className="overflow-x-auto -mx-4 sm:mx-0">
        <table className="w-full min-w-[760px] text-[13px] font-mono">
          <thead>
            <tr className="text-left terminal-label">
              <th className="py-2 px-2 font-semibold">Module</th><th className="px-2 font-semibold">Version</th>
              <th className="px-2 font-semibold">Status</th><th className="px-2 font-semibold text-right">Signals</th>
              <th className="px-2 font-semibold text-right">Resolved</th><th className="px-2 font-semibold text-right">TP1 first</th>
              <th className="px-2 font-semibold text-right">Mean R (95%)</th><th className="px-2 font-semibold">Finding</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const key = `${r.module_id}@${r.version}`;
              const isOpen = open === key;
              const entry = lab.modules[r.module_id]?.versions[r.version];
              return (
                <Fragment key={key}>
                  <tr className={cn("border-t border-border/40 cursor-pointer hover:bg-white/[0.03]", isOpen && "bg-white/[0.03]")}
                    onClick={() => setOpen(isOpen ? null : key)}>
                    <td className="py-2 px-2">
                      <button type="button" aria-expanded={isOpen} className="text-left underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary rounded"
                        onClick={(ev) => { ev.stopPropagation(); setOpen(isOpen ? null : key); }}>
                        {r.module_id}
                      </button>
                    </td>
                    <td className="px-2 text-muted-foreground" title={r.version}>{shortV(r.version)}</td>
                    <td className="px-2"><Badge cls={STATUS_STYLE[r.status ?? ""] ?? STATUS_STYLE.DISABLED}>{r.status ?? "-"}</Badge></td>
                    <td className="px-2 text-right">{r.signals}</td>
                    <td className="px-2 text-right">{r.resolved}</td>
                    <td className="px-2 text-right">{pct(r.tp1_before_stop)} <span className="text-muted-foreground">/{r.tp1_n}</span></td>
                    <td className="px-2 text-right whitespace-nowrap">{rr(r.mean_r)} <span className="text-muted-foreground">{r.r_lo == null ? "" : `${rr(r.r_lo)}..${rr(r.r_hi)}`}</span></td>
                    <td className={cn("px-2", FINDING_STYLE[r.finding])}>{r.finding.replace(/_/g, " ")}</td>
                  </tr>
                  {isOpen && entry && (
                    <tr><td colSpan={8} className="px-2 pb-4 pt-2 bg-white/[0.02]"><ResearchCard e={entry} /></td></tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ScoreResearch({ score }: { score: LabScore }) {
  const entries = Object.entries(score.modules).flatMap(([mid, m]) =>
    Object.entries(m.versions).map(([v, s]) => ({ mid, name: m.name, v, s, excluded: m.excluded_direction_against_votes })));
  return (
    <Panel title="Consensus Score research"
      sub={`${score.score_definition} Outcome: ${score.outcome_definition}. A score band gets a measured rate only once its interval is within ±10 points; score-range labels are shown to users only after that, and only if higher scores actually went with more wins.`}>
      {entries.length === 0 && <p className="text-sm font-mono text-muted-foreground">No resolved Copilot signals with a score yet.</p>}
      <div className="grid gap-4 md:grid-cols-2">
        {entries.map(({ mid, name, v, s, excluded }) => (
          <div key={`${mid}${v}`} className="border border-border/50 rounded p-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
              <span className="font-mono text-sm">{name}</span>
              <span className="font-mono text-[12px] text-muted-foreground" title={v}>{shortV(v)} · n {s.n}</span>
            </div>
            <table className="w-full font-mono text-[12px]">
              <thead><tr className="text-muted-foreground text-left"><th className="font-normal">Score</th><th className="font-normal text-right">n</th>
                <th className="font-normal text-right">TP1 first</th><th className="font-normal text-right">95% interval</th></tr></thead>
              <tbody>
                {s.bands.map((b) => (
                  <tr key={b.band} className="border-t border-border/30">
                    <td className="py-0.5">{b.band}</td><td className="text-right">{b.n}</td>
                    <td className="text-right">{b.n ? pct(b.rate) : "-"}</td>
                    <td className={cn("text-right", !b.adequate && "text-muted-foreground")}>
                      {b.n ? `${pct(b.lo)}–${pct(b.hi)}` : "-"}{b.n > 0 && !b.adequate ? " (insufficient)" : ""}</td>
                  </tr>))}
              </tbody>
            </table>
            <p className="text-[12px] mt-2 text-foreground/80">
              Discrimination: {s.discrimination.auc == null ? s.discrimination.verdict
                : `AUC ${s.discrimination.auc.toFixed(2)} (95% ${s.discrimination.lo?.toFixed(2)}–${s.discrimination.hi?.toFixed(2)}) - ${s.discrimination.verdict}`}
            </p>
            {excluded > 0 && <p className="text-[12px] text-muted-foreground">{excluded} signal(s) traded against the vote majority - excluded from bands.</p>}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function RecentSignals({ signals }: { signals: IebSignal[] }) {
  return (
    <Panel title="Latest IEB signals" sub="As received from IEB, with the module version that produced each one. Rebuilt paper history is marked; it is never posted to Telegram.">
      {signals.length === 0 ? <p className="text-sm font-mono text-muted-foreground">No IEB signals received yet.</p> : (
        <div className="overflow-x-auto -mx-4 sm:mx-0">
          <table className="w-full min-w-[820px] text-[12px] font-mono">
            <thead><tr className="text-left terminal-label">
              <th className="py-2 px-2 font-semibold">Time</th><th className="px-2 font-semibold">Module</th><th className="px-2 font-semibold">Symbol</th>
              <th className="px-2 font-semibold">Side</th><th className="px-2 font-semibold text-right">Entry</th><th className="px-2 font-semibold text-right">Stop</th>
              <th className="px-2 font-semibold text-right">TP1</th><th className="px-2 font-semibold">Result</th><th className="px-2 font-semibold">Record</th></tr></thead>
            <tbody>
              {signals.map((s) => (
                <tr key={s.signal_id} className="border-t border-border/40" title={`signal ${s.signal_id} · version ${s.module_version}`}>
                  <td className="py-1.5 px-2 whitespace-nowrap">{utc(s.generated_at)}</td>
                  <td className="px-2">{s.module_id}</td><td className="px-2">{s.symbol}</td>
                  <td className={cn("px-2 font-bold", s.direction === "LONG" ? "text-bull" : "text-bear")}>{s.direction}</td>
                  <td className="px-2 text-right">{px(s.entry_reference)}</td><td className="px-2 text-right">{px(s.stop_reference)}</td>
                  <td className="px-2 text-right">{px(s.tp1)}</td>
                  <td className="px-2 whitespace-nowrap">{!s.resolved ? <span className="text-muted-foreground">open</span>
                    : s.exit_reason === "unknown" ? <span className="text-muted-foreground">exit unknown</span>
                    : <span className={cn((s.r_multiple ?? 0) >= 0 ? "text-bull" : "text-bear")}>{s.exit_reason} {rr(s.r_multiple)} R</span>}</td>
                  <td className="px-2 whitespace-nowrap text-muted-foreground">{s.source === "ieb_forward" ? (s.on_telegram ? "forward · Telegram" : "forward") : "rebuilt history"}</td>
                </tr>))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function Pipeline({ lab }: { lab: LabModules }) {
  const counts: Record<string, number> = {};
  Object.values(lab.modules).forEach((m) => {
    const statuses = new Set(Object.values(m.versions).map((v) => v.registry?.status).filter(Boolean) as string[]);
    const best = STATUS_ORDER.find((s) => statuses.has(s));
    if (best) counts[best] = (counts[best] ?? 0) + 1;
  });
  const steps = lab.pipeline;
  return (
    <Panel title="Promotion pipeline" sub="The rules a module version must meet to move up. The server checks them on every module's own record; nothing is promoted automatically.">
      <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        {steps.map((s, i) => (
          <li key={s} className="border border-border/50 rounded p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="font-mono text-[12px] font-bold tracking-wider">{i + 1}. {s.replace("_", " ")}</span>
              <span className="font-mono text-[12px] text-muted-foreground">{counts[s] ?? 0} {(counts[s] ?? 0) === 1 ? "module" : "modules"}</span>
            </div>
            <p className="text-[12px] text-foreground/70 leading-relaxed">{lab.pipeline_rules[s]}</p>
          </li>))}
      </ol>
      <p className="text-[12px] text-foreground/70 mt-3">{lab.pipeline_rules.DEMOTION}</p>
      <p className="text-[12px] text-muted-foreground mt-1">Switched off: {counts.DISABLED ?? 0} {(counts.DISABLED ?? 0) === 1 ? "module" : "modules"}.</p>
    </Panel>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────
export default function SignalLabPage() {
  const [lab, setLab] = useState<LabModules | null>(null);
  const [score, setScore] = useState<LabScore | null>(null);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [recent, setRecent] = useState<IebSignal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    const t = setTimeout(() => setSlow(true), 5000);
    try {
      const get = async <T,>(p: string): Promise<T> => {
        const r = await fetch(`${API_URL}${p}`, { cache: "no-store" });
        if (!r.ok) throw new Error(`${p} answered ${r.status}`);
        return r.json();
      };
      const [l, s, st, rs] = await Promise.all([
        get<LabModules>("/api/v1/lab/modules"), get<LabScore>("/api/v1/lab/score"),
        get<{ instances: Instance[] }>("/api/v1/ieb/status"), get<{ signals: IebSignal[] }>("/api/v1/ieb/signals/recent?limit=40"),
      ]);
      setLab(l); setScore(s); setInstances(st.instances); setRecent(rs.signals);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      clearTimeout(t); setSlow(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {                                   // connection status stays current
    const id = setInterval(async () => {
      try {
        const r = await fetch(`${API_URL}/api/v1/ieb/status`, { cache: "no-store" });
        if (r.ok) setInstances((await r.json()).instances);
      } catch { /* the next tick retries */ }
    }, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 space-y-4">
      <header className="space-y-1">
        <h1 className="text-xl sm:text-2xl font-mono font-bold tracking-wide">SIGNAL LAB</h1>
        <p className="text-sm text-foreground/75 max-w-3xl leading-relaxed">
          Every signal module - IEB rule modules and the Copilot generators - measured the same way, per code version:
          signals, outcomes, intervals and what each still needs. Numbers are measured, not forecast; where the sample is
          too small the page says so.
        </p>
        {lab && <p className="text-[12px] font-mono text-muted-foreground">Computed {ago(lab.generated_at)} from the canonical record.</p>}
      </header>

      {error && (
        <div role="alert" className="terminal-panel p-4 flex flex-wrap items-center gap-3">
          <span className="text-sm font-mono text-bear">Could not load the lab: {error}</span>
          <button onClick={load} className="min-h-[44px] px-4 rounded border border-border font-mono text-sm hover:bg-white/5">Retry</button>
        </div>
      )}
      {!lab && !error && (
        <div className="space-y-4" aria-busy="true">
          {[0, 1, 2].map((i) => <div key={i} className="terminal-panel h-40 animate-pulse" />)}
          {slow && <p className="text-[13px] font-mono text-muted-foreground">Waking the server - the first request after a quiet period can take up to a minute.</p>}
        </div>
      )}
      {lab && score && (
        <>
          <BridgeStatus instances={instances} />
          <Comparison lab={lab} />
          <ScoreResearch score={score} />
          <RecentSignals signals={recent} />
          <Pipeline lab={lab} />
        </>
      )}
    </main>
  );
}
