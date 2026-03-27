"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { supabase } from "@/lib/supabase";
import { wakeBackend, getJournalSignals, listSignals } from "@/lib/api";
import type { Signal } from "@/lib/api";
import { SignalDetailModal } from "@/components/SignalDetailModal";

const PAGE_SIZE = 20;

export default function JournalPage() {
  const router = useRouter();
  const [user, setUser] = useState<unknown>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);

  // Filters
  const [tickerFilter, setTickerFilter] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [assetFilter, setAssetFilter] = useState("");

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        const token = localStorage.getItem("token");
        if (!token) {
          router.push("/login");
          return;
        }
      }
      setUser(session?.user || { demo: true });
    });
  }, [router]);

  const fetchSignals = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getJournalSignals({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        ticker: tickerFilter || undefined,
        outcome: outcomeFilter || undefined,
        asset_class: assetFilter || undefined,
      });
      setSignals(data);
    } catch {
      try {
        const data = await listSignals(PAGE_SIZE);
        setSignals(data);
      } catch { /* ignore */ }
    } finally {
      setLoading(false);
    }
  }, [page, tickerFilter, outcomeFilter, assetFilter]);

  useEffect(() => {
    if (user) {
      wakeBackend();
      fetchSignals();
    }
  }, [user, fetchSignals]);

  const totalSignals = signals.length;
  const wins = signals.filter((s) => s.outcome === "WIN").length;
  const losses = signals.filter((s) => s.outcome === "LOSS").length;
  const resolved = wins + losses;
  const winRate = resolved > 0 ? ((wins / resolved) * 100).toFixed(1) : "—";
  const avgPnl = signals.filter((s) => s.pnl_pct != null).reduce((sum, s) => sum + (s.pnl_pct || 0), 0);

  if (!user) return null;

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-7xl mx-auto pt-16">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold tracking-tight">Signal Journal</h1>
        <p className="text-xs font-mono text-[hsl(var(--muted-foreground))] mt-1">Your complete signal history with outcomes and analysis</p>
      </div>

      {/* Personal Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="panel p-3">
          <span className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] tracking-widest">TOTAL SIGNALS</span>
          <div className="text-lg font-mono font-bold">{totalSignals}</div>
        </div>
        <div className="panel p-3">
          <span className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] tracking-widest">WIN RATE</span>
          <div className={cn("text-lg font-mono font-bold", Number(winRate) >= 50 ? "text-bull" : resolved > 0 ? "text-bear" : "text-[hsl(var(--foreground))]")}>
            {winRate}{winRate !== "—" && "%"}
          </div>
        </div>
        <div className="panel p-3">
          <span className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] tracking-widest">W / L</span>
          <div className="text-lg font-mono font-bold">
            <span className="text-bull">{wins}</span>
            <span className="text-[hsl(var(--muted-foreground))]"> / </span>
            <span className="text-bear">{losses}</span>
          </div>
        </div>
        <div className="panel p-3">
          <span className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] tracking-widest">CUMULATIVE P&L</span>
          <div className={cn("text-lg font-mono font-bold", avgPnl >= 0 ? "text-bull" : "text-bear")}>
            {avgPnl >= 0 ? "+" : ""}{avgPnl.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-[hsl(var(--muted-foreground))]" />
          <input
            className="input-terminal pl-7 w-[140px]"
            placeholder="Ticker..."
            value={tickerFilter}
            onChange={(e) => { setTickerFilter(e.target.value.toUpperCase()); setPage(0); }}
          />
        </div>
        <select
          className="input-terminal w-[120px]"
          value={outcomeFilter}
          onChange={(e) => { setOutcomeFilter(e.target.value); setPage(0); }}
        >
          <option value="">All Outcomes</option>
          <option value="WIN">WIN</option>
          <option value="LOSS">LOSS</option>
          <option value="EXPIRED">EXPIRED</option>
        </select>
        <select
          className="input-terminal w-[120px]"
          value={assetFilter}
          onChange={(e) => { setAssetFilter(e.target.value); setPage(0); }}
        >
          <option value="">All Classes</option>
          <option value="stocks">Stocks</option>
          <option value="crypto">Crypto</option>
          <option value="fx">Forex</option>
          <option value="commodities">Commodities</option>
          <option value="indices">Indices</option>
        </select>
        {(tickerFilter || outcomeFilter || assetFilter) && (
          <button
            className="btn btn-ghost text-[13px]"
            onClick={() => { setTickerFilter(""); setOutcomeFilter(""); setAssetFilter(""); setPage(0); }}
          >
            CLEAR
          </button>
        )}
      </div>

      {/* Signal Table */}
      <div className="panel overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-[200px]">
            <div className="live-dot" />
          </div>
        ) : signals.length === 0 ? (
          <div className="flex items-center justify-center h-[200px]">
            <span className="text-[hsl(var(--muted-foreground))] font-mono text-xs">NO SIGNALS FOUND</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--surface-2))]">
                  <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] py-2 px-3 text-left">DATE</th>
                  <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] py-2 px-3 text-left">TICKER</th>
                  <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] py-2 px-3 text-left">PROB</th>
                  <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] py-2 px-3 text-right">ENTRY</th>
                  <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] py-2 px-3 text-right">CONF</th>
                  <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] py-2 px-3 text-center">OUTCOME</th>
                  <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] py-2 px-3 text-right">P&L</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((signal) => (
                  <tr
                    key={signal.signal_id}
                    className="border-b border-[hsl(var(--border)/0.5)] hover:bg-[hsl(var(--surface-2)/0.5)] cursor-pointer transition-colors"
                    onClick={() => setSelectedSignal(signal)}
                  >
                    <td className="text-[14px] font-mono text-[hsl(var(--muted-foreground))] py-2 px-3">
                      {new Date(signal.timestamp).toLocaleDateString()}
                    </td>
                    <td className="text-[13px] font-mono font-bold text-[hsl(var(--foreground))] py-2 px-3">{signal.ticker}</td>
                    <td className="py-2 px-3">
                      {(() => {
                        const p = signal.probability_score ?? signal.confidence_score ?? 50;
                        const bull = p >= 50;
                        return (
                          <span className={cn("text-[14px] font-mono font-bold", bull ? "text-bull" : "text-bear")}>
                            {Math.round(p)}% {bull ? "BULL" : "BEAR"}
                          </span>
                        );
                      })()}
                    </td>
                    <td className="text-[14px] font-mono text-[hsl(var(--foreground))] text-right py-2 px-3">{signal.entry_price.toFixed(2)}</td>
                    <td className="text-[14px] font-mono text-[hsl(var(--foreground))] text-right py-2 px-3">{signal.confidence_score}</td>
                    <td className="text-center py-2 px-3">
                      {signal.outcome ? (
                        <span className={cn(
                          "text-[13px] font-mono font-bold px-1.5 py-0.5 rounded",
                          signal.outcome === "WIN" ? "bg-[hsl(var(--bull)/0.1)] text-bull" : signal.outcome === "LOSS" ? "bg-[hsl(var(--bear)/0.1)] text-bear" : "bg-[hsl(var(--warn)/0.1)] text-[hsl(var(--warn))]"
                        )}>
                          {signal.outcome}
                        </span>
                      ) : (
                        <span className="text-[13px] font-mono text-[hsl(var(--muted-foreground))]">ACTIVE</span>
                      )}
                    </td>
                    <td className={cn("text-[14px] font-mono font-bold text-right py-2 px-3",
                      signal.pnl_pct != null ? (signal.pnl_pct >= 0 ? "text-bull" : "text-bear") : "text-[hsl(var(--muted-foreground))]"
                    )}>
                      {signal.pnl_pct != null ? `${signal.pnl_pct >= 0 ? "+" : ""}${signal.pnl_pct.toFixed(2)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="flex items-center justify-between px-3 py-2 border-t border-[hsl(var(--border))]">
          <span className="text-[13px] font-mono text-[hsl(var(--muted-foreground))]">
            Page {page + 1} · {signals.length} results
          </span>
          <div className="flex items-center gap-1">
            <button className="btn btn-ghost p-1" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <button className="btn btn-ghost p-1" disabled={signals.length < PAGE_SIZE} onClick={() => setPage((p) => p + 1)}>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Signal Detail Modal */}
      {selectedSignal && (
        <SignalDetailModal signal={selectedSignal} onClose={() => setSelectedSignal(null)} />
      )}
    </div>
  );
}
