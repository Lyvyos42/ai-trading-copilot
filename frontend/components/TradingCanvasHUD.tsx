"use client";

import { useState, useRef, useEffect } from "react";
import {
  Target,
  ArrowUpRight,
  ArrowDownRight,
  Copy,
  Check,
  Shield,
  Layers,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Plus,
  X,
  Search,
  Zap,
  Activity,
  Play,
} from "lucide-react";
import { cn, formatPrice, formatPct, formatPositionSize } from "@/lib/utils";
import type { Signal } from "@/lib/api";
import { SymbolPicker } from "@/components/SymbolPicker";

interface TradingCanvasHUDProps {
  ticker: string;
  onSelectTicker: (ticker: string) => void;
  signal: Signal | null;
  activeInterval: string;
  onIntervalChange: (interval: string) => void;
  show3D: boolean;
  onToggle3D: () => void;
  onAdoptSignal?: (signal: Signal) => void;
  isAdopted?: boolean;
  onExecutePaperTrade?: (signal: Signal) => void;
  onGenerate?: (ticker: string) => void;
  analyzing?: boolean;
  /** Emitted whenever the pinned watchlist changes, so callers that need to
   *  ACT on it - SCAN NOW - operate on the list the user can actually see.
   *  This component stays the owner; consumers mirror it. */
  onWatchlistChange?: (symbols: string[]) => void;
  /** "chart" | "split" | "flow" - the toggle cycles through all three, so the
   *  label has to say which one the next press gives you. */
  canvasMode?: "chart" | "split" | "flow";
}

const INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"];

const DEFAULT_PINNED = ["AAPL", "BTC-USD", "NVDA", "XAUUSD", "EURUSD=X", "TSLA", "US500"];

// ASSET_SUGGESTIONS lived here: eleven hardcoded instruments that were the
// ONLY thing the watchlist search could find. Deleted rather than left
// dormant - it is the list that made a 283-instrument catalogue invisible,
// and a stale copy of a catalogue is worse than no copy. See SymbolPicker.

export function TradingCanvasHUD({
  ticker,
  onSelectTicker,
  signal,
  activeInterval,
  onIntervalChange,
  show3D,
  onToggle3D,
  onAdoptSignal,
  isAdopted = false,
  onExecutePaperTrade,
  onGenerate,
  analyzing = false,
  onWatchlistChange,
  canvasMode = "chart",
}: TradingCanvasHUDProps) {
  const [copied, setCopied] = useState(false);
  const [pinnedTabs, setPinnedTabs] = useState<string[]>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("cockpit_pinned_tabs");
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length > 0) return parsed;
        } catch {}
      }
    }
    return DEFAULT_PINNED;
  });

  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  // The picker is portalled to document.body to escape the ribbon's
  // overflow-x-auto and the dashboard's overflow-hidden, so it needs an
  // anchor element to measure its position from.
  const addSymbolRef = useRef<HTMLButtonElement>(null);

  // Save pinned tabs to localStorage, and tell the parent.
  //
  // SCAN NOW used to scan a list hardcoded in dashboard/page.tsx that neither
  // matched this bar nor the background scanner's config - three unconnected
  // symbol lists, so the button scanned symbols the user could not see and
  // skipped one that was right in front of them.
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("cockpit_pinned_tabs", JSON.stringify(pinnedTabs));
    }
    onWatchlistChange?.(pinnedTabs);
  }, [pinnedTabs, onWatchlistChange]);

  // Ensure current active ticker is present in pinned tabs
  useEffect(() => {
    if (ticker && !pinnedTabs.includes(ticker)) {
      setPinnedTabs((prev) => [...prev, ticker]);
    }
  }, [ticker, pinnedTabs]);

  // Focus input on search open
  useEffect(() => {
    if (searchOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }
  }, [searchOpen]);

  function handleSelectSymbol(sym: string) {
    const cleanSym = sym.trim().toUpperCase();
    if (!cleanSym) return;
    if (!pinnedTabs.includes(cleanSym)) {
      setPinnedTabs((prev) => [...prev, cleanSym]);
    }
    onSelectTicker(cleanSym);
    // The panel is NOT closed here. Adding one instrument is the rare case;
    // building a watchlist means adding several, and closing after each one
    // forces the user to reopen and re-find their place in the catalogue.
    // SymbolPicker closes itself on Escape or an outside click.
    setSearchQuery("");
  }

  function handleRemoveTab(e: React.MouseEvent, tab: string) {
    e.stopPropagation();
    if (pinnedTabs.length <= 1) return;
    const remaining = pinnedTabs.filter((t) => t !== tab);
    setPinnedTabs(remaining);
    if (ticker === tab) {
      onSelectTicker(remaining[0]);
    }
  }

  // STRICT SYMBOL MATCH: Ensure the signal belongs to the active ticker
  const matchingSignal =
    signal && signal.ticker.toUpperCase() === ticker.toUpperCase() ? signal : null;

  const isNoSignal =
    !matchingSignal ||
    matchingSignal.status === "NO_SIGNAL" ||
    matchingSignal.direction === "NEUTRAL";
  const isShort = matchingSignal?.direction === "SHORT";
  const entry = matchingSignal?.entry_price || matchingSignal?.current_price || null;
  const target = matchingSignal?.research_target || matchingSignal?.take_profit_1 || null;
  const inval = matchingSignal?.invalidation_level || matchingSignal?.stop_loss || null;
  const spot = matchingSignal?.current_price || entry;

  let journeyPct = 50;
  if (entry && target && inval && spot) {
    if (isShort) {
      const totalDist = inval - target;
      if (totalDist > 0) {
        journeyPct = Math.max(0, Math.min(100, ((inval - spot) / totalDist) * 100));
      }
    } else {
      const totalDist = target - inval;
      if (totalDist > 0) {
        journeyPct = Math.max(0, Math.min(100, ((spot - inval) / totalDist) * 100));
      }
    }
  }

  const targetDelta =
    target && entry && entry > 0
      ? isShort
        ? ((entry - target) / entry) * 100
        : ((target - entry) / entry) * 100
      : null;

  const invalDelta =
    inval && entry && entry > 0
      ? isShort
        ? -((inval - entry) / entry) * 100
        : ((inval - entry) / entry) * 100
      : null;

  const handleCopy = () => {
    if (!matchingSignal) return;
    const text = `${matchingSignal.ticker} ${matchingSignal.direction}\nEntry: ${entry || "Market"}\nTarget: ${target || "—"}\nInvalidation: ${inval || "—"}\nR:R: ${matchingSignal.risk_reward_ratio || "—"}\nSize: ${formatPositionSize(matchingSignal.position_size_pct)}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };


  return (
    <div className="border-b border-border/40 bg-surface-1/95 backdrop-blur-md flex flex-col z-20 shrink-0">
      {/* 2027 ROW 1: Interactive Multi-Asset Ribbon & Timeframes */}
      <div className="flex items-center justify-between px-2.5 py-1.5 border-b border-border/30 gap-2 overflow-x-auto scrollbar-none">
        {/* Left: Ticker Switcher Ribbon Tabs */}
        <div className="flex items-center gap-1 shrink-0">
          <span className="text-[12px] font-mono text-muted-foreground uppercase mr-1 hidden sm:inline">
            WATCHLIST:
          </span>

          {pinnedTabs.map((sym) => {
            const isActive = ticker === sym;
            return (
              <div
                key={sym}
                onClick={() => onSelectTicker(sym)}
                className={cn(
                  "group flex items-center gap-1.5 px-2 py-0.5 rounded cursor-pointer text-xs font-mono transition-all border",
                  isActive
                    ? "bg-primary/15 text-primary border-primary font-bold shadow-[0_0_10px_rgba(212,162,64,0.15)]"
                    : "bg-surface-2/60 text-muted-foreground border-border/40 hover:text-foreground hover:bg-surface-3"
                )}
              >
                <span>{sym}</span>
                {pinnedTabs.length > 1 && (
                  <button
                    onClick={(e) => handleRemoveTab(e, sym)}
                    className="opacity-0 group-hover:opacity-100 hover:text-bear transition-opacity p-0.5"
                    title={`Close ${sym}`}
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                )}
              </div>
            );
          })}

          {/* Add Symbol / Search Dialog Button */}
          <div className="relative">
            <button
              ref={addSymbolRef}
              onClick={() => setSearchOpen(!searchOpen)}
              className={cn(
                "flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono border transition-colors",
                searchOpen
                  ? "bg-primary text-primary-foreground border-primary font-bold"
                  : "bg-surface-2 text-muted-foreground border-border/40 hover:text-foreground hover:bg-surface-3"
              )}
              title="Add or Switch Symbol"
            >
              <Plus className="h-3 w-3" />
              <span className="text-[12px] font-bold">ADD SYMBOL</span>
            </button>

            {/* Fast Symbol Search Palette Dropdown */}
            {searchOpen && (
              /* Browsable catalogue, not a text box.
                 Was a filter over eleven hardcoded suggestions, so a user who
                 did not already know a ticker had no way to find one. The
                 backend has carried 283 instruments across 11 asset classes
                 all along; SymbolPicker reads them. Multi-add keeps the panel
                 open so several can be pinned in one pass. */
              <SymbolPicker
                anchorRef={addSymbolRef}
                selected={pinnedTabs}
                multi
                onSelect={handleSelectSymbol}
                onClose={() => setSearchOpen(false)}
              />
            )}
          </div>
        </div>

        {/* Right: Timeframe Interval Pills & 3D Order Flow Toggle */}
        <div className="flex items-center gap-1.5 shrink-0">
          <div className="flex items-center gap-0.5 bg-surface-2 p-0.5 rounded border border-border/40">
            {INTERVALS.map((inv) => (
              <button
                key={inv}
                onClick={() => onIntervalChange(inv)}
                className={cn(
                  "px-1.5 py-0.5 rounded text-[12px] font-mono transition-colors",
                  activeInterval === inv
                    ? "bg-primary text-primary-foreground font-bold shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {inv.toUpperCase()}
              </button>
            ))}
          </div>

          <button
            onClick={onToggle3D}
            className={cn(
              "flex items-center gap-1 px-2 py-0.5 rounded text-[12px] font-mono border transition-colors",
              canvasMode !== "chart"
                ? "bg-primary text-primary-foreground font-bold border-primary"
                : "border-border/40 hover:bg-surface-2 text-muted-foreground"
            )}
            title={
              canvasMode === "chart" ? "Show order flow beneath the chart"
              : canvasMode === "split" ? "Order flow only"
              : "Back to the chart"
            }
          >
            <Layers className="h-3 w-3" />
            <span className="hidden sm:inline">
              {canvasMode === "chart" ? "ORDER FLOW 3D"
               : canvasMode === "split" ? "SPLIT: CHART + FLOW"
               : "FLOW ONLY"}
            </span>
          </button>
        </div>
      </div>

      {/* 2027 ROW 2: Floating Glassmorphic Telemetry HUD & Target Rays */}
      <div className="px-3 py-2 flex flex-wrap items-center justify-between gap-2">
        {/* Left Telemetry Cluster */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <span className="text-base font-mono font-bold text-foreground tracking-tight">
              {ticker}
            </span>
            <span
              className={cn(
                "px-2 py-0.5 rounded text-[12px] font-mono font-bold uppercase border",
                matchingSignal && matchingSignal.direction === "LONG"
                  ? "bg-bull/15 text-bull border-bull/30"
                  : matchingSignal && matchingSignal.direction === "SHORT"
                  ? "bg-bear/15 text-bear border-bear/30"
                  : "bg-surface-2 text-muted-foreground border-border/40"
              )}
            >
              {matchingSignal ? matchingSignal.direction : "MONITORING"}
            </span>
            {matchingSignal?.asset_class && (
              <span className="text-[12px] font-mono text-muted-foreground border border-border/40 px-1 py-0.2 rounded uppercase">
                {matchingSignal.asset_class}
              </span>
            )}
          </div>

          {/* Key Floating Telemetry Chips */}
          <div className="hidden lg:flex items-center gap-1.5 pl-2 border-l border-border/40">
            {matchingSignal && !isNoSignal && entry && target && inval ? (
              <>
                <div className="px-2 py-0.5 rounded bg-surface-2/80 border border-border/30 text-[12px] font-mono">
                  <span className="text-muted-foreground">ENTRY: </span>
                  <span className="font-bold text-foreground">{formatPrice(entry, ticker)}</span>
                </div>

                <div className="px-2 py-0.5 rounded bg-bull/10 border border-bull/30 text-[12px] font-mono text-bull flex items-center gap-1">
                  <Target className="h-2.5 w-2.5" />
                  <span>TP: {formatPrice(target, ticker)}</span>
                  {targetDelta !== null && (
                    <span className="font-bold">({targetDelta >= 0 ? "+" : ""}{targetDelta.toFixed(1)}%)</span>
                  )}
                </div>

                <div className="px-2 py-0.5 rounded bg-bear/10 border border-bear/30 text-[12px] font-mono text-bear flex items-center gap-1">
                  <Shield className="h-2.5 w-2.5" />
                  <span>SL: {formatPrice(inval, ticker)}</span>
                  {invalDelta !== null && (
                    <span className="font-bold">({invalDelta >= 0 ? "+" : ""}{invalDelta.toFixed(1)}%)</span>
                  )}
                </div>

                {matchingSignal.risk_reward_ratio && matchingSignal.risk_reward_ratio > 0 && (
                  <div className="px-2 py-0.5 rounded bg-surface-2/80 border border-border/30 text-[12px] font-mono text-primary font-bold">
                    R:R {matchingSignal.risk_reward_ratio.toFixed(1)}:1
                  </div>
                )}
              </>
            ) : analyzing ? (
              <div className="px-2 py-0.5 rounded bg-primary/10 border border-primary/30 text-[12px] font-mono text-primary flex items-center gap-1.5 animate-pulse">
                <Activity className="h-3 w-3 animate-spin" />
                <span>SYNTHESIZING 9-AGENT CONSENSUS FOR {ticker}...</span>
              </div>
            ) : matchingSignal && isNoSignal ? (
              <div className="px-2 py-0.5 rounded bg-surface-2/80 border border-border/30 text-[12px] font-mono flex items-center gap-2 text-muted-foreground">
                <span className="font-bold text-warn">NEUTRAL PIPELINE STANCE</span>
                <span>•</span>
                <span className="truncate max-w-md text-foreground/80">
                  {matchingSignal.status_reasons && matchingSignal.status_reasons.length > 0
                    ? matchingSignal.status_reasons[0]
                    : "Fewer than 2 directional votes from specialist analysts; consensus withheld"}
                </span>
              </div>
            ) : (
              <div className="px-2 py-0.5 rounded bg-surface-2/80 border border-border/30 text-[12px] font-mono flex items-center gap-2 text-muted-foreground">
                <span>TELEMETRY: STANDBY</span>
                <span>•</span>
                <span>NO ACTIVE DOSSIER FOR {ticker} — INITIALIZE 9-AGENT SYNTHESIS</span>
              </div>
            )}
          </div>
        </div>

        {/* Right Action Cluster */}
        <div className="flex items-center gap-1.5">
          {onGenerate && (
            <button
              onClick={() => onGenerate(ticker)}
              disabled={analyzing}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono font-bold border transition-colors",
                analyzing
                  ? "bg-primary/10 text-primary border-primary/30 cursor-wait animate-pulse"
                  : "bg-primary text-primary-foreground border-primary hover:bg-primary/90 shadow-sm"
              )}
            >
              <Zap className="h-3 w-3" />
              <span>{analyzing ? "DELIBERATING..." : "ANALYZE NOW"}</span>
            </button>
          )}

          {matchingSignal && !isNoSignal && (
            <>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 px-2 py-1 rounded text-[12px] font-mono border border-border/40 hover:bg-surface-2 text-muted-foreground transition-colors"
                title="Copy Trade Blueprint"
              >
                {copied ? <Check className="h-3 w-3 text-bull" /> : <Copy className="h-3 w-3" />}
                <span className="hidden sm:inline">{copied ? "COPIED" : "COPY PLAN"}</span>
              </button>

              {onAdoptSignal && (
                <button
                  onClick={() => onAdoptSignal(matchingSignal)}
                  disabled={isAdopted}
                  className={cn(
                    "flex items-center gap-1 px-2 py-1 rounded text-[12px] font-mono font-bold border transition-colors",
                    isAdopted
                      ? "bg-bull/10 text-bull border-bull/30"
                      : "bg-surface-2 text-muted-foreground border-border/40 hover:text-foreground"
                  )}
                  title="Adopt to My Desk Watchlist"
                >
                  <Sparkles className="h-3 w-3" />
                  <span className="hidden sm:inline">{isAdopted ? "TRACKED" : "ADOPT"}</span>
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Target Rays & Price Journey Bar (When active target exists) */}
      {!isNoSignal && entry && target && inval && (
        <div className="px-3 pb-1.5">
          <div className="p-1.5 rounded border border-border/30 bg-surface-2/30">
            <div className="flex items-center justify-between text-[12px] font-mono text-muted-foreground mb-1">
              <span className="text-bear font-bold">STOP {formatPrice(inval, ticker)}</span>
              <span className="font-bold text-foreground">
                PRICE JOURNEY: {journeyPct.toFixed(0)}% TO TARGET
              </span>
              <span className="text-bull font-bold">TARGET {formatPrice(target, ticker)}</span>
            </div>
            <div className="h-1.5 w-full bg-surface-3 rounded-full overflow-hidden relative">
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-foreground/70 z-10"
                style={{ left: "30%" }}
                title="Entry Reference"
              />
              <div
                className={cn(
                  "h-full transition-all duration-500 rounded-full",
                  isShort
                    ? "bg-gradient-to-r from-bear via-warn to-bull"
                    : "bg-gradient-to-r from-bear via-warn to-bull"
                )}
                style={{ width: `${journeyPct}%` }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

