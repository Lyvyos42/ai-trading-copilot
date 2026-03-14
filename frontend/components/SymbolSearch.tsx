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

const QUICK_PICKS = [
  { symbol: "AAPL",     exchange: "NASDAQ" },
  { symbol: "NVDA",     exchange: "NASDAQ" },
  { symbol: "TSLA",     exchange: "NASDAQ" },
  { symbol: "SPY",      exchange: "NYSE"   },
  { symbol: "BTC-USD",  exchange: "CRYPTO" },
  { symbol: "EURUSD=X", exchange: "FX"     },
  { symbol: "GC=F",     exchange: "COMEX"  },
  { symbol: "^GSPC",    exchange: "INDEX"  },
];

interface SymbolSearchProps {
  value: string;
  onChange: (symbol: string) => void;
}

export function SymbolSearch({ value, onChange }: SymbolSearchProps) {
  const [open, setOpen]       = useState(false);
  const [query, setQuery]     = useState("");
  const [results, setResults] = useState<SymbolItem[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Fetch symbols whenever query changes
  useEffect(() => {
    if (!open) return;
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
          style={{ width: 380, maxHeight: 480 }}
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

          <div style={{ overflowY: "auto", maxHeight: 400 }}>
            {/* Quick picks (shown when query is empty) */}
            {!query && (
              <div className="px-3 py-2">
                <div className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-widest mb-2">
                  Quick Pick
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {QUICK_PICKS.map(q => (
                    <button
                      key={q.symbol}
                      onClick={() => select(q.symbol)}
                      className="px-2.5 py-1 rounded-md text-xs font-mono font-medium border border-border/40 hover:border-primary/40 hover:text-primary transition-colors"
                      style={{ color: value === q.symbol ? CATEGORY_COLORS[q.exchange] : undefined,
                               borderColor: value === q.symbol ? CATEGORY_COLORS[q.exchange] + "66" : undefined }}
                    >
                      {q.symbol.replace("=X","").replace("-USD","").replace("=F","")}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Results list */}
            {loading && (
              <div className="flex items-center justify-center py-6 text-xs text-muted-foreground gap-2">
                <span className="h-3 w-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
                Searching…
              </div>
            )}

            {!loading && results.length === 0 && query && (
              <div className="py-6 text-center text-xs text-muted-foreground">
                No symbols found for "{query}"
              </div>
            )}

            {!loading && results.map(s => {
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
