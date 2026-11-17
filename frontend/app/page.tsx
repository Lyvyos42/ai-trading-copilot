"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

/* ── Backend response types (real IEB + Telegram + Signal Lab schemas) ── */
interface IebInstance {
  instance_id: string;
  state: string;
  version?: string | null;
  last_heartbeat?: string | null;
  last_signal_received?: string | null;
  modules_active?: string[];
}

interface IebSignal {
  signal_id: string;
  module_id: string;
  module_version?: string | null;
  generated_at: string;
  symbol: string;
  timeframe?: string | null;
  direction: string;
  entry_reference: number;
  stop_reference?: number | null;
  tp1?: number | null;
  expected_horizon?: string | null;
  session?: string | null;
  resolved: boolean;
  exit_reason?: string | null;
  r_multiple?: number | null;
  exit_timestamp?: string | null;
  on_telegram?: boolean;
}

interface TelegramRecord {
  channel?: string;
  posted: number;
  open: number;
  results: { target: number; stop: number; other: number; unknown?: number; no_stop?: number };
  tp1_before_stop?: { k: number; n: number; rate: number | null };
  r?: { n: number; mean: number | null; win_rate: number | null };
  signals?: IebSignal[];
}

interface LabModuleRow {
  module_id: string;
  version: string;
  status?: string | null;
  signals: number;
  resolved: number;
  tp1_before_stop: number | null;
  tp1_n: number;
  mean_r: number | null;
  r_lo?: number | null;
  r_hi?: number | null;
  r_n: number;
  finding?: string;
  next_step?: string;
}

interface CurvePt {
  idx: number;
  cumR: number;
  r: number;
  symbol: string;
  module: string;
  date: string;
}

function fmtPrice(px: number | null | undefined, symbol: string): string {
  if (px == null || !Number.isFinite(px)) return "—";
  const s = symbol.toUpperCase();
  if (s.includes("JPY") || s.includes("XAU") || s.includes("US30") || s.includes("USTEC") || s.includes("NAS") || s.includes("DE40") || s.includes("GER") || s.includes("US500")) {
    return px >= 1000 ? px.toFixed(1) : px.toFixed(3);
  }
  return px.toFixed(5);
}

function fmtAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function MiniCurve({ pts }: { pts: CurvePt[] }) {
  if (pts.length < 2) {
    return <div className="h-10 flex items-center text-[10px] font-mono text-slate-500">Awaiting 2+ settled trades</div>;
  }
  const W = 220, H = 40, PAD = 4;
  const vals = [0, ...pts.map((p) => p.cumR)];
  const lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  const xAt = (i: number) => PAD + (i / (pts.length - 1)) * (W - 2 * PAD);
  const yAt = (v: number) => H - PAD - ((v - lo) / span) * (H - 2 * PAD);
  const d = pts.map((p, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(1)},${yAt(p.cumR).toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1].cumR;
  const stroke = last >= 0 ? "#34d399" : "#f87171";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-10">
      <line x1={PAD} x2={W - PAD} y1={yAt(0)} y2={yAt(0)} stroke="#334155" strokeDasharray="3 3" strokeWidth="1" />
      <path d={d} fill="none" stroke={stroke} strokeWidth="1.75" />
    </svg>
  );
}

export default function LiveTerminalPage() {
  const [instances, setInstances] = useState<IebInstance[]>([]);
  const [signals, setSignals] = useState<IebSignal[]>([]);
  const [tg, setTg] = useState<TelegramRecord | null>(null);
  const [modules, setModules] = useState<LabModuleRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedModule, setSelectedModule] = useState<string>("");
  const [feedFilter, setFeedFilter] = useState<"ALL" | "OPEN" | "WON" | "STOPPED">("ALL");
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [lastSync, setLastSync] = useState<string>("—");

  const loadAll = useCallback(async () => {
    try {
      setError(null);
      const [stRes, sigRes, tgRes, labRes] = await Promise.allSettled([
        apiFetch<{ instances: IebInstance[] }>("/api/v1/ieb/status"),
        apiFetch<{ signals: IebSignal[] }>("/api/v1/ieb/signals/recent?limit=200"),
        apiFetch<TelegramRecord>("/api/v1/ieb/telegram-record"),
        apiFetch<{ comparison: LabModuleRow[] }>("/api/v1/lab/modules"),
      ]);
      if (stRes.status === "fulfilled") setInstances(stRes.value.instances || []);
      if (sigRes.status === "fulfilled") setSignals(sigRes.value.signals || []);
      if (tgRes.status === "fulfilled") setTg(tgRes.value);
      if (labRes.status === "fulfilled") setModules(labRes.value.comparison || []);
      if (stRes.status === "rejected" && sigRes.status === "rejected" && tgRes.status === "rejected") {
        setError("Backend API is waking up or unreachable. Retrying automatically...");
      }
      setLastSync(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
    const id = setInterval(loadAll, 30_000);
    return () => clearInterval(id);
  }, [loadAll]);

  const primaryIeb = instances[0] || null;
  const activeArms = primaryIeb?.modules_active?.length ?? 0;

  /* ── Combine unique recent + telegram settled signals per module ── */
  const allSignals = useMemo(() => {
    const map = new Map<string, IebSignal>();
    for (const s of tg?.signals || []) map.set(s.signal_id, s);
    for (const s of signals) map.set(s.signal_id, s);
    return Array.from(map.values());
  }, [signals, tg]);

  const curvesByModule = useMemo(() => {
    const grouped = new Map<string, IebSignal[]>();
    for (const s of allSignals) {
      if (!s.resolved || s.r_multiple == null || !Number.isFinite(s.r_multiple)) continue;
      const arr = grouped.get(s.module_id) || [];
      arr.push(s);
      grouped.set(s.module_id, arr);
    }
    const out = new Map<string, CurvePt[]>();
    Array.from(grouped.entries()).forEach(([mid, arr]) => {
      arr.sort((a, b) => new Date(a.exit_timestamp || a.generated_at).getTime() - new Date(b.exit_timestamp || b.generated_at).getTime());
      let cum = 0;
      out.set(mid, arr.map((s, idx) => {
        const r = Number(s.r_multiple || 0);
        cum += r;
        return {
          idx,
          cumR: Number(cum.toFixed(3)),
          r,
          symbol: s.symbol,
          module: mid,
          date: new Date(s.exit_timestamp || s.generated_at).toLocaleDateString([], { month: "short", day: "numeric" }),
        };
      }));
    });
    return out;
  }, [allSignals]);

  /* ── Separate Module Cards (sorted by positive mean_r / resolved count) ── */
  const moduleCards = useMemo(() => {
    return [...modules]
      .filter((m) => m.signals > 0)
      .sort((a, b) => {
        const aHas = (curvesByModule.get(a.module_id)?.length || 0) >= 2 ? 1 : 0;
        const bHas = (curvesByModule.get(b.module_id)?.length || 0) >= 2 ? 1 : 0;
        if (bHas !== aHas) return bHas - aHas;
        return ((b.mean_r ?? -99) - (a.mean_r ?? -99)) || (b.resolved - a.resolved);
      });
  }, [modules, curvesByModule]);

  const positiveModules = useMemo(
    () => moduleCards.filter((m) => m.resolved >= 2 && (m.mean_r ?? -1) > 0),
    [moduleCards]
  );

  /* ── Auto-select top positive module with >=2 settled points ── */
  const activeModuleId = useMemo(() => {
    if (selectedModule && curvesByModule.has(selectedModule)) return selectedModule;
    const best = moduleCards.find((m) => (curvesByModule.get(m.module_id)?.length || 0) >= 2);
    if (best) return best.module_id;
    const firstKey = curvesByModule.keys().next().value;
    return firstKey || "";
  }, [selectedModule, moduleCards, curvesByModule]);

  const activeCurve = useMemo(() => curvesByModule.get(activeModuleId) || [], [curvesByModule, activeModuleId]);

  /* ── Real Net R by Symbol (across recent settled signals) ── */
  const bySymbol = useMemo(() => {
    const map = new Map<string, { symbol: string; netR: number; n: number; wins: number }>();
    for (const s of signals) {
      if (!s.resolved || s.r_multiple == null || !Number.isFinite(s.r_multiple)) continue;
      const cur = map.get(s.symbol) || { symbol: s.symbol, netR: 0, n: 0, wins: 0 };
      const r = Number(s.r_multiple || 0);
      cur.netR += r;
      cur.n += 1;
      if (r > 0) cur.wins += 1;
      map.set(s.symbol, cur);
    }
    return Array.from(map.values()).sort((a, b) => b.netR - a.netR).slice(0, 8);
  }, [signals]);

  /* ── Right Rail Filtered Signals ── */
  const filteredFeed = useMemo(() => {
    return signals.filter((s) => {
      if (feedFilter === "OPEN") return !s.resolved;
      if (feedFilter === "WON") return s.resolved && (s.exit_reason === "target" || Number(s.r_multiple || 0) > 0);
      if (feedFilter === "STOPPED") return s.resolved && (s.exit_reason === "stop" || Number(s.r_multiple || 0) < 0);
      return true;
    }).slice(0, 40);
  }, [signals, feedFilter]);

  /* ── SVG Geometry for Selected Module's Independent Curve ── */
  const chartSvg = useMemo(() => {
    const W = 760, H = 220, PAD_L = 46, PAD_R = 16, PAD_T = 16, PAD_B = 26;
    if (!activeCurve.length) return null;
    const vals = [0, ...activeCurve.map((p) => p.cumR)];
    const minV = Math.min(...vals);
    const maxV = Math.max(0.5, ...vals);
    const span = Math.max(0.5, maxV - minV);
    const xAt = (i: number) => PAD_L + (activeCurve.length === 1 ? (W - PAD_L - PAD_R) / 2 : (i / (activeCurve.length - 1)) * (W - PAD_L - PAD_R));
    const yAt = (v: number) => PAD_T + ((maxV - v) / span) * (H - PAD_T - PAD_B);
    const pts = activeCurve.map((p, i) => ({ ...p, x: xAt(i), y: yAt(p.cumR) }));
    const lineD = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
    const zeroY = yAt(0);
    const areaD = `${lineD} L${pts[pts.length - 1].x.toFixed(1)},${zeroY.toFixed(1)} L${pts[0].x.toFixed(1)},${zeroY.toFixed(1)} Z`;
    const isPos = pts[pts.length - 1].cumR >= 0;
    return { W, H, PAD_L, PAD_R, PAD_T, PAD_B, pts, lineD, areaD, zeroY, minV, maxV, isPos };
  }, [activeCurve]);

  const activeHover = hoverIdx != null && chartSvg?.pts[hoverIdx] ? chartSvg.pts[hoverIdx] : chartSvg?.pts[chartSvg.pts.length - 1] ?? null;

  return (
    <div className="min-h-screen bg-[#070B12] text-slate-100 px-4 py-4 max-w-[1680px] mx-auto space-y-4">
      {/* Top Status & Refresh Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-base font-bold tracking-wider uppercase font-mono text-white">
              LIVE IEB &amp; TELEGRAM TERMINAL
            </h1>
            <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              INDEPENDENT MODULE CURVES
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Each strategy and module is measured independently—click any module card to inspect its standalone R-curve.
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="text-slate-400">Synced: <span className="text-slate-200">{lastSync}</span></span>
          <button
            onClick={loadAll}
            className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 transition cursor-pointer"
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-amber-500/10 border border-amber-500/30 text-amber-300 px-3 py-2 rounded text-xs font-mono">
          {error}
        </div>
      )}

      {/* 1. TOP KPI STRIP */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-[#0D131F] border border-slate-800 rounded-lg p-3.5">
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>IEB BRIDGE STATUS</span>
            <span className={cn(
              "font-bold",
              primaryIeb?.state === "CONNECTED" ? "text-emerald-400" :
              primaryIeb?.state === "PAUSED" ? "text-amber-400" : "text-red-400"
            )}>
              {primaryIeb?.state ?? (loading ? "LOADING" : "OFFLINE")}
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-1">
            {activeArms} <span className="text-sm font-normal text-slate-400">ACTIVE ARMS</span>
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-1">
            Instance: <span className="text-slate-200">{primaryIeb?.instance_id ?? "—"}</span> &bull; Heartbeat {fmtAgo(primaryIeb?.last_heartbeat)}
          </div>
        </div>

        <div className="bg-[#0D131F] border border-slate-800 rounded-lg p-3.5">
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>TELEGRAM @NEURALICC</span>
            <Link href="/telegram-record" className="text-cyan-400 hover:underline">AUDIT &rarr;</Link>
          </div>
          <div className="text-2xl font-bold font-mono text-cyan-300 mt-1">
            {tg ? tg.posted : "—"} <span className="text-sm font-normal text-slate-400">POSTED</span>
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-1">
            {tg ? (
              <>
                <span className="text-cyan-300">{tg.open} open</span> &bull;{" "}
                <span className="text-emerald-400">{tg.results.target} TP1</span> &bull;{" "}
                <span className="text-red-400">{tg.results.stop} SL</span>
              </>
            ) : "Loading Telegram record..."}
          </div>
        </div>

        <div className="bg-[#0D131F] border border-slate-800 rounded-lg p-3.5">
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>SIGNAL LAB MODULES</span>
            <Link href="/signal-lab" className="text-cyan-400 hover:underline">OPEN LAB &rarr;</Link>
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-1">
            {moduleCards.length} <span className="text-sm font-normal text-slate-400">TRACKED</span>
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-1">
            {moduleCards.reduce((acc, m) => acc + m.resolved, 0)} independent settlements recorded
          </div>
        </div>

        <div className="bg-[#0D131F] border border-slate-800 rounded-lg p-3.5">
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>POSITIVE MODULES</span>
            <span className="text-emerald-400 font-bold">{positiveModules.length} WINNERS</span>
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
            {positiveModules[0]?.mean_r != null ? `+${positiveModules[0].mean_r.toFixed(2)}R` : "—"}
            <span className="text-xs font-normal text-slate-400 ml-1.5">TOP MEAN</span>
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-1 truncate">
            Leader: <span className="text-slate-200">{positiveModules[0]?.module_id ?? "—"}</span>
          </div>
        </div>
      </section>

      {/* 2. MAIN WORKSPACE: LEFT CHARTS (2/3) + RIGHT LIVE SIGNALS (1/3) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
        <div className="xl:col-span-8 space-y-4">
          {/* Chart 1: Selected Module's Independent R-Curve */}
          <div className="bg-[#0D131F] border border-slate-800 rounded-lg p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <div>
                <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-200">
                  MODULE OUTCOME CURVE: <span className="text-cyan-300">{activeModuleId || "—"}</span>
                </h2>
                {activeHover && (
                  <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                    {activeHover.date} &bull; <span className="text-slate-200">{activeHover.symbol}</span> &bull;{" "}
                    Trade: <span className={activeHover.r >= 0 ? "text-emerald-400" : "text-red-400"}>{activeHover.r >= 0 ? "+" : ""}{activeHover.r.toFixed(2)}R</span> &bull;{" "}
                    Module Cum: <span className={activeHover.cumR >= 0 ? "text-emerald-400 font-bold" : "text-red-400 font-bold"}>{activeHover.cumR >= 0 ? "+" : ""}{activeHover.cumR.toFixed(2)}R</span>
                  </p>
                )}
              </div>

              <select
                value={activeModuleId}
                onChange={(e) => { setSelectedModule(e.target.value); setHoverIdx(null); }}
                className="bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs font-mono text-slate-200"
              >
                {Array.from(curvesByModule.keys()).sort().map((mid) => (
                  <option key={mid} value={mid}>{mid} ({curvesByModule.get(mid)?.length || 0})</option>
                ))}
              </select>
            </div>

            {chartSvg ? (
              <svg
                viewBox={`0 0 ${chartSvg.W} ${chartSvg.H}`}
                className="w-full h-56 select-none"
                onMouseLeave={() => setHoverIdx(null)}
              >
                <defs>
                  <linearGradient id="modEqFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={chartSvg.isPos ? "#10B981" : "#EF4444"} stopOpacity="0.28" />
                    <stop offset="100%" stopColor={chartSvg.isPos ? "#10B981" : "#EF4444"} stopOpacity="0.02" />
                  </linearGradient>
                </defs>
                <line
                  x1={chartSvg.PAD_L} x2={chartSvg.W - chartSvg.PAD_R}
                  y1={chartSvg.zeroY} y2={chartSvg.zeroY}
                  stroke="#334155" strokeDasharray="4 4" strokeWidth="1"
                />
                <text x={chartSvg.PAD_L - 6} y={chartSvg.zeroY + 3} textAnchor="end" className="fill-slate-500 text-[10px] font-mono">0R</text>
                <text x={chartSvg.PAD_L - 6} y={chartSvg.PAD_T + 8} textAnchor="end" className="fill-slate-400 text-[10px] font-mono">{chartSvg.maxV.toFixed(1)}R</text>
                <text x={chartSvg.PAD_L - 6} y={chartSvg.H - chartSvg.PAD_B} textAnchor="end" className="fill-slate-400 text-[10px] font-mono">{chartSvg.minV.toFixed(1)}R</text>

                <path d={chartSvg.areaD} fill="url(#modEqFill)" />
                <path d={chartSvg.lineD} fill="none" stroke={chartSvg.isPos ? "#34d399" : "#f87171"} strokeWidth="2.2" />

                {chartSvg.pts.map((p, i) => (
                  <g key={i}>
                    <circle
                      cx={p.x} cy={p.y} r={hoverIdx === i ? 4.5 : 2.5}
                      className={cn(
                        hoverIdx === i ? "fill-white stroke-cyan-400 stroke-2" : p.r >= 0 ? "fill-emerald-400" : "fill-red-400"
                      )}
                    />
                    <rect
                      x={p.x - 10} y={chartSvg.PAD_T} width={20} height={chartSvg.H - chartSvg.PAD_T - chartSvg.PAD_B}
                      fill="transparent"
                      onMouseEnter={() => setHoverIdx(i)}
                    />
                  </g>
                ))}
              </svg>
            ) : (
              <div className="h-56 flex items-center justify-center text-xs font-mono text-slate-500">
                {loading ? "Loading module outcome curve..." : "Select a module with settled trades to view its curve."}
              </div>
            )}
          </div>

          {/* Section 2: Separate Cards for Each Module (with Independent Mini Curve + Expectancy + Win Rate) */}
          <div className="bg-[#0D131F] border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-200">
                  INDEPENDENT STRATEGY &amp; MODULE CARDS
                </h2>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Separate curve, expectancy, and win rate per module. Click any card to inspect above.
                </p>
              </div>
              <Link href="/signal-lab" className="text-xs font-mono text-cyan-400 hover:underline">
                Full Signal Lab &rarr;
              </Link>
            </div>

            {moduleCards.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {moduleCards.map((m) => {
                  const wrPct = m.tp1_before_stop != null ? m.tp1_before_stop * 100 : null;
                  const meanR = m.mean_r;
                  const rPos = meanR != null && meanR >= 0;
                  const pts = curvesByModule.get(m.module_id) || [];
                  const selected = activeModuleId === m.module_id;
                  return (
                    <button
                      key={`${m.module_id}@${m.version}`}
                      type="button"
                      onClick={() => { if (pts.length) { setSelectedModule(m.module_id); setHoverIdx(null); } }}
                      className={cn(
                        "text-left bg-[#111927] border rounded-lg p-3 flex flex-col justify-between gap-2 transition cursor-pointer",
                        selected ? "border-cyan-400/70 ring-1 ring-cyan-400/30" : "border-slate-800 hover:border-slate-700"
                      )}
                    >
                      <div className="flex items-start justify-between gap-2 w-full">
                        <div className="min-w-0">
                          <div className="text-xs font-bold font-mono text-white truncate" title={m.module_id}>
                            {m.module_id}
                          </div>
                          <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                            v:{m.version} {m.status ? `• ${m.status}` : ""}
                          </div>
                        </div>
                        <span className={cn(
                          "px-1.5 py-0.5 rounded text-[11px] font-mono font-bold shrink-0",
                          meanR == null ? "bg-slate-800 text-slate-400" :
                          rPos ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400"
                        )}>
                          {meanR == null ? "—" : `${rPos ? "+" : ""}${meanR.toFixed(2)}R`}
                        </span>
                      </div>

                      {/* Independent Mini Outcome Curve */}
                      <MiniCurve pts={pts} />

                      {/* Win Rate bar */}
                      <div className="w-full">
                        <div className="flex justify-between text-[11px] font-mono mb-1">
                          <span className="text-slate-400">Win Rate (TP1)</span>
                          <span className="text-slate-200 font-semibold">
                            {wrPct != null ? `${wrPct.toFixed(1)}%` : "—"}
                          </span>
                        </div>
                        <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded-full transition-all",
                              wrPct == null ? "bg-slate-600" : wrPct >= 50 ? "bg-emerald-400" : wrPct >= 35 ? "bg-amber-400" : "bg-red-400"
                            )}
                            style={{ width: `${wrPct != null ? Math.min(100, Math.max(4, wrPct)) : 0}%` }}
                          />
                        </div>
                      </div>

                      <div className="flex items-center justify-between w-full text-[10px] font-mono text-slate-400 pt-1 border-t border-slate-800/80">
                        <span>{m.resolved}/{m.signals} resolved</span>
                        <span className="truncate max-w-[140px]" title={m.finding || ""}>{m.finding || "accumulating"}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="py-8 text-center text-xs font-mono text-slate-500">
                {loading ? "Loading module cards..." : "No modules recorded yet."}
              </div>
            )}
          </div>

          {/* Section 3: Outcome Distribution & Net R by Symbol */}
          <div className="bg-[#0D131F] border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-200">
                OUTCOME DISTRIBUTION &amp; NET R BY SYMBOL
              </h2>
              <span className="text-[11px] font-mono text-slate-400">Recent 200 signals</span>
            </div>
            {bySymbol.length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {bySymbol.map((row) => {
                  const wr = row.n ? (100 * row.wins) / row.n : 0;
                  const pos = row.netR >= 0;
                  return (
                    <div key={row.symbol} className="bg-[#111927] border border-slate-800 rounded p-2.5 font-mono">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-white">{row.symbol}</span>
                        <span className={pos ? "text-emerald-400 font-bold" : "text-red-400 font-bold"}>
                          {pos ? "+" : ""}{row.netR.toFixed(2)}R
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden my-2">
                        <div
                          className={cn("h-full rounded-full", pos ? "bg-emerald-400" : "bg-red-400")}
                          style={{ width: `${Math.min(100, Math.max(8, wr))}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[10px] text-slate-400">
                        <span>{row.wins}W / {row.n - row.wins}L</span>
                        <span>{wr.toFixed(0)}% WR</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="py-8 text-center text-xs font-mono text-slate-500">No symbol outcome breakdown available yet.</div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: LIVE IEB & TELEGRAM SIGNALS */}
        <aside className="xl:col-span-4 bg-[#0D131F] border border-slate-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-200">
              LIVE IEB &amp; TELEGRAM SIGNALS
            </h2>
            <span className="text-[11px] font-mono text-slate-400">{filteredFeed.length} shown</span>
          </div>

          <div className="flex items-center gap-1 mb-3 bg-slate-900 border border-slate-800 rounded p-0.5 text-[11px] font-mono">
            {(["ALL", "OPEN", "WON", "STOPPED"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFeedFilter(f)}
                className={cn(
                  "flex-1 py-1 rounded transition cursor-pointer",
                  feedFilter === f ? "bg-cyan-500/20 text-cyan-300 font-bold" : "text-slate-400 hover:text-slate-200"
                )}
              >
                {f}
              </button>
            ))}
          </div>

          <div className="space-y-2.5 max-h-[960px] overflow-y-auto pr-1">
            {filteredFeed.map((s) => {
              const isLong = s.direction?.toUpperCase() === "LONG" || s.direction?.toUpperCase() === "BUY";
              const rVal = s.r_multiple != null ? Number(s.r_multiple) : null;
              const isWin = s.resolved && (s.exit_reason === "target" || (rVal != null && rVal > 0));
              const isLoss = s.resolved && (s.exit_reason === "stop" || (rVal != null && rVal < 0));
              const rr =
                s.stop_reference != null && s.tp1 != null && Math.abs(s.entry_reference - s.stop_reference) > 0
                  ? Math.abs(s.tp1 - s.entry_reference) / Math.abs(s.entry_reference - s.stop_reference)
                  : null;

              return (
                <div
                  key={s.signal_id}
                  className={cn(
                    "bg-[#111927] border rounded-lg p-3 font-mono text-xs transition",
                    !s.resolved ? "border-cyan-500/30" : isWin ? "border-emerald-500/30" : isLoss ? "border-red-500/30" : "border-slate-800"
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white text-sm">{s.symbol}</span>
                      <span className={cn(
                        "px-1.5 py-0.5 rounded text-[10px] font-bold",
                        isLong ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400"
                      )}>
                        {isLong ? "BUY" : "SELL"}
                      </span>
                      {s.timeframe && <span className="text-[10px] text-slate-400">{s.timeframe}</span>}
                    </div>

                    <span className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-bold",
                      !s.resolved ? "bg-cyan-500/15 text-cyan-300" :
                      isWin ? "bg-emerald-500/15 text-emerald-400" :
                      isLoss ? "bg-red-500/15 text-red-400" : "bg-slate-800 text-slate-300"
                    )}>
                      {!s.resolved ? "OPEN" : rVal != null ? `${rVal >= 0 ? "+" : ""}${rVal.toFixed(2)}R` : (s.exit_reason || "CLOSED").toUpperCase()}
                    </span>
                  </div>

                  <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between">
                    <span className="truncate max-w-[200px]" title={s.module_id}>{s.module_id}</span>
                    <span>{fmtAgo(s.generated_at)}</span>
                  </div>

                  <div className="grid grid-cols-3 gap-1.5 mt-2 pt-2 border-t border-slate-800/80 text-[11px]">
                    <div>
                      <span className="text-slate-500 block text-[9px]">ENTRY</span>
                      <span className="text-slate-200">{fmtPrice(s.entry_reference, s.symbol)}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[9px]">SL</span>
                      <span className="text-red-300">{fmtPrice(s.stop_reference, s.symbol)}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[9px]">TP1 {rr != null ? `(${rr.toFixed(1)}R)` : ""}</span>
                      <span className="text-emerald-300">{fmtPrice(s.tp1, s.symbol)}</span>
                    </div>
                  </div>

                  {s.on_telegram && (
                    <div className="mt-1.5 text-[10px] text-sky-400">
                      Posted on Telegram @NeuralICC
                    </div>
                  )}
                </div>
              );
            })}

            {!loading && filteredFeed.length === 0 && (
              <div className="py-10 text-center text-xs font-mono text-slate-500">
                No signals match this filter.
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
