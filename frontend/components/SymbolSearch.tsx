"use client";

import { useState, useEffect, useRef } from "react";
import { Search, X } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SymbolItem {
  symbol: string;
  name: string;
  exchange: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  NASDAQ: "#3b82f6", NYSE: "#6366f1", FX: "#f59e0b",
  CRYPTO: "#f97316", INDEX: "#8b5cf6", COMEX: "#eab308",
  NYMEX: "#ef4444", ICE: "#06b6d4", CBOT: "#84cc16",
};

// Maps exchange → display group label
const EXCHANGE_GROUP: Record<string, string> = {
  NASDAQ: "Equities", NYSE: "Equities",
  FX: "Forex",
  CRYPTO: "Crypto",
  INDEX: "Indices",
  COMEX: "Commodities", NYMEX: "Commodities", ICE: "Commodities", CBOT: "Commodities",
};

// Stable display order for groups
const GROUP_ORDER = ["Equities", "Crypto", "Forex", "Indices", "Commodities"];

const QUICK_PICKS = [
  // US Equities
  { symbol: "AAPL",     exchange: "NASDAQ" },
  { symbol: "NVDA",     exchange: "NASDAQ" },
  { symbol: "MSFT",     exchange: "NASDAQ" },
  { symbol: "TSLA",     exchange: "NASDAQ" },
  { symbol: "META",     exchange: "NASDAQ" },
  { symbol: "GOOGL",    exchange: "NASDAQ" },
  { symbol: "AMZN",     exchange: "NASDAQ" },
  { symbol: "AMD",      exchange: "NASDAQ" },
  // ETFs
  { symbol: "SPY",      exchange: "NYSE"   },
  { symbol: "QQQ",      exchange: "NASDAQ" },
  { symbol: "IWM",      exchange: "NYSE"   },
  // Crypto
  { symbol: "BTC-USD",  exchange: "CRYPTO" },
  { symbol: "ETH-USD",  exchange: "CRYPTO" },
  { symbol: "SOL-USD",  exchange: "CRYPTO" },
  // FX
  { symbol: "EURUSD=X", exchange: "FX"     },
  { symbol: "GBPUSD=X", exchange: "FX"     },
  { symbol: "USDJPY=X", exchange: "FX"     },
  // Commodities
  { symbol: "GC=F",     exchange: "COMEX"  },
  { symbol: "SI=F",     exchange: "COMEX"  },
  { symbol: "CL=F",     exchange: "NYMEX"  },
  // Indices
  { symbol: "^GSPC",    exchange: "INDEX"  },
  { symbol: "^NDX",     exchange: "INDEX"  },
  { symbol: "^VIX",     exchange: "INDEX"  },
];

interface SymbolSearchProps {
  value: string;
  onChange: (symbol: string) => void;
}

export function SymbolSearch({ value, onChange }: SymbolSearchProps) {
  const [open, setOpen]           = useState(false);
  const [query, setQuery]         = useState("");
  const [results, setResults]     = useState<SymbolItem[]>([]);
  const [allSymbols, setAllSymbols] = useState<SymbolItem[]>([]);
  const [loading, setLoading]     = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // When panel opens with empty query, fetch the full symbol list once
  useEffect(() => {
    if (!open) return;
    if (allSymbols.length > 0) return; // already loaded
    setLoading(true);
    fetch(`${API}/api/v1/market/symbols`)
      .then(r => r.json())
      .then(data => setAllSymbols(data.symbols ?? []))
      .catch(() => setAllSymbols([]))
      .finally(() => setLoading(false));
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch filtered results when user types
  useEffect(() => {
    if (!open || !query) return;
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`${API}/api/v1/market/symbols?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        setResults(data.symbols ?? []);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [query, open]);

  // Close on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  function select(symbol: string) {
    onChange(symbol);
    setOpen(false);
    setQuery("");
  }

  function openSearch() {
    setOpen(true);
    setTimeout(() => inputRef.current?.focus(), 50);
  }

  // Group all symbols by display category for the browse view
  const groupedSymbols: Record<string, SymbolItem[]> = {};
  for (const s of allSymbols) {
    const group = EXCHANGE_GROUP[s.exchange] ?? s.exchange;
    if (!groupedSymbols[group]) groupedSymbols[group] = [];
    groupedSymbols[group].push(s);
  }

  const displaySymbol = value.replace("=X", "").replace("-USD", "/USD").replace("=F","");

  return (
    <div ref={panelRef} style={{ position: "relative", zIndex: 50 }}>
      {/* Trigger button */}
      <button
        onClick={openSearch}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-border/50 hover:border-primary/40 transition-colors bg-card text-sm font-mono font-semibold text-foreground"
        style={{ minWidth: 140 }}
      >
        <Search className="h-3.5 w-3.5 text-muted-foreground" />
        <span>{displaySymbol}</span>
        <span className="ml-auto text-[10px] text-muted-foreground border border-border/50 rounded px-1">▾</span>
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          className="absolute left-0 top-full mt-1 bg-card border border-border/60 rounded-xl shadow-2xl overflow-hidden"
          style={{ width: 380, maxHeight: 520 }}
        >
          {/* Search input */}
          <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border/40">
            <Search className="h-4 w-4 text-muted-foreground shrink-0" />
            <input
              ref={inputRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search symbols, e.g. AAPL, EUR, Bitcoin…"
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/50"
              autoFocus
            />
            {query && (
              <button onClick={() => setQuery("")}>
                <X className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
              </button>
            )}
          </div>

          <div style={{ overflowY: "auto", maxHeight: 448 }}>
            {loading && (
              <div className="flex items-center justify-center py-6 text-xs text-muted-foreground gap-2">
                <span className="h-3 w-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
                Loading…
              </div>
            )}

            {/* ── Empty query: quick picks + full grouped catalogue ── */}
            {!loading && !query && (
              <>
                {/* Quick picks row */}
                <div className="px-3 py-2 border-b border-border/30">
                  <div className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-widest mb-2">
                    Quick Pick
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {QUICK_PICKS.map(q => (
                      <button
                        key={q.symbol}
                        onClick={() => select(q.symbol)}
                        className="px-2.5 py-1 rounded-md text-xs font-mono font-medium border border-border/40 hover:border-primary/40 hover:text-primary transition-colors"
                        style={{
                          color: value === q.symbol ? CATEGORY_COLORS[q.exchange] : undefined,
                          borderColor: value === q.symbol ? CATEGORY_COLORS[q.exchange] + "66" : undefined,
                        }}
                      >
                        {q.symbol.replace("=X","").replace("-USD","").replace("=F","")}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Full catalogue grouped by asset class */}
                {GROUP_ORDER.filter(g => groupedSymbols[g]?.length).map(group => (
                  <div key={group}>
                    <div className="px-3 pt-2.5 pb-1 text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-widest">
                      {group}
                    </div>
                    {groupedSymbols[group].map(s => {
                      const color = CATEGORY_COLORS[s.exchange] || "#64748b";
                      const isActive = s.symbol === value;
                      return (
                        <button
                          key={s.symbol}
                          onClick={() => select(s.symbol)}
                          className="w-full flex items-center gap-3 px-3 py-2 hover:bg-muted/30 transition-colors text-left"
                          style={{ background: isActive ? "rgba(59,130,246,0.06)" : undefined }}
                        >
                          <div
                            className="text-xs font-bold font-mono rounded px-1.5 py-0.5 shrink-0"
                            style={{ background: color + "18", color, border: `1px solid ${color}30`, minWidth: 70, textAlign: "center" }}
                          >
                            {s.symbol.replace("=X","").replace("-USD","").replace("=F","").replace("^","")}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-medium text-foreground truncate">{s.name}</div>
                            <div className="text-[10px] text-muted-foreground">{s.exchange}</div>
                          </div>
                          {isActive && <div className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" />}
                        </button>
                      );
                    })}
                  </div>
                ))}
              </>
            )}

            {/* ── Query active: filtered search results ── */}
            {!loading && query && results.length === 0 && (
              <div className="py-6 text-center text-xs text-muted-foreground">
                No symbols found for "{query}"
              </div>
            )}

            {!loading && query && results.map(s => {
              const color = CATEGORY_COLORS[s.exchange] || "#64748b";
              const isActive = s.symbol === value;
              return (
                <button
                  key={s.symbol}
                  onClick={() => select(s.symbol)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-muted/30 transition-colors text-left"
                  style={{ background: isActive ? "rgba(59,130,246,0.06)" : undefined }}
                >
                  <div
                    className="text-xs font-bold font-mono rounded px-1.5 py-0.5 shrink-0"
                    style={{ background: color + "18", color, border: `1px solid ${color}30`, minWidth: 70, textAlign: "center" }}
                  >
                    {s.symbol.replace("=X","").replace("-USD","").replace("=F","").replace("^","")}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-foreground truncate">{s.name}</div>
                    <div className="text-[10px] text-muted-foreground">{s.exchange}</div>
                  </div>
                  {isActive && <div className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
