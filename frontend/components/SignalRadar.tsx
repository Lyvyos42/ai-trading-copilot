"use client";

import { useState, useMemo } from "react";
import {
  Search,
  Radar,
  Bookmark,
  TrendingUp,
  TrendingDown,
  Clock,
  Sparkles,
  ChevronRight,
  Shield,
  Layers,
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
  onSelectTicker?: (ticker: string) => void;
}

const ASSET_TABS = ["ALL", "CRYPTO", "FOREX", "STOCKS", "COMMODITIES", "INDICES"];

function renderMiniSparkline(isBull: boolean, ticker: string) {
  const points = isBull
    ? [16, 13, 15, 10, 12, 7, 9, 3]
    : [3, 7, 6, 11, 9, 14, 12, 17];

  const d = `M 0,${points[0]} L 8,${points[1]} L 16,${points[2]} L 24,${points[3]} L 32,${points[4]} L 40,${points[5]} L 48,${points[6]} L 56,${points[7]}`;
  const strokeColor = isBull ? "#22c55e" : "#ef4444";

  return (
    <svg className="w-14 h-4 overflow-visible shrink-0" viewBox="0 0 56 20">
      <path
        d={d}
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function RadarScannerDial({ count, scanning }: { count: number; scanning: boolean }) {
  return (
    <div className="p-2.5 bg-surface-2/80 border-b border-border/40 flex items-center gap-3 shrink-0">
      {/* Animated Radar Dial SVG */}
      <div className="relative w-12 h-12 shrink-0 flex items-center justify-center">
        <svg className="w-full h-full" viewBox="0 0 60 60">
          <circle cx="30" cy="30" r="28" fill="none" stroke="currentColor" strokeWidth="1" className="text-primary/20" />
          <circle cx="30" cy="30" r="19" fill="none" stroke="currentColor" strokeWidth="1" strokeDasharray="2 3" className="text-primary/30" />
          <circle cx="30" cy="30" r="10" fill="none" stroke="currentColor" strokeWidth="1" className="text-primary/40" />
          <line x1="30" y1="2" x2="30" y2="58" stroke="currentColor" strokeWidth="0.75" className="text-primary/20" />
          <line x1="2" y1="30" x2="58" y2="30" stroke="currentColor" strokeWidth="0.75" className="text-primary/20" />
          <circle cx="38" cy="22" r="2" fill="#22c55e" className="animate-ping" style={{ animationDuration: "3s" }} />
          <circle cx="38" cy="22" r="1.5" fill="#22c55e" />
          <circle cx="20" cy="38" r="1.5" fill="#ef4444" />
          <circle cx="22" cy="18" r="1.5" fill="#22c55e" />
          <circle cx="44" cy="40" r="1.5" fill="#D4A240" />
        </svg>

        {/* Sweeping Radar Beam */}
        <div
          className="absolute inset-0 rounded-full pointer-events-none animate-spin"
          style={{
            animationDuration: scanning ? "1.5s" : "4s",
            background: "conic-gradient(from 0deg, transparent 0deg, rgba(34, 197, 94, 0.3) 60deg, transparent 65deg)",
          }}
        />
      </div>

      {/* Radar Telemetry Readout */}
      <div className="flex-1 min-w-0 font-mono">
        <div className="flex items-center justify-between text-[12px]">
          <span className="text-primary font-bold tracking-wider">ALGO_CONF_RADAR</span>
          <span className="text-bull font-bold">{scanning ? "SWEEPING..." : "92% ACTIVE"}</span>
        </div>
        <div className="text-[12px] text-muted-foreground truncate">
          {scanning ? "Polling microstructure L2 books..." : `${count} institutional setups detected`}
        </div>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className="h-1.5 w-1.5 rounded-full bg-bull animate-pulse" />
          <span className="text-[11px] text-muted-foreground uppercase">Liquidity Clusters Monitored</span>
        </div>
      </div>
    </div>
  );
}

export function SignalRadar({
  signals,
  activeSignalId,
  onSelectSignal,
  adoptedSignals,
  onToggleAdopt,
  onScanNow,
  scanning,
  onSelectTicker,
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

  function handleCardClick(sig: Signal) {
    onSelectSignal(sig);
    if (onSelectTicker) {
      onSelectTicker(sig.ticker);
    }
  }

  return (
    <div className="flex flex-col h-full bg-surface-1 border-r border-border/40 overflow-hidden select-none">
      {/* 2027 Circular Radar Scanner Dial at Top */}
      <RadarScannerDial count={signals.length} scanning={scanning} />

      {/* Top Header: View Mode Switcher + Scan Action */}
      <div className="p-2.5 border-b border-border/40 space-y-2 shrink-0 bg-surface-1/90">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1 bg-surface-2 p-0.5 rounded border border-border/40">
            <button
              onClick={() => setViewMode("STREAM")}
              className={cn(
                "px-2 py-0.5 rounded text-[12px] font-mono font-bold transition-colors flex items-center gap-1",
                viewMode === "STREAM"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Radar className="h-3 w-3" />
              <span>RADAR</span>
              <span className="text-[12px] opacity-75">({signals.length})</span>
            </button>
            <button
              onClick={() => setViewMode("MY_DESK")}
              className={cn(
                "px-2 py-0.5 rounded text-[12px] font-mono font-bold transition-colors flex items-center gap-1",
                viewMode === "MY_DESK"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Bookmark className="h-3 w-3" />
              <span>MY DESK</span>
              <span className="text-[12px] opacity-75">({adoptedSignals.length})</span>
            </button>
          </div>

          <button
            onClick={onScanNow}
            disabled={scanning}
            className="flex items-center gap-1 px-2 py-0.5 rounded border border-primary/40 bg-primary/10 hover:bg-primary/20 text-primary text-[12px] font-mono font-bold transition-colors disabled:opacity-50"
          >
            <Sparkles className={cn("h-3 w-3", scanning && "animate-spin")} />
            <span>{scanning ? "SCANNING" : "SCAN NOW"}</span>
          </button>
        </div>

        {/* Search input */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
          <input
            type="text"
            placeholder="Filter radar setups..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-7 pr-3 py-1 rounded border border-border/40 bg-surface-2 text-xs font-mono text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary"
          />
        </div>

        {/* Asset Category Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto scrollbar-none pt-0.5">
          {ASSET_TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "px-1.5 py-0.5 rounded text-[12px] font-mono whitespace-nowrap transition-colors",
                activeTab === tab
                  ? "bg-surface-3 text-primary font-bold border border-border/60"
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
            <p className="text-[12px] font-mono text-muted-foreground/70 max-w-xs mx-auto">
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
                onClick={() => handleCardClick(sig)}
                className={cn(
                  "p-2.5 cursor-pointer transition-all hover:bg-surface-2/70 select-none group",
                  isSelected ? "bg-surface-2/90 border-l-2 border-l-primary" : ""
                )}
              >
                {/* Line 1: Ticker, Direction badge, Mini Sparkline, Bookmark */}
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono font-bold text-xs text-foreground tracking-tight">
                      {sig.ticker}
                    </span>
                    <span
                      className={cn(
                        "px-1 py-0.2 rounded text-[11px] font-mono font-bold uppercase",
                        isBull
                          ? "bg-bull/15 text-bull border border-bull/30"
                          : isShort
                          ? "bg-bear/15 text-bear border border-bear/30"
                          : "bg-surface-3 text-muted-foreground border border-border"
                      )}
                    >
                      {sig.direction}
                    </span>
                    <span className="text-[11px] font-mono text-muted-foreground uppercase">
                      {sig.timeframe || "1D"}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {/* SVG Mini Sparkline */}
                    {!isNoSignal && renderMiniSparkline(isBull, sig.ticker)}

                    {/* Adopt star/bookmark button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleAdopt(sig);
                      }}
                      className={cn(
                        "p-1 rounded hover:bg-surface-3 transition-colors",
                        isAdopted ? "text-primary font-bold" : "text-muted-foreground/40 hover:text-muted-foreground"
                      )}
                      title={isAdopted ? "Remove from My Desk" : "Adopt to My Desk"}
                    >
                      <Bookmark className={cn("h-3 w-3", isAdopted && "fill-primary text-primary")} />
                    </button>
                  </div>
                </div>

                {/* Line 2: Levels & Geometry */}
                {!isNoSignal && (
                  <div className="flex items-center justify-between text-[12px] font-mono mb-1">
                    <span className="text-muted-foreground">
                      E: <span className="text-foreground font-semibold">{formatPrice(entry, sig.ticker)}</span>
                    </span>
                    <span className="text-bull">
                      TP: <span className="font-semibold">{formatPrice(target, sig.ticker)}</span>
                    </span>
                    {sig.risk_reward_ratio && sig.risk_reward_ratio > 0 && (
                      <span className="text-primary font-semibold">
                        R:R {sig.risk_reward_ratio.toFixed(1)}
                      </span>
                    )}
                  </div>
                )}

                {/* Line 3: Confluence Bar & Time */}
                <div className="flex items-center justify-between pt-1 border-t border-border/20 text-[12px] font-mono text-muted-foreground">
                  <span className={cn("font-bold", isBull ? "text-bull" : isShort ? "text-bear" : "text-muted-foreground")}>
                    {prob.toFixed(0)}% {isBull ? "BULL" : isShort ? "BEAR" : "CONFLUENCE"}
                  </span>
                  <div className="flex items-center gap-1">
                    <Clock className="h-2.5 w-2.5" />
                    <span>{timeAgo(sig.timestamp)}</span>
                    <ChevronRight className="h-2.5 w-2.5 opacity-40 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
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

