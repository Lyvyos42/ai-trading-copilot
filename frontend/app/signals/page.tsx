"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { SignalCard } from "@/components/SignalCard";
import { generateSignal, listSignals, API_URL, type Signal } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { UpgradeModal } from "@/components/UpgradeModal";
import {
  IconSignal,
  IconLock,
  IconX,
  IconShield,
  IconAgents,
  GeoOctahedron,
  GeoCylinder,
  GeoSphere,
  GeoIcosahedron,
  GeoTorus,
  GeoCube,
} from "@/components/icons/GeoIcons";

const ASSET_CLASSES = [
  "stocks", "etfs", "crypto", "forex", "metals", "energy", "indices", "futures", "agriculture"
];

const POPULAR_TICKERS: Record<string, string[]> = {
  stocks:      ["AAPL","NVDA","MSFT","TSLA","AMZN","GOOGL","META","JPM","GS","V","NFLX","AMD","PLTR","COIN","LLY"],
  etfs:        ["SPY","QQQ","DIA","IWM","VTI","GLD","TLT","XLK","XLE","XLF","SOXX","ARKK","EEM","GDX"],
  crypto:      ["BTC-USD","ETH-USD","SOL-USD","XRP-USD","BNB-USD","DOGE-USD","AVAX-USD","LINK-USD","MATIC-USD"],
  forex:       ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURGBP","EURJPY","GBPJPY","USDMXN","USDTRY"],
  metals:      ["XAUUSD","XAGUSD","XPTUSD","XPDUSD","HG=F"],
  energy:      ["USOIL","UKOIL","NATGAS","RB=F","HO=F"],
  indices:     ["US500","US100","US30","US2000","UK100","GER40","FRA40","JPN225","HK50","AUS200"],
  futures:     ["ES=F","NQ=F","YM=F","RTY=F","ZN=F","ZB=F","VX=F"],
  agriculture: ["CORN","WHEAT","SOYBEAN","COFFEE","SUGAR","COTTON","COCOA"],
};

const TICKER_ASSET_CLASS: Record<string, string> = {
  stocks: "stocks", etfs: "etfs", crypto: "crypto",
  forex: "fx", metals: "commodities", energy: "commodities",
  indices: "indices", futures: "futures", agriculture: "commodities",
};

// Pipeline stages — geometric icons replace emoji
const PIPELINE_STAGES = [
  {
    label: "MARKET DATA",
    desc: "OHLCV fetch",
    Icon: () => (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
        <polyline points="1,10 3.5,5 6,7 8.5,3.5 11,2" />
        <line x1="1" y1="12" x2="13" y2="12" />
        <line x1="1" y1="2" x2="1" y2="12" />
      </svg>
    ),
  },
  {
    label: "NEWS INTEL",
    desc: "Headline scan",
    Icon: () => (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="1.5" y="2" width="11" height="10" rx="1" />
        <line x1="4" y1="5" x2="10" y2="5" />
        <line x1="4" y1="7" x2="10" y2="7" />
        <line x1="4" y1="9" x2="7" y2="9" />
      </svg>
    ),
  },
  {
    label: "ANALYST DEBATE",
    desc: "4 agents parallel",
    Icon: () => <IconAgents size={14} color="currentColor" strokeWidth={1.2} />,
  },
  {
    label: "RISK CHECK",
    desc: "Kelly + exposure",
    Icon: () => <IconShield size={14} color="currentColor" strokeWidth={1.2} />,
  },
  {
    label: "DEBATE PROTOCOL",
    desc: "Bull vs Bear",
    Icon: () => (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="7" y1="1" x2="7" y2="13" />
        <polyline points="3,4 7,7 11,4" />
        <polyline points="3,10 7,7 11,10" />
      </svg>
    ),
  },
  {
    label: "TRADER SIGNAL",
    desc: "Final synthesis",
    Icon: () => <IconSignal size={14} color="currentColor" strokeWidth={1.2} />,
  },
];

// Agent shapes for the visual pipeline while running
const PIPELINE_AGENTS = [
  { name: "FUND",  Geo: GeoOctahedron,   color: "#D4A240" },
  { name: "TECH",  Geo: GeoCylinder,      color: "#f59e0b" },
  { name: "SENT",  Geo: GeoSphere,        color: "#7c3aed" },
  { name: "MACRO", Geo: GeoIcosahedron,   color: "#06b6d4" },
  { name: "RISK",  Geo: GeoTorus,         color: "#f97316" },
  { name: "TRADE", Geo: GeoCube,          color: "#22c55e" },
];

export default function SignalsPage() {
  const [signals, setSignals]       = useState<Signal[]>([]);
  const [loading, setLoading]       = useState<string | null>(null);
  const [waking, setWaking]         = useState(false);
  const [assetClass, setAssetClass] = useState("stocks");
  const [customTicker, setCustomTicker] = useState("");
  const [error, setError]           = useState("");
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [pipelineStage, setPipelineStage] = useState(0);

  const { isLoggedIn } = useAuth();
  const cancelRef = useRef(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastTickerRef = useRef<string>("");

  // Load existing signals from DB on mount
  useEffect(() => {
    if (!isLoggedIn) return;
    listSignals(50)
      .then((data) => setSignals(data))
      .catch(() => {}); // silent — signals will appear when generated
  }, [isLoggedIn]);

  const STAGE_DELAYS = [0, 4_000, 11_000, 25_000, 31_000, 37_000];
  useEffect(() => {
    if (!loading) { setPipelineStage(0); return; }
    setPipelineStage(0);
    const timers = STAGE_DELAYS.slice(1).map((delay, i) =>
      setTimeout(() => setPipelineStage(i + 1), delay)
    );
    return () => timers.forEach(clearTimeout);
  }, [loading]); // eslint-disable-line react-hooks/exhaustive-deps

  const cancelAnalysis = useCallback(() => {
    cancelRef.current = true;
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setLoading(null);
    setWaking(false);
    setError("Analysis cancelled.");
  }, []);

  async function handleGenerate(ticker: string) {
    if (!isLoggedIn) { window.location.href = "/login"; return; }
    cancelRef.current = false;
    lastTickerRef.current = ticker;
    setError("");
    setWaking(false);
    setLoading(ticker);

    timeoutRef.current = setTimeout(() => {
      if (cancelRef.current) return;
      cancelRef.current = true;
      setLoading(null);
      setWaking(false);
      setError("Backend took too long to respond. Render free tier may be sleeping — please retry.");
    }, 75_000);

    try {
      const warmRes = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(5_000) });
      if (!warmRes.ok) setWaking(true);
    } catch {
      setWaking(true);
    }

    if (cancelRef.current) return;

    try {
      const signal = await generateSignal(ticker, TICKER_ASSET_CLASS[assetClass] ?? assetClass);
      if (!cancelRef.current) setSignals((prev) => {
        // Avoid duplicate if signal was already loaded from DB
        const exists = prev.some((s) => s.signal_id === signal.signal_id);
        return exists ? prev : [signal, ...prev];
      });
    } catch (e: unknown) {
      if (!cancelRef.current) {
        const msg = e instanceof Error ? e.message : "Failed to generate signal";
        const isColdStart = msg.toLowerCase().includes("fetch") || msg.toLowerCase().includes("network");
        setError(isColdStart
          ? "Backend is waking up (Render free tier, ~60s). Wait a moment and try again."
          : `${msg}`
        );
      }
    } finally {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (!cancelRef.current) { setLoading(null); setWaking(false); }
    }
  }

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customTicker.trim()) {
      if (loading) cancelAnalysis();
      setTimeout(() => {
        handleGenerate(customTicker.trim().toUpperCase());
        setCustomTicker("");
      }, 0);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">

      {/* Visitor gate */}
      {!isLoggedIn && (
        <div
          className="panel"
          style={{ borderColor: "hsl(var(--primary) / 0.2)" }}
        >
          <div className="panel-header">
            <IconLock size={12} color="hsl(var(--primary))" />
            <span
              className="text-[9px] font-bold tracking-[0.1em]"
              style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--primary))" }}
            >
              SIGN IN TO USE AI SIGNAL GENERATOR
            </span>
          </div>
          <div className="p-4 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { label: "FREE", color: "hsl(var(--muted-foreground))", features: ["5 AI signals / day", "Stocks & ETFs only", "Paper trading portfolio", "Market intel & news"] },
                { label: "RETAIL — $49/mo", color: "hsl(var(--primary))", features: ["Unlimited signals", "All 8 asset classes", "All 80+ strategies", "Bull/Bear agent debate"] },
                { label: "PRO — $199/mo", color: "#f59e0b", features: ["Everything in Retail", "Custom agent tuning", "API & webhook access", "Priority support"] },
              ].map(({ label, color, features }) => (
                <div
                  key={label}
                  className="p-3"
                  style={{
                    border: `1px solid ${color}25`,
                    borderRadius: "2px",
                    background: `${color}04`,
                  }}
                >
                  <div
                    className="text-[9px] font-bold mb-2 tracking-[0.1em]"
                    style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color }}
                  >
                    {label}
                  </div>
                  <ul className="space-y-1">
                    {features.map(f => (
                      <li
                        key={f}
                        className="flex items-center gap-1.5 text-[10px]"
                        style={{ color: "hsl(var(--muted-foreground))" }}
                      >
                        <div className="h-1 w-1 shrink-0" style={{ background: color, borderRadius: "0.5px" }} />
                        {f}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <a
                href="/login"
                className="px-4 py-1.5 text-[10px] font-bold tracking-[0.08em] transition-colors"
                style={{
                  fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                  border: "1px solid hsl(var(--primary) / 0.4)",
                  borderRadius: "2px",
                  background: "hsl(var(--primary) / 0.08)",
                  color: "hsl(var(--primary))",
                }}
              >
                SIGN IN FREE
              </a>
              <a
                href="/pricing"
                className="px-4 py-1.5 text-[10px] font-bold tracking-[0.08em] transition-colors"
                style={{
                  fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                  border: "1px solid hsl(var(--border-strong))",
                  borderRadius: "2px",
                  color: "hsl(var(--muted-foreground))",
                }}
              >
                SEE PRICING
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Generator panel */}
      <div className="panel panel-active">
        <div className="panel-header">
          <IconSignal size={12} color="hsl(var(--primary))" />
          <span className="terminal-label" style={{ color: "hsl(var(--foreground) / 0.6)" }}>Signal Generator</span>
          <span className="text-[9px]" style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--muted-foreground))" }}>
            — 6-Agent LangGraph Pipeline
          </span>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="live-dot" />
            <span
              className="text-[8px] font-bold"
              style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--bull))" }}
            >
              LIVE
            </span>
          </div>
        </div>
        <div className="p-4 space-y-4">

          {/* Asset class tabs */}
          <div className="flex gap-1 flex-wrap">
            {ASSET_CLASSES.map((ac) => (
              <button
                key={ac}
                onClick={() => setAssetClass(ac)}
                className="px-3 py-1 text-[9px] font-bold tracking-[0.08em] uppercase transition-colors"
                style={{
                  fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                  border: "1px solid",
                  borderColor: assetClass === ac ? "hsl(var(--primary) / 0.5)" : "hsl(var(--border-strong))",
                  borderRadius: "2px",
                  background: assetClass === ac ? "hsl(var(--primary) / 0.08)" : "transparent",
                  color: assetClass === ac ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
                  cursor: "pointer",
                }}
              >
                {ac.replace("_", " ")}
              </button>
            ))}
          </div>

          {/* Quick tickers */}
          <div>
            <span className="terminal-label mb-2 block">
              QUICK PICK — {assetClass.replace("_", " ").toUpperCase()}
            </span>
            <div className="flex gap-1.5 flex-wrap">
              {(POPULAR_TICKERS[assetClass] || []).map((ticker) => (
                <button
                  key={ticker}
                  onClick={() => {
                    setAssetClass(TICKER_ASSET_CLASS[assetClass] ?? assetClass);
                    handleGenerate(ticker);
                  }}
                  disabled={loading !== null}
                  className="px-2.5 py-1 text-[10px] font-bold transition-all"
                  style={{
                    fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                    border: "1px solid",
                    borderColor: loading === ticker ? "hsl(var(--primary))" : "hsl(var(--border-strong))",
                    borderRadius: "2px",
                    background: loading === ticker ? "hsl(var(--primary) / 0.12)" : "transparent",
                    color: loading === ticker ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
                    cursor: loading !== null ? "not-allowed" : "pointer",
                    opacity: loading !== null && loading !== ticker ? 0.5 : 1,
                    animation: loading === ticker ? "pulse-live 1.6s ease-in-out infinite" : "none",
                  }}
                >
                  {loading === ticker ? "···" : ticker.replace("=X","").replace("-USD","").replace("=F","")}
                </button>
              ))}
            </div>
          </div>

          {/* Custom ticker */}
          <form onSubmit={handleCustomSubmit} className="flex gap-2 items-center">
            <span className="terminal-label shrink-0">CUSTOM TICKER</span>
            <div className="relative">
              <span
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[10px] font-bold"
                style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--muted-foreground) / 0.5)" }}
              >
                &rsaquo;
              </span>
              <input
                type="text"
                value={customTicker}
                onChange={(e) => setCustomTicker(e.target.value.toUpperCase())}
                placeholder="e.g. COIN, RIVN, NQ=F"
                className="input-terminal pl-6 w-52"
              />
            </div>
            <button
              type="submit"
              disabled={!customTicker.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-bold tracking-[0.08em] transition-colors"
              style={{
                fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                border: "1px solid hsl(var(--primary) / 0.4)",
                borderRadius: "2px",
                background: "hsl(var(--primary) / 0.08)",
                color: "hsl(var(--primary))",
                cursor: !customTicker.trim() ? "not-allowed" : "pointer",
                opacity: !customTicker.trim() ? 0.4 : 1,
              }}
            >
              <IconSignal size={11} color="currentColor" />
              ANALYZE
            </button>
          </form>

          {/* Error */}
          {error && (
            <div
              className="flex items-center gap-3 px-3 py-2 text-[10px]"
              style={{
                fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                color: "hsl(var(--bear))",
                background: "hsl(var(--bear) / 0.05)",
                border: "1px solid hsl(var(--bear) / 0.2)",
                borderRadius: "2px",
              }}
            >
              <span className="flex-1">ERR — {error}</span>
              {lastTickerRef.current && (
                <button
                  onClick={() => handleGenerate(lastTickerRef.current)}
                  className="shrink-0 px-2 py-0.5 font-bold border transition-colors"
                  style={{
                    borderColor: "hsl(var(--bear) / 0.4)",
                    borderRadius: "2px",
                    background: "transparent",
                    color: "hsl(var(--bear))",
                    cursor: "pointer",
                    fontSize: "9px",
                    letterSpacing: "0.1em",
                  }}
                >
                  RETRY
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Pipeline running indicator */}
      {loading && (
        <div
          className="panel"
          style={{ borderColor: waking ? "hsl(var(--warn) / 0.3)" : "hsl(var(--primary) / 0.25)" }}
        >
          <div
            className="panel-header"
            style={{ background: waking ? "hsl(var(--warn) / 0.04)" : "hsl(var(--primary) / 0.04)" }}
          >
            {waking ? (
              <>
                <div style={{ animation: "agent-pulse 0.8s ease-in-out infinite" }}>
                  <IconSignal size={12} color="hsl(var(--warn))" />
                </div>
                <span
                  className="text-[9px] font-bold tracking-[0.1em] ml-1"
                  style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--warn))" }}
                >
                  WAKING BACKEND
                </span>
                <span
                  className="ml-2 text-[9px]"
                  style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--foreground) / 0.7)" }}
                >
                  {loading}
                </span>
                <span
                  className="mx-auto text-[9px]"
                  style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--warn) / 0.6)" }}
                >
                  Render cold start — auto-retrying (~26s max)
                </span>
              </>
            ) : (
              <>
                <span
                  className="text-[9px] font-bold tracking-[0.1em]"
                  style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--primary))" }}
                >
                  PIPELINE RUNNING
                </span>
                <span
                  className="ml-2 text-[9px]"
                  style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--foreground) / 0.8)" }}
                >
                  {loading}
                </span>
              </>
            )}
            <button
              onClick={cancelAnalysis}
              className="ml-auto flex items-center gap-1 text-[9px] font-bold px-2 py-0.5 transition-colors"
              style={{
                fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                border: "1px solid hsl(var(--border-strong))",
                borderRadius: "2px",
                background: "none",
                color: "hsl(var(--muted-foreground))",
                cursor: "pointer",
                letterSpacing: "0.08em",
              }}
            >
              <IconX size={10} color="currentColor" />
              CANCEL
            </button>
          </div>

          <div className="p-4 space-y-4">

            {/* 3D agent shapes — animate while pipeline runs */}
            <div className="flex items-center justify-center gap-3 flex-wrap py-2">
              {PIPELINE_AGENTS.map(({ name, Geo, color }, i) => {
                const isCurrentStage = i === Math.min(pipelineStage, 5);
                const isPastStage = i < pipelineStage;
                return (
                  <div key={name} className="flex flex-col items-center gap-1.5">
                    <div
                      className="flex items-center justify-center"
                      style={{
                        width: 40,
                        height: 40,
                        background: isPastStage ? `${color}15` : isCurrentStage ? `${color}10` : "transparent",
                        border: `1px solid ${isPastStage ? color + "40" : isCurrentStage ? color + "30" : "hsl(var(--border))"}`,
                        borderRadius: "3px",
                        transition: "all 400ms ease",
                        opacity: isPastStage ? 0.5 : isCurrentStage ? 1 : 0.25,
                      }}
                    >
                      <div style={{ animation: isCurrentStage ? "agent-pulse 0.8s ease-in-out infinite" : `rotate-idle-octahedron 14s linear infinite`, transformStyle: "preserve-3d" }}>
                        <Geo size={26} color={color} strokeWidth={1} active={isCurrentStage} />
                      </div>
                    </div>
                    <span
                      className="text-[8px] font-bold"
                      style={{
                        fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                        color: isCurrentStage ? color : isPastStage ? `${color}80` : "hsl(var(--muted-foreground) / 0.3)",
                      }}
                    >
                      {name}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Stage progress — text indicators */}
            <div className="flex items-center gap-1 overflow-x-auto pb-1">
              {PIPELINE_STAGES.map((s, i) => {
                const done   = i < pipelineStage;
                const active = i === pipelineStage;
                const { Icon } = s;
                return (
                  <div key={s.label} className="flex items-center gap-1">
                    <div
                      className="flex items-center gap-1.5 px-2 py-1 relative overflow-hidden"
                      style={{
                        border: "1px solid",
                        borderColor: done
                          ? "hsl(var(--primary) / 0.35)"
                          : active
                          ? "hsl(var(--primary) / 0.25)"
                          : "hsl(var(--border))",
                        borderRadius: "2px",
                        background: done
                          ? "hsl(var(--primary) / 0.08)"
                          : active
                          ? "hsl(var(--primary) / 0.04)"
                          : "transparent",
                        transition: "all 300ms ease",
                      }}
                    >
                      <span
                        style={{
                          color: done ? "hsl(var(--primary))" : active ? "hsl(var(--primary) / 0.7)" : "hsl(var(--muted-foreground) / 0.3)",
                          display: "flex",
                          alignItems: "center",
                          animation: active ? "agent-pulse 0.8s ease-in-out infinite" : "none",
                        }}
                      >
                        <Icon />
                      </span>
                      <span
                        className="text-[8px] font-bold tracking-[0.08em] whitespace-nowrap"
                        style={{
                          fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                          color: done
                            ? "hsl(var(--primary))"
                            : active
                            ? "hsl(var(--primary) / 0.8)"
                            : "hsl(var(--muted-foreground) / 0.3)",
                        }}
                      >
                        {s.label}
                      </span>
                      {done && (
                        <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="hsl(var(--primary))" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="1.5,4 3,5.5 6.5,2" />
                        </svg>
                      )}
                      {/* Active stage fill animation */}
                      {active && (
                        <div
                          className="absolute bottom-0 left-0 h-[1px]"
                          style={{
                            background: "hsl(var(--primary))",
                            animation: "stage-fill 4s linear forwards",
                          }}
                        />
                      )}
                    </div>
                    {i < PIPELINE_STAGES.length - 1 && (
                      <svg width="12" height="8" viewBox="0 0 12 8" fill="none" className="shrink-0">
                        <line x1="0" y1="4" x2="8" y2="4" stroke={done ? "hsl(var(--primary) / 0.4)" : "hsl(var(--border-strong))"} strokeWidth="1" />
                        <polyline points="5,1.5 8.5,4 5,6.5" stroke={done ? "hsl(var(--primary) / 0.4)" : "hsl(var(--border-strong))"} strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                      </svg>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Signal output */}
      {signals.length === 0 && !loading ? (
        <div className="panel">
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            {/* Empty state — icosahedron wireframe */}
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none" stroke="hsl(var(--primary) / 0.15)" strokeWidth="1">
              <polygon points="20,3 35,13.5 29,30 11,30 5,13.5" />
              <line x1="20" y1="3" x2="20" y2="30" />
              <line x1="35" y1="13.5" x2="5" y2="13.5" />
            </svg>
            <span className="terminal-label">NO SIGNALS YET — SELECT A TICKER ABOVE</span>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {signals.map((signal) => (
            <SignalCard key={signal.signal_id} signal={signal} />
          ))}
        </div>
      )}

      <UpgradeModal
        isOpen={upgradeOpen}
        onClose={() => setUpgradeOpen(false)}
        feature="Unlimited AI Signals"
        requiredTier="retail"
        reason="Free accounts can run 5 AI analyses per day. Upgrade to Retail for unlimited signals across all asset classes."
      />
    </div>
  );
}
