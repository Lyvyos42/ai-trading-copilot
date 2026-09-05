"use client";

import { useState, useMemo } from "react";
import {
  Search,
  Radar,
  Bookmark,
  TrendingUp,
  TrendingDown,
  Minus,
  Clock,
  Sparkles,
  ChevronRight,
  ShieldAlert,
  SlidersHorizontal,
} from "lucide-react";
import { cn, formatPrice, timeAgo } from "@/lib/utils";
import type { Signal } from "@/lib/api";

interface SignalRadarProps {
  signals: Signal[];
  activeSignalId: string | null;
  onSelectSignal: (signal: Signal) => void;
  adoptedSignals: Signal[];
  onToggleAdopt: (signal: Signal) => void;
  onScanNow: () => void;
  scanning: boolean;
}

const ASSET_TABS = ["ALL", "CRYPTO", "FOREX", "STOCKS", "COMMODITIES", "INDICES"];

export function SignalRadar({
  signals,
  activeSignalId,
  onSelectSignal,
  adoptedSignals,
  onToggleAdopt,
  onScanNow,
  scanning,
}: SignalRadarProps) {
  const [activeTab, setActiveTab] = useState("ALL");
  const [viewMode, setViewMode] = useState<"STREAM" | "MY_DESK">("STREAM");
  const [searchQuery, setSearchQuery] = useState("");

  const adoptedIds = useMemo(() => new Set(adoptedSignals.map((s) => s.signal_id)), [adoptedSignals]);

  const filteredSignals = useMemo(() => {
    const list = viewMode === "MY_DESK" ? adoptedSignals : signals;
    return list.filter((s) => {
      const q = searchQuery.trim().toUpperCase();
      if (q && !s.ticker.toUpperCase().includes(q)) return false;

      if (activeTab === "ALL") return true;
      const ac = (s.asset_class || "").toLowerCase();
      if (activeTab === "CRYPTO") return ac === "crypto";
      if (activeTab === "FOREX") return ac === "forex" || ac === "fx";
      if (activeTab === "STOCKS") return ac === "stocks" || ac === "etfs";
      if (activeTab === "COMMODITIES") return ac === "commodities" || ac === "metals" || ac === "energy";
      if (activeTab === "INDICES") return ac === "indices" || ac === "futures";
      return true;
    });
  }, [signals, adoptedSignals, viewMode, activeTab, searchQuery]);

  return (
    <div className="flex flex-col h-full bg-surface-1 border-r border-border/40 overflow-hidden">
      {/* Top Header: View Mode Switcher + Scan Action */}
      <div className="p-3 border-b border-border/40 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1 bg-surface-2 p-0.5 rounded border border-border/40">
            <button
              onClick={() => setViewMode("STREAM")}
              className={cn(
                "px-2.5 py-1 rounded text-xs font-mono font-bold transition-colors flex items-center gap-1",
                viewMode === "STREAM"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Radar className="h-3 w-3" />
              <span>RADAR</span>
              <span className="text-[10px] opacity-75">({signals.length})</span>
            </button>
            <button
              onClick={() => setViewMode("MY_DESK")}
              className={cn(
                "px-2.5 py-1 rounded text-xs font-mono font-bold transition-colors flex items-center gap-1",
                viewMode === "MY_DESK"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Bookmark className="h-3 w-3" />
              <span>MY DESK</span>
              <span className="text-[10px] opacity-75">({adoptedSignals.length})</span>
            </button>
          </div>

          <button
            onClick={onScanNow}
            disabled={scanning}
            className="flex items-center gap-1 px-2.5 py-1 rounded border border-primary/40 bg-primary/10 hover:bg-primary/20 text-primary text-xs font-mono font-bold transition-colors disabled:opacity-50"
          >
            <Sparkles className={cn("h-3 w-3", scanning && "animate-spin")} />
            <span>{scanning ? "SCANNING" : "SCAN NOW"}</span>
          </button>
        </div>

        {/* Search input */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search ticker (e.g. AAPL, BTC, EURUSD)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 rounded border border-border/40 bg-surface-2 text-xs font-mono text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary"
          />
        </div>

        {/* Asset Category Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto scrollbar-none pt-0.5">
          {ASSET_TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "px-2 py-0.5 rounded text-[10px] font-mono whitespace-nowrap transition-colors",
                activeTab === tab
                  ? "bg-surface-3 text-foreground font-bold border border-border/60"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Signal Card Feed */}
      <div className="flex-1 overflow-y-auto divide-y divide-border/30">
        {filteredSignals.length === 0 ? (
          <div className="p-6 text-center space-y-2">
            <Radar className="h-6 w-6 mx-auto text-muted-foreground/40" />
            <div className="text-xs font-mono font-bold text-muted-foreground">
              {viewMode === "MY_DESK" ? "NO ADOPTED TRADES YET" : "NO SIGNALS MATCH FILTER"}
            </div>
            <p className="text-[11px] font-mono text-muted-foreground/70 max-w-xs mx-auto">
              {viewMode === "MY_DESK"
                ? "Click 'Adopt Signal' on any setup to monitor live price action and distance to target here."
                : "Trigger 'SCAN NOW' to run multi-agent confluence screening across the market catalogue."}
            </p>
          </div>
        ) : (
          filteredSignals.map((sig) => {
            const isSelected = activeSignalId === sig.signal_id;
            const isAdopted = adoptedIds.has(sig.signal_id);
            const isNoSignal = sig.status === "NO_SIGNAL" || sig.direction === "NEUTRAL";
            const prob = sig.probability_score ?? sig.confidence_score ?? 50;
            const isBull = sig.direction === "LONG";
            const isShort = sig.direction === "SHORT";
            const entry = sig.entry_price || sig.current_price;
            const target = sig.research_target || sig.take_profit_1;

            return (
              <div
                key={sig.signal_id}
                onClick={() => onSelectSignal(sig)}
                className={cn(
                  "p-3 cursor-pointer transition-all hover:bg-surface-2/70 select-none group",
                  isSelected ? "bg-surface-2 border-l-2 border-l-primary" : ""
                )}
              >
                {/* Line 1: Ticker, Direction badge, State badge */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono font-bold text-sm text-foreground tracking-tight">
                      {sig.ticker}
                    </span>
                    <span
                      className={cn(
                        "px-1 py-0.2 rounded text-[9px] font-mono font-bold uppercase",
                        isBull
                          ? "bg-bull/15 text-bull border border-bull/30"
                          : isShort
                          ? "bg-bear/15 text-bear border border-bear/30"
                          : "bg-muted text-muted-foreground border border-border"
                      )}
                    >
                      {sig.direction}
                    </span>
                    <span className="text-[9px] font-mono text-muted-foreground uppercase">
                      {sig.timeframe || "1D"}
                    </span>
                  </div>

                  <div className="flex items-center gap-1">
                    {/* Adopt star/bookmark button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleAdopt(sig);
                      }}
                      className={cn(
                        "p-1 rounded hover:bg-surface-3 transition-colors",
                        isAdopted ? "text-primary font-bold" : "text-muted-foreground/50 hover:text-muted-foreground"
                      )}
                      title={isAdopted ? "Remove from My Desk" : "Adopt to My Desk"}
                    >
                      <Bookmark className={cn("h-3 w-3", isAdopted && "fill-primary text-primary")} />
                    </button>

                    {/* State badge */}
                    {isNoSignal ? (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-border/40 bg-surface-3 text-muted-foreground">
                        RESTRAINT
                      </span>
                    ) : sig.outcome === "WIN" ? (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-bull/40 bg-bull/10 text-bull font-bold">
                        WIN
                      </span>
                    ) : sig.outcome === "LOSS" ? (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-bear/40 bg-bear/10 text-bear font-bold">
                        STOPPED
                      </span>
                    ) : (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-bull/30 bg-bull/5 text-bull flex items-center gap-1">
                        <span className="h-1.5 w-1.5 rounded-full bg-bull animate-pulse" />
                        ACTIVE
                      </span>
                    )}
                  </div>
                </div>

                {/* Line 2: Levels & Geometry */}
                {!isNoSignal && (
                  <div className="flex items-center justify-between text-[11px] font-mono mb-1">
                    <span className="text-muted-foreground">
                      Entry: <span className="text-foreground font-semibold">{formatPrice(entry, sig.ticker)}</span>
                    </span>
                    <span className="text-bull">
                      Target: <span className="font-semibold">{formatPrice(target, sig.ticker)}</span>
                    </span>
                    {sig.risk_reward_ratio && sig.risk_reward_ratio > 0 && (
                      <span className="text-primary font-semibold">
                        R:R {sig.risk_reward_ratio.toFixed(1)}
                      </span>
                    )}
                  </div>
                )}

                {/* Line 3: Mini Confluence Bar & Time */}
                <div className="flex items-center justify-between mt-1 pt-1 border-t border-border/20 text-[10px] font-mono text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <span className={cn("font-bold", isBull ? "text-bull" : isShort ? "text-bear" : "text-muted-foreground")}>
                      {prob.toFixed(0)}% {isBull ? "BULL" : isShort ? "BEAR" : "CONSENSUS"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="h-2.5 w-2.5" />
                    <span>{timeAgo(sig.timestamp)}</span>
                    <ChevronRight className="h-3 w-3 opacity-40 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
