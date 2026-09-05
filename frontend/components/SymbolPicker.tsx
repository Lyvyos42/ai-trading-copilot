"use client";

/**
 * Browsable instrument picker.
 *
 * The watchlist could only be added to by TYPING a ticker, against a
 * hardcoded list of eleven suggestions - so anyone who did not already know
 * that Brent is "UKOIL" or the Dax is "GER40" simply could not find it. The
 * backend has carried a 283-instrument catalogue across 11 asset classes the
 * whole time; nothing in the UI ever read it.
 *
 * So: browse first, search second. Pick an asset class and see everything in
 * it, grouped by sub-category, with the full name beside every ticker. Typing
 * still works and now filters the real catalogue rather than eleven entries.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Search, X, Check, Loader2 } from "lucide-react";
import { API_URL } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface CatalogSymbol {
  symbol: string;
  name: string;
  exchange?: string;
  cat?: string;
  asset_class?: string;
}

interface AssetClass {
  key: string;
  label: string;
  count: number;
}

interface SymbolPickerProps {
  /** Already on the watchlist - shown ticked, and re-clicking removes. */
  selected?: string[];
  onSelect: (symbol: string) => void;
  onClose?: () => void;
  /** Multi-add keeps the panel open; single-select closes on pick. */
  multi?: boolean;
}

export function SymbolPicker({ selected = [], onSelect, onClose, multi = true }: SymbolPickerProps) {
  const [all, setAll] = useState<CatalogSymbol[]>([]);
  const [classes, setClasses] = useState<AssetClass[]>([]);
  const [activeClass, setActiveClass] = useState<string>("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // One fetch for the whole catalogue. 283 rows is a few KB, so paging it
  // would add latency and complexity to save nothing - and filtering locally
  // keeps browsing instant instead of round-tripping on every keystroke.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/market/symbols`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        setAll(data.symbols ?? []);
        setClasses(data.asset_classes ?? []);
        setError(null);
      } catch (e) {
        if (!cancelled) {
          // Say what failed. An empty picker with no explanation reads as an
          // empty catalogue rather than an unreachable one.
          setError(e instanceof Error ? e.message : "could not load the catalogue");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const visible = useMemo(() => {
    let rows = all;
    if (activeClass) rows = rows.filter((s) => s.asset_class === activeClass);
    const q = query.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (s) =>
          s.symbol.toLowerCase().includes(q) ||
          s.name.toLowerCase().includes(q) ||
          (s.cat || "").toLowerCase().includes(q)
      );
    }
    return rows;
  }, [all, activeClass, query]);

  // Sub-category headings give a 80-row stock list some shape.
  const grouped = useMemo(() => {
    const m = new Map<string, CatalogSymbol[]>();
    for (const s of visible) {
      const k = s.cat || "Other";
      if (!m.has(k)) m.set(k, []);
      m.get(k)!.push(s);
    }
    return Array.from(m.entries());
  }, [visible]);

  const isOn = (sym: string) => selected.includes(sym);

  return (
    <div className="w-[26rem] max-w-[92vw] rounded-md border border-border/80 bg-surface-3 shadow-2xl z-50 flex flex-col max-h-[28rem]">
      {/* Search */}
      <div className="p-2 border-b border-border/40 shrink-0">
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-surface-1 border border-border/50">
          <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose?.();
              if (e.key === "Enter" && visible.length === 1) onSelect(visible[0].symbol);
            }}
            placeholder="Filter, or just browse below"
            className="w-full bg-transparent text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none"
          />
          {query && (
            <button onClick={() => setQuery("")} className="text-muted-foreground hover:text-foreground shrink-0">
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {/* Asset classes */}
      <div className="flex flex-wrap gap-1 p-2 border-b border-border/40 shrink-0">
        <button
          onClick={() => setActiveClass("")}
          className={cn(
            "px-2 py-0.5 rounded text-[11px] font-mono border transition-colors",
            activeClass === ""
              ? "bg-primary/20 border-primary/50 text-primary font-bold"
              : "border-border/40 text-muted-foreground hover:text-foreground"
          )}
        >
          ALL {all.length > 0 && <span className="opacity-60">{all.length}</span>}
        </button>
        {classes.map((c) => (
          <button
            key={c.key}
            onClick={() => setActiveClass(activeClass === c.key ? "" : c.key)}
            className={cn(
              "px-2 py-0.5 rounded text-[11px] font-mono border transition-colors",
              activeClass === c.key
                ? "bg-primary/20 border-primary/50 text-primary font-bold"
                : "border-border/40 text-muted-foreground hover:text-foreground"
            )}
          >
            {c.label.toUpperCase()} <span className="opacity-60">{c.count}</span>
          </button>
        ))}
      </div>

      {/* Results */}
      <div className="flex-1 min-h-0 overflow-y-auto p-1.5">
        {loading && (
          <div className="flex items-center gap-2 px-2 py-6 text-xs font-mono text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> loading catalogue...
          </div>
        )}

        {!loading && error && (
          <div className="px-2 py-6 text-xs font-mono text-bear">
            Instrument catalogue unavailable: {error}.
            <div className="text-muted-foreground mt-1">
              You can still type an exact ticker and press Enter.
            </div>
          </div>
        )}

        {!loading && !error && visible.length === 0 && (
          <div className="px-2 py-6 text-xs font-mono text-muted-foreground">
            Nothing matches &quot;{query}&quot;
            {activeClass && " in this asset class"}.
          </div>
        )}

        {!loading && !error &&
          grouped.map(([cat, rows]) => (
            <div key={cat} className="mb-1.5">
              <div className="px-2 py-0.5 text-[11px] font-mono uppercase tracking-wider text-muted-foreground/70">
                {cat}
              </div>
              {rows.map((s) => {
                const on = isOn(s.symbol);
                return (
                  <button
                    key={s.symbol + (s.asset_class || "")}
                    onClick={() => { onSelect(s.symbol); if (!multi) onClose?.(); }}
                    className={cn(
                      "w-full flex items-center justify-between px-2 py-1.5 rounded text-xs font-mono text-left transition-colors",
                      on ? "bg-primary/10 hover:bg-primary/15" : "hover:bg-surface-1"
                    )}
                  >
                    <span className="flex items-center gap-2 min-w-0">
                      <span className={cn("font-bold shrink-0", on ? "text-primary" : "text-foreground")}>
                        {s.symbol}
                      </span>
                      <span className="text-[11px] text-muted-foreground truncate">{s.name}</span>
                    </span>
                    <span className="flex items-center gap-1.5 shrink-0 pl-2">
                      {s.exchange && (
                        <span className="text-[11px] text-muted-foreground/60">{s.exchange}</span>
                      )}
                      {on && <Check className="h-3 w-3 text-primary" />}
                    </span>
                  </button>
                );
              })}
            </div>
          ))}
      </div>

      <div className="px-2 py-1 border-t border-border/40 text-[11px] font-mono text-muted-foreground shrink-0">
        {loading ? " " : `${visible.length} of ${all.length} instruments`}
        {multi && selected.length > 0 && ` · ${selected.length} on watchlist`}
      </div>
    </div>
  );
}
