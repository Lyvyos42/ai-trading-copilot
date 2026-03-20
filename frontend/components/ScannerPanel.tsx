"use client";

import { useState, useEffect, useCallback } from "react";
import { X, Plus, Play, Square, Zap, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ScannerConfig {
  enabled:                   boolean;
  symbols:                   string[];
  max_concurrent:            number;
  interval_minutes:          number;
  last_scan_at:              string | null;
  estimated_cost_per_hour:   number;
}

const INTERVAL_OPTIONS = [15, 30, 60] as const;
const CONCURRENT_OPTIONS = [1, 2, 3, 4, 5] as const;
const MAX_SYMBOLS = 20;

async function apiFetch(path: string, options?: RequestInit) {
  const token = typeof window !== "undefined"
    ? (localStorage.getItem("sb-access-token") || localStorage.getItem("token"))
    : null;
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

interface ScannerPanelProps {
  /** Called when a new alert arrives so the feed can refresh */
  onConfigChange?: () => void;
}

export function ScannerPanel({ onConfigChange }: ScannerPanelProps) {
  const [config,   setConfig]   = useState<ScannerConfig | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [saving,   setSaving]   = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [newSymbol, setNewSymbol] = useState("");

  // Local editable state
  const [symbols,     setSymbols]     = useState<string[]>([]);
  const [concurrent,  setConcurrent]  = useState(2);
  const [interval,    setIntervalMin] = useState(30);
  const [enabled,     setEnabled]     = useState(false);

  const costPerHour = ((symbols.length * (60 / interval)) * 0.001).toFixed(4);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const cfg: ScannerConfig = await apiFetch("/api/v1/scanner/config");
      setConfig(cfg);
      setSymbols(cfg.symbols);
      setConcurrent(cfg.max_concurrent);
      setIntervalMin(cfg.interval_minutes);
      setEnabled(cfg.enabled);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load config";
      if (msg.includes("Pro") || msg.includes("Enterprise") || msg.includes("403")) {
        setError("pro_required");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  async function saveConfig(newEnabled?: boolean) {
    setSaving(true);
    setError(null);
    try {
      const cfg: ScannerConfig = await apiFetch("/api/v1/scanner/config", {
        method: "PUT",
        body: JSON.stringify({
          enabled:          newEnabled ?? enabled,
          symbols,
          max_concurrent:   concurrent,
          interval_minutes: interval,
        }),
      });
      setConfig(cfg);
      setEnabled(cfg.enabled);
      onConfigChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  function addSymbol() {
    const s = newSymbol.trim().toUpperCase();
    if (!s || symbols.includes(s) || symbols.length >= MAX_SYMBOLS) return;
    setSymbols(prev => [...prev, s]);
    setNewSymbol("");
  }

  function removeSymbol(sym: string) {
    setSymbols(prev => prev.filter(s => s !== sym));
  }

  async function toggleEnabled() {
    const next = !enabled;
    setEnabled(next);
    await saveConfig(next);
  }

  if (loading) {
    return (
      <div className="px-3 py-4 flex items-center gap-2 text-[9px] font-mono text-muted-foreground">
        <span className="h-2 w-2 rounded-full border border-primary/40 border-t-primary animate-spin" />
        Loading scanner…
      </div>
    );
  }

  if (error === "pro_required") {
    return (
      <div className="px-3 py-3">
        <div className="text-[9px] font-mono font-bold text-primary mb-1 tracking-widest">AGENT SCANNER</div>
        <div className="text-[9px] font-mono text-muted-foreground leading-relaxed">
          Agent Scanner is available on <span className="text-primary font-bold">Pro</span> and{" "}
          <span className="text-primary font-bold">Enterprise</span> plans.
          <br />
          <a href="/pricing" className="underline text-primary/70 hover:text-primary mt-1 inline-block">
            Upgrade your plan →
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="px-3 py-3 space-y-3">
      {/* Header + toggle */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Zap className={cn("h-3 w-3", enabled ? "text-primary" : "text-muted-foreground")} />
          <span className="text-[9px] font-mono font-bold tracking-widest text-foreground">AGENT SCANNER</span>
        </div>
        <button
          onClick={toggleEnabled}
          disabled={saving || symbols.length === 0}
          className={cn(
            "flex items-center gap-1 text-[8px] font-mono font-bold px-2 py-0.5 rounded border transition-colors",
            enabled
              ? "bg-bear/10 border-bear/30 text-bear hover:bg-bear/20"
              : "bg-bull/10 border-bull/30 text-bull hover:bg-bull/20",
            (saving || symbols.length === 0) && "opacity-40 cursor-not-allowed"
          )}
        >
          {enabled
            ? <><Square className="h-2 w-2" /> STOP</>
            : <><Play  className="h-2 w-2" /> START</>}
        </button>
      </div>

      {/* Status line */}
      {config && (
        <div className="flex items-center gap-2">
          <span className={cn("h-1.5 w-1.5 rounded-full", enabled ? "bg-bull animate-pulse" : "bg-muted-foreground")} />
          <span className="text-[8px] font-mono text-muted-foreground">
            {enabled ? "ACTIVE" : "INACTIVE"}
            {config.last_scan_at && ` — last scan ${new Date(config.last_scan_at).toLocaleTimeString()}`}
          </span>
        </div>
      )}

      {error && error !== "pro_required" && (
        <div className="text-[8px] font-mono text-bear">{error}</div>
      )}

      {/* Symbol list */}
      <div>
        <div className="text-[8px] font-mono text-muted-foreground mb-1.5">
          SYMBOLS ({symbols.length}/{MAX_SYMBOLS})
        </div>
        <div className="flex flex-wrap gap-1 mb-1.5 min-h-[20px]">
          {symbols.map(sym => (
            <span
              key={sym}
              className="flex items-center gap-0.5 text-[8px] font-mono px-1.5 py-0.5 rounded border border-primary/20 bg-primary/5 text-primary"
            >
              {sym}
              <button onClick={() => removeSymbol(sym)} className="hover:text-bear transition-colors ml-0.5">
                <X className="h-2 w-2" />
              </button>
            </span>
          ))}
          {symbols.length === 0 && (
            <span className="text-[8px] font-mono text-muted-foreground/50 italic">No symbols added</span>
          )}
        </div>

        {/* Add symbol input */}
        {symbols.length < MAX_SYMBOLS && (
          <div className="flex items-center gap-1">
            <input
              value={newSymbol}
              onChange={e => setNewSymbol(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === "Enter" && addSymbol()}
              placeholder="e.g. XAUUSD"
              maxLength={12}
              className="flex-1 text-[8px] font-mono bg-muted/20 border border-border/50 rounded px-1.5 py-1 text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/40"
            />
            <button
              onClick={addSymbol}
              disabled={!newSymbol.trim()}
              className="text-[8px] font-mono px-1.5 py-1 rounded border border-primary/30 text-primary hover:bg-primary/10 transition-colors disabled:opacity-40"
            >
              <Plus className="h-2.5 w-2.5" />
            </button>
          </div>
        )}
      </div>

      {/* Concurrent scans */}
      <div>
        <div className="text-[8px] font-mono text-muted-foreground mb-1">CONCURRENT SCANS</div>
        <div className="flex gap-1">
          {CONCURRENT_OPTIONS.map(n => (
            <button
              key={n}
              onClick={() => setConcurrent(n)}
              className={cn(
                "w-6 h-6 text-[8px] font-mono font-bold rounded border transition-colors",
                concurrent === n
                  ? "bg-primary/10 border-primary/50 text-primary"
                  : "border-border/40 text-muted-foreground hover:border-primary/30 hover:text-primary"
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {/* Interval */}
      <div>
        <div className="text-[8px] font-mono text-muted-foreground mb-1">SCAN INTERVAL</div>
        <div className="flex gap-1">
          {INTERVAL_OPTIONS.map(m => (
            <button
              key={m}
              onClick={() => setIntervalMin(m)}
              className={cn(
                "px-2 h-6 text-[8px] font-mono font-bold rounded border transition-colors",
                interval === m
                  ? "bg-primary/10 border-primary/50 text-primary"
                  : "border-border/40 text-muted-foreground hover:border-primary/30 hover:text-primary"
              )}
            >
              {m}m
            </button>
          ))}
        </div>
      </div>

      {/* Cost estimate */}
      <div className="pt-1 border-t border-border/30">
        <div className="flex items-center justify-between">
          <span className="text-[8px] font-mono text-muted-foreground">EST. COST / HOUR</span>
          <span className={cn(
            "text-[9px] font-mono font-bold",
            parseFloat(costPerHour) < 0.02 ? "text-bull" : parseFloat(costPerHour) < 0.05 ? "text-warn" : "text-bear"
          )}>
            ~${costPerHour}
          </span>
        </div>
        <div className="text-[7px] font-mono text-muted-foreground/50 mt-0.5">
          {symbols.length} symbols × {Math.round(60 / interval)} scans/hr × $0.001 (Haiku)
        </div>
      </div>

      {/* Save button */}
      <button
        onClick={() => saveConfig()}
        disabled={saving}
        className="w-full text-[8px] font-mono font-bold px-2 py-1.5 rounded border border-primary/30 text-primary hover:bg-primary/10 transition-colors disabled:opacity-40"
      >
        {saving ? "SAVING…" : "SAVE CONFIG"}
      </button>
    </div>
  );
}
