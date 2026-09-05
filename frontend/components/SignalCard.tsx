"use client";

import { useState, memo } from "react";
import { Clock, Shield, Zap, ChevronDown, ChevronUp, Target, ArrowUpRight, ArrowDownRight, X } from "lucide-react";
import { type Signal, executePosition, resolveSignal } from "@/lib/api";
import { formatPrice, timeAgo, formatPositionSize } from "@/lib/utils";
import { cn } from "@/lib/utils";

const AGENT_LABELS: Record<string, string> = {
  fundamental:   "Fundamental",
  technical:     "Technical",
  sentiment:     "Sentiment",
  macro:         "Macro",
  order_flow:    "Order Flow",
  regime_change: "Regime",
  correlation:   "Correlation",
};

const AGENT_SHORT: Record<string, string> = {
  fundamental:   "FUND",
  technical:     "TECH",
  sentiment:     "SENT",
  macro:         "MACRO",
  order_flow:    "FLOW",
  regime_change: "RGME",
  correlation:   "CORR",
};

interface SignalCardProps {
  signal: Signal;
  onExecute?: (id: string) => void;
  onResolve?: (id: string, outcome: "WIN" | "LOSS") => void;
  onDismiss?: (id: string) => void;
  compact?: boolean;
}

export const SignalCard = memo(function SignalCard({ signal, onExecute, onResolve, onDismiss, compact }: SignalCardProps) {
  const [expanded, setExpanded]   = useState(false);
  const [loading, setLoading]     = useState(false);
  const [executeError, setExecuteError] = useState<string | null>(null);
  const [executed, setExecuted]   = useState(false);
  const [resolving, setResolving]   = useState(false);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [resolved, setResolved]     = useState<"WIN" | "LOSS" | null>(
    signal.status === "WIN" || signal.status === "LOSS" ? (signal.status as "WIN" | "LOSS") : null
  );

  // Probability model fields (with backward compat)
  const isNoSignal = signal.status === "NO_SIGNAL" || signal.direction === "NEUTRAL";
  const prob = signal.probability_score ?? signal.confidence_score ?? (isNoSignal ? 0 : 50);
  const bullPct = isNoSignal ? 0 : (signal.bullish_pct ?? prob);
  const bearPct = isNoSignal ? 0 : (signal.bearish_pct ?? (100 - bullPct));
  const isBullish = bullPct > bearPct;
  const displayPct = isBullish ? bullPct : bearPct;  // Show the dominant side percentage
  const lean = isNoSignal ? "NEUTRAL" : (isBullish ? "BULLISH" : "BEARISH");
  const leanColor = isNoSignal ? "text-muted-foreground" : (isBullish ? "text-bull" : "text-bear");
  const leanBg = isNoSignal ? "bg-muted/20 border-border/40" : (isBullish ? "bg-bull/10 border-bull/30" : "bg-bear/10 border-bear/30");
  const convictionTier = signal.conviction_tier || (isNoSignal ? "ABSTAINED" : "MODERATE");

  const isActive = signal.status === "ACTIVE";
  const hasLivePrice = isActive && signal.current_price && signal.current_price > 0;
  const liveEntry = hasLivePrice ? signal.current_price! : (signal.entry_price ?? 0);
  let target = signal.research_target || signal.take_profit_1 || 0;
  let inval  = signal.invalidation_level || signal.stop_loss || 0;
  if (!isNoSignal && target && inval && liveEntry > 0) {
    if (isBullish && target < liveEntry && inval > liveEntry) {
      [target, inval] = [inval, target];
    } else if (!isBullish && target > liveEntry && inval < liveEntry) {
      [target, inval] = [inval, target];
    }
    const maxDrift = liveEntry * 0.15;
    if (Math.abs(target - liveEntry) > maxDrift) target = 0;
    if (Math.abs(inval - liveEntry) > maxDrift) inval = 0;
  }
  const rawRR = (!isNoSignal && liveEntry && inval && target)
    ? Math.abs((target - liveEntry) / Math.max(Math.abs(inval - liveEntry), 0.0001))
    : (signal.risk_reward_ratio ?? 0);
  const rrRatio = Math.min(rawRR, 10);

  const handleExecute = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setLoading(true);
    setExecuteError(null);
    try {
      await executePosition(signal.signal_id);
      setExecuted(true);
      onExecute?.(signal.signal_id);
    } catch (err) {
      setExecuteError(err instanceof Error ? err.message : "Failed to execute trade");
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (e: React.MouseEvent, outcome: "WIN" | "LOSS") => {
    e.stopPropagation();
    setResolving(true);
    setResolveError(null);
    try {
      await resolveSignal(signal.signal_id, outcome);
      setResolved(outcome);
      onResolve?.(signal.signal_id, outcome);
      // Dispatch global event so Navbar can refresh signal count
      window.dispatchEvent(new CustomEvent("signal-resolved"));
    } catch (err) {
      setResolveError(err instanceof Error ? err.message : "Failed to resolve");
    } finally {
      setResolving(false);
    }
  };

  /* ── COMPACT MODE — probability feed row ─────────────────────── */
  if (compact) {
    if (isNoSignal) {
      return (
        <div className="px-3 py-2.5 border-l-2 border-border/60 bg-muted/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-mono font-bold px-1.5 py-0.5 rounded bg-muted/40 text-muted-foreground border border-border/40">
                ABSTAIN
              </span>
              <span className="text-xs font-mono font-bold text-foreground">{signal.ticker}</span>
              {signal.timeframe && (
                <span className="text-[11px] font-mono text-muted-foreground border border-border/40 px-1 rounded">
                  {signal.timeframe}
                </span>
              )}
              <span className="text-[12px] font-mono text-muted-foreground">
                PIPELINE ABSTAINED
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-[12px] font-mono text-muted-foreground">
              <Clock className="h-2.5 w-2.5" />
              {timeAgo(signal.timestamp)}
              {onDismiss && (
                <button
                  onClick={(e) => { e.stopPropagation(); onDismiss(signal.signal_id); }}
                  className="text-[11px] font-mono p-0.5 rounded border border-border/30 text-muted-foreground hover:text-bear transition-colors ml-1"
                  title="Dismiss signal"
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              )}
            </div>
          </div>
          {signal.status_reasons && signal.status_reasons.length > 0 && (
            <p className="text-[12px] font-mono text-muted-foreground/80 mt-1.5 leading-relaxed line-clamp-2">
              {signal.status_reasons[0]}
            </p>
          )}
        </div>
      );
    }

    return (
      <div className="px-3 py-2.5">
        {/* Row 1: Ticker + Probability + Conviction */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={cn(
              "text-[13px] font-mono font-bold px-1 rounded",
              isBullish ? "bg-bull/10 text-bull" : "bg-bear/10 text-bear"
            )}>
              {isBullish ? "▲" : "▼"}
            </span>
            <span className="text-xs font-mono font-bold text-foreground">{signal.ticker}</span>
            {signal.timeframe && (
              <span className="text-[11px] font-mono text-primary/70 border border-primary/20 px-1 rounded">
                {signal.timeframe}
              </span>
            )}
            <span className={cn(
              "text-[13px] font-mono font-semibold px-1.5 rounded border",
              leanBg, leanColor
            )}>
              {Math.round(displayPct)}% {lean}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <ConvictionBadge tier={convictionTier} size="sm" />
          </div>
        </div>

        {/* Row 2: Research Target + Invalidation + R:R */}
        <div className="flex items-center gap-3 mt-1.5">
          {liveEntry > 0 && (
            <span className="text-[13px] font-mono text-muted-foreground">
              {isActive && signal.current_price ? "PRICE" : "ENTRY"}{" "}
              <span className="text-foreground font-semibold">{formatPrice(liveEntry, signal.ticker)}</span>
            </span>
          )}
          {target ? (
            <span className="text-[13px] font-mono text-muted-foreground">
              TARGET <span className="text-bull font-semibold">{formatPrice(target, signal.ticker)}</span>
            </span>
          ) : null}
          {inval ? (
            <span className="text-[13px] font-mono text-muted-foreground">
              INVAL <span className="text-bear font-semibold">{formatPrice(inval, signal.ticker)}</span>
            </span>
          ) : null}
          {rrRatio > 0 && (
            <span className="text-[13px] font-mono text-muted-foreground">
              R:R <span className="text-foreground font-semibold">{typeof rrRatio === 'number' ? rrRatio.toFixed(1) : rrRatio}:1</span>
            </span>
          )}
          <span className="text-[13px] font-mono text-muted-foreground">
            Size <span className="text-foreground font-semibold">{formatPositionSize(signal.position_size_pct)}</span>
          </span>
        </div>

        {/* Row 3: Bull/Bear bar + Meta */}
        <div className="flex items-center justify-between mt-1.5">
          <div className="flex items-center gap-2 flex-1 mr-3">
            <ProbabilityBar bullPct={bullPct} bearPct={bearPct} />
          </div>
          <div className="flex items-center gap-1 text-[13px] font-mono text-muted-foreground shrink-0">
            <Clock className="h-2.5 w-2.5" />
            {timeAgo(signal.timestamp)}
            {signal.analytical_window && (
              <span className="ml-1 text-primary/70">{signal.analytical_window}</span>
            )}
          </div>
        </div>

        {/* Agent contribution chips — de-cluttered with abstention grouping */}
        <div className="flex gap-1 mt-2 flex-wrap items-center">
          {Object.entries(signal.agent_votes).map(([agent, vote]) => {
            if (["risk_approved", "quant_validated"].includes(agent) || typeof vote !== "object" || !vote) return null;
            const v = vote as { direction?: string; bullish_contribution?: number; bearish_contribution?: number; confidence?: number; abstained?: boolean };
            if (v.abstained || v.direction === "NEUTRAL" || ((v.confidence ?? 0) === 0 && (v.bullish_contribution ?? 0) === 0 && (v.bearish_contribution ?? 0) === 0)) {
              return null;
            }
            const contrib = (v.bullish_contribution ?? 0) - (v.bearish_contribution ?? 0);
            const isPos = contrib >= 0;
            return (
              <span key={agent} className={cn(
                "text-[11px] font-mono px-1 py-0.5 rounded border font-semibold",
                isPos ? "bg-bull/10 text-bull border-bull/20" : "bg-bear/10 text-bear border-bear/20"
              )}>
                {AGENT_SHORT[agent] || agent}: {isPos ? "+" : ""}{contrib.toFixed(0)}pp
              </span>
            );
          })}
          {(() => {
            const abstainedCount = Object.entries(signal.agent_votes).filter(([agent, vote]) => {
              if (["risk_approved", "quant_validated"].includes(agent) || typeof vote !== "object" || !vote) return false;
              const v = vote as { direction?: string; confidence?: number; abstained?: boolean };
              return v.abstained || v.direction === "NEUTRAL" || (v.confidence ?? 0) === 0;
            }).length;
            if (abstainedCount > 0) {
              return (
                <span className="text-[11px] font-mono px-1 py-0.5 rounded border border-border/30 bg-muted/20 text-muted-foreground">
                  {abstainedCount} ABSTAINED
                </span>
              );
            }
            return null;
          })()}
          {signal.agent_votes.risk_approved !== undefined && (
            <span className={cn(
              "text-[11px] font-mono px-1 py-0.5 rounded border flex items-center gap-0.5",
              signal.agent_votes.risk_approved ? "bg-bull/10 text-bull border-bull/20" : "bg-bear/10 text-bear border-bear/20"
            )}>
              <Shield className="h-2 w-2" />
              {signal.agent_votes.risk_approved ? "RISK OK" : "RISK NO"}
            </span>
          )}
        </div>

        {/* Action row */}
        <div className="flex items-center gap-1.5 mt-2 pt-2 border-t border-border/30">
          {resolved ? (
            <span className={cn(
              "text-[11px] font-mono px-2 py-0.5 rounded border font-bold",
              resolved === "WIN" ? "bg-bull/10 border-bull/30 text-bull" : "bg-bear/10 border-bear/30 text-bear"
            )}>
              {resolved === "WIN" ? "WIN" : "LOSS"}
            </span>
          ) : (
            <>
              <button onClick={(e) => handleResolve(e, "WIN")} disabled={resolving}
                className="text-[11px] font-mono px-2 py-0.5 rounded border font-bold transition-colors bg-bull/10 border-bull/30 text-bull hover:bg-bull/20 disabled:opacity-50">
                WIN
              </button>
              <button onClick={(e) => handleResolve(e, "LOSS")} disabled={resolving}
                className="text-[11px] font-mono px-2 py-0.5 rounded border font-bold transition-colors bg-bear/10 border-bear/30 text-bear hover:bg-bear/20 disabled:opacity-50">
                LOSS
              </button>
            </>
          )}
          {onDismiss && (
            <button
              onClick={(e) => { e.stopPropagation(); onDismiss(signal.signal_id); }}
              className="text-[11px] font-mono p-0.5 rounded border border-border/30 text-muted-foreground hover:text-bear hover:border-bear/30 transition-colors"
              title="Dismiss signal"
            >
              <X className="h-2.5 w-2.5" />
            </button>
          )}
          <div className="ml-auto flex items-center gap-1.5">
            {resolveError && <span className="text-[11px] font-mono text-bear truncate">{resolveError}</span>}
            {executeError && <span className="text-[11px] font-mono text-bear truncate">Error</span>}
            {executed ? (
              <span className="text-[11px] font-mono text-bull">
                <a href="/portfolio" className="underline">Portfolio</a>
              </span>
            ) : (
              !resolved && (
                <button onClick={handleExecute} disabled={loading || executed}
                  className={cn(
                    "text-[11px] font-mono px-2 py-0.5 rounded border font-bold transition-colors",
                    (loading || executed) ? "opacity-50 cursor-not-allowed border-border/30 text-muted-foreground" :
                    isBullish ? "bg-bull/10 border-bull/30 text-bull hover:bg-bull/20"
                             : "bg-bear/10 border-bear/30 text-bear hover:bg-bear/20"
                  )}>
                  {loading ? "..." : "PAPER TRADE"}
                </button>
              )
            )}
          </div>
        </div>
      </div>
    );
  }

  /* ── FULL MODE — probability signal card ─────────────────────── */
  if (isNoSignal) {
    return (
      <div className="terminal-panel animate-fade-in border-muted-foreground/30 bg-card/60">
        <div className="p-4">
          {/* Header */}
          <div className="flex items-start justify-between mb-3 border-b border-border/40 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-foreground text-lg font-mono">{signal.ticker}</span>
                <span className="text-xs font-mono text-muted-foreground border border-border px-1.5 rounded">
                  {signal.asset_class}
                </span>
                {signal.timeframe && (
                  <span className="text-xs font-mono text-muted-foreground border border-border/40 px-1.5 rounded">
                    {signal.timeframe}
                  </span>
                )}
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-muted/40 text-muted-foreground border border-border/50 tracking-wider">
                  STATUS: NO SIGNAL — PIPELINE ABSTAINED
                </span>
              </div>
              <div className="flex items-center gap-1.5 mt-1 text-xs text-muted-foreground font-mono">
                <Clock className="h-3 w-3" />
                {timeAgo(signal.timestamp)}
                {signal.pipeline_latency_ms && (
                  <span className="flex items-center gap-0.5 ml-2 text-muted-foreground">
                    <Zap className="h-3 w-3" />{signal.pipeline_latency_ms}ms
                  </span>
                )}
              </div>
            </div>
            {onDismiss && (
              <button
                onClick={(e) => { e.stopPropagation(); onDismiss(signal.signal_id); }}
                className="p-1 rounded border border-border/30 text-muted-foreground hover:text-foreground transition-colors"
                title="Dismiss"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Institutional Restraint Callout */}
          <div className="p-3 mb-4 rounded border border-border/50 bg-background/50 font-mono text-xs space-y-2">
            <div className="text-[12px] font-bold text-foreground uppercase tracking-wider">
              INSTITUTIONAL RESTRAINT ACTIVATED
            </div>
            <p className="text-muted-foreground leading-relaxed">
              The 9-agent quantitative consensus pipeline evaluated {signal.ticker} and determined market conditions do not meet the strict criteria required to publish a tradeable signal.
            </p>
            {signal.status_reasons && signal.status_reasons.length > 0 && (
              <div className="mt-2 space-y-1 pt-2 border-t border-border/30">
                <div className="text-[12px] text-muted-foreground/70 uppercase font-semibold">Abstention Factors:</div>
                {signal.status_reasons.map((r, i) => (
                  <div key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                    <span className="text-primary font-bold">•</span>
                    <span>{r}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Agent Attributions — Separated into Active vs Abstained */}
          {signal.agent_votes && (
            <div className="mb-4">
              <div className="text-[12px] font-mono text-muted-foreground uppercase font-bold tracking-wider mb-2">
                AGENT ATTRIBUTIONS
              </div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(signal.agent_votes).map(([agent, vote]) => {
                  if (["risk_approved", "quant_validated"].includes(agent) || typeof vote !== "object" || !vote) return null;
                  const v = vote as { direction?: string; confidence?: number; abstained?: boolean };
                  const isAbstain = v.abstained || v.direction === "NEUTRAL" || (v.confidence ?? 0) === 0;
                  return (
                    <span
                      key={agent}
                      className={cn(
                        "text-[12px] font-mono px-2 py-0.5 rounded border",
                        isAbstain
                          ? "bg-muted/20 text-muted-foreground border-border/40"
                          : v.direction === "LONG"
                          ? "bg-bull/10 text-bull border-bull/20 font-bold"
                          : "bg-bear/10 text-bear border-bear/20 font-bold"
                      )}
                    >
                      {AGENT_SHORT[agent] || agent.toUpperCase()}: {isAbstain ? "ABSTAIN" : v.direction}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* Reasoning Chain */}
          {signal.reasoning_chain && signal.reasoning_chain.length > 0 && (
            <div className="p-2.5 rounded border border-border/40 bg-muted/20 text-xs font-mono">
              <div className="text-[12px] text-muted-foreground font-bold tracking-wider uppercase mb-1">
                PIPELINE AUDIT TRAIL
              </div>
              {signal.reasoning_chain.map((step, i) => (
                <div key={i} className="text-muted-foreground flex gap-1.5 leading-relaxed">
                  <span className="text-primary/70">{i + 1}.</span>
                  <span>{step}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="terminal-panel animate-fade-in">
      <div className="p-4">
        {/* Header: Ticker + Probability Score */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-foreground text-lg font-mono">{signal.ticker}</span>
              <span className="text-xs font-mono text-muted-foreground border border-border px-1.5 rounded">
                {signal.asset_class}
              </span>
              {signal.timeframe && (
                <span className="text-xs font-mono text-primary/70 border border-primary/20 px-1.5 rounded">
                  {signal.timeframe}
                </span>
              )}
              <ConvictionBadge tier={convictionTier} />
              {signal.analytical_window && (
                <span className="text-[13px] font-mono text-primary/70 border border-primary/20 px-1.5 py-0.5 rounded">
                  {signal.analytical_window}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5 mt-0.5 text-xs text-muted-foreground font-mono">
              <Clock className="h-3 w-3" />
              {timeAgo(signal.timestamp)}
              {signal.pipeline_latency_ms && (
                <span className="flex items-center gap-0.5 ml-1 text-warn">
                  <Zap className="h-3 w-3" />{signal.pipeline_latency_ms}ms
                </span>
              )}
            </div>
            {signal.strategy_sources && signal.strategy_sources.length > 0 && (
              <div className="flex gap-1 mt-1 flex-wrap">
                {signal.strategy_sources.slice(0, 3).map((s: string) => (
                  <span key={s} className="text-[11px] font-mono px-1.5 py-0.5 rounded border border-primary/20 bg-primary/5 text-primary/80">
                    {s}
                  </span>
                ))}
                {signal.strategy_sources.length > 3 && (
                  <span className="text-[11px] font-mono text-muted-foreground">+{signal.strategy_sources.length - 3} more</span>
                )}
              </div>
            )}
          </div>
          <ProbabilityDonut score={displayPct} isBullish={isBullish} />
        </div>

        {/* Probability bar */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[14px] font-mono text-bull font-bold">{bullPct.toFixed(0)}% BULLISH</span>
            <span className="text-[14px] font-mono text-bear font-bold">{bearPct.toFixed(0)}% BEARISH</span>
          </div>
          <ProbabilityBar bullPct={bullPct} bearPct={bearPct} tall />
        </div>

        {/* Research Target + Invalidation Level + R:R + Position Size */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-4">
          <div className="text-center p-2.5 rounded border bg-background/40 border-primary/30">
            <div className="terminal-label mb-0.5 flex items-center justify-center gap-1">
              <Target className="h-3 w-3 text-primary" /> {isActive && signal.current_price ? "MARKET PRICE" : "ENTRY PRICE"}
            </div>
            <div className="text-xs font-mono font-bold text-foreground">
              {formatPrice(liveEntry, signal.ticker)}
            </div>
            <div className="text-[13px] font-mono text-primary/70 mt-0.5">
              {isActive && signal.current_price ? "LIVE" : (signal.timeframe || "1D") + " window"}
            </div>
          </div>
          {(() => {
            const isShort = signal.direction === "SHORT";
            const targetDelta = (target && liveEntry > 0)
              ? (isShort ? ((liveEntry - target) / liveEntry) * 100 : ((target - liveEntry) / liveEntry) * 100)
              : null;
            return (
              <div className="text-center p-2.5 rounded border bg-background/40 border-bull/30">
                <div className="terminal-label mb-0.5 flex items-center justify-center gap-1">
                  <ArrowUpRight className="h-3 w-3 text-bull" /> RESEARCH TARGET
                </div>
                <div className="text-xs font-mono font-bold text-bull">
                  {target ? formatPrice(target, signal.ticker) : "—"}
                </div>
                {targetDelta !== null && (
                  <div className="text-[13px] font-mono text-bull/70 mt-0.5">
                    {targetDelta >= 0 ? "+" : ""}{targetDelta.toFixed(1)}%
                  </div>
                )}
              </div>
            );
          })()}
          {(() => {
            const isShort = signal.direction === "SHORT";
            const invalDelta = (inval && liveEntry > 0)
              ? (isShort ? -((inval - liveEntry) / liveEntry) * 100 : ((inval - liveEntry) / liveEntry) * 100)
              : null;
            return (
              <div className="text-center p-2.5 rounded border bg-background/40 border-bear/30">
                <div className="terminal-label mb-0.5 flex items-center justify-center gap-1">
                  <ArrowDownRight className="h-3 w-3 text-bear" /> INVALIDATION
                </div>
                <div className="text-xs font-mono font-bold text-bear">
                  {inval ? formatPrice(inval, signal.ticker) : "—"}
                </div>
                {invalDelta !== null && (
                  <div className="text-[13px] font-mono text-bear/70 mt-0.5">
                    {invalDelta >= 0 ? "+" : ""}{invalDelta.toFixed(1)}%
                  </div>
                )}
              </div>
            );
          })()}
          <div className="text-center p-2.5 rounded border bg-background/40 border-primary/30">
            <div className="terminal-label mb-0.5">POTENTIAL R:R</div>
            <div className="text-xs font-mono font-bold text-primary">
              {typeof rrRatio === 'number' ? rrRatio.toFixed(1) : rrRatio}:1
            </div>
            <div className="text-[13px] font-mono text-muted-foreground mt-0.5">
              risk/reward
            </div>
          </div>
          <div className="text-center p-2.5 rounded border bg-background/40 border-primary/30 col-span-2 sm:col-span-1">
            <div className="terminal-label mb-0.5">POSITION SIZE</div>
            <div className="text-xs font-mono font-bold text-primary">
              {formatPositionSize(signal.position_size_pct)}
            </div>
            <div className="text-[13px] font-mono text-muted-foreground mt-0.5">
              {typeof signal.position_size_pct === "number" && signal.position_size_pct > 0 ? "Kelly-adjusted" : "uncalibrated"}
            </div>
          </div>
        </div>

        {/* Per-agent contribution bars & attribution */}
        <div className="mb-4">
          <div className="terminal-label mb-2">AGENT CONTRIBUTIONS &amp; ATTRIBUTION</div>
          <div className="space-y-1.5">
            {Object.entries(signal.agent_votes).map(([agent, vote]) => {
              if (["risk_approved", "quant_validated"].includes(agent) || typeof vote !== "object" || !vote) return null;
              const v = vote as { direction?: string; bullish_contribution?: number; bearish_contribution?: number; confidence?: number; abstained?: boolean };
              const isAbstained = v.abstained || v.direction === "NEUTRAL" || ((v.confidence ?? 0) === 0 && (v.bullish_contribution ?? 0) === 0 && (v.bearish_contribution ?? 0) === 0);
              if (isAbstained) {
                return (
                  <div key={agent} className="flex items-center gap-2 text-muted-foreground/60">
                    <span className="text-[13px] font-mono w-24 shrink-0 uppercase text-muted-foreground/60">
                      {AGENT_LABELS[agent] || agent}
                    </span>
                    <div className="flex-1 h-2 bg-muted/20 rounded overflow-hidden relative">
                      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-border/30" />
                    </div>
                    <span className="text-[12px] font-mono w-16 text-right text-muted-foreground/60 italic">
                      ABSTAINED
                    </span>
                  </div>
                );
              }
              const bullContrib = v.bullish_contribution ?? (v.direction === "LONG" ? (v.confidence ?? 50) / 7 : 0);
              const bearContrib = v.bearish_contribution ?? (v.direction === "SHORT" ? (v.confidence ?? 50) / 7 : 0);
              const net = bullContrib - bearContrib;
              const isPos = net >= 0;
              return (
                <div key={agent} className="flex items-center gap-2">
                  <span className="text-[13px] font-mono text-muted-foreground w-24 shrink-0 uppercase">
                    {AGENT_LABELS[agent] || agent}
                  </span>
                  <div className="flex-1 flex items-center gap-1">
                    <div className="flex-1 h-2 bg-muted/50 rounded overflow-hidden relative">
                      {/* Center line */}
                      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-border/50" />
                      {isPos ? (
                        <div className="absolute top-0 bottom-0 bg-bull/60 rounded-r"
                          style={{ left: '50%', width: `${Math.min(Math.abs(net) * 2, 50)}%` }} />
                      ) : (
                        <div className="absolute top-0 bottom-0 bg-bear/60 rounded-l"
                          style={{ right: '50%', width: `${Math.min(Math.abs(net) * 2, 50)}%` }} />
                      )}
                    </div>
                  </div>
                  <span className={cn(
                    "text-[13px] font-mono font-bold w-16 text-right",
                    isPos ? "text-bull" : "text-bear"
                  )}>
                    {isPos ? "+" : ""}{net.toFixed(0)}pp
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Bull Case / Bear Case */}
        {(signal.bull_case || signal.bear_case) && (
          <div className="grid grid-cols-2 gap-2 mb-4">
            {signal.bull_case && (
              <div className="p-2.5 rounded border border-bull/20 bg-bull/5">
                <div className="text-[13px] font-mono font-bold text-bull mb-1 flex items-center gap-1">
                  <ArrowUpRight className="h-3 w-3" /> BULL CASE
                </div>
                <p className="text-[14px] font-mono text-foreground/80 leading-relaxed">{signal.bull_case}</p>
              </div>
            )}
            {signal.bear_case && (
              <div className="p-2.5 rounded border border-bear/20 bg-bear/5">
                <div className="text-[13px] font-mono font-bold text-bear mb-1 flex items-center gap-1">
                  <ArrowDownRight className="h-3 w-3" /> BEAR CASE
                </div>
                <p className="text-[14px] font-mono text-foreground/80 leading-relaxed">{signal.bear_case}</p>
              </div>
            )}
          </div>
        )}

        {/* Risk + Quant badges */}
        <div className="flex gap-1.5 mb-3 flex-wrap">
          {signal.agent_votes.quant_validated === true && (
            <div className="text-xs font-mono px-2 py-0.5 rounded border flex items-center gap-1 bg-bull/10 text-bull border-bull/20">
              QUANT VALIDATED
            </div>
          )}
          {signal.agent_votes.quant_validated === false && (
            <div className="text-xs font-mono px-2 py-0.5 rounded border flex items-center gap-1 bg-warn/10 text-warn border-warn/20">
              QUANT UNCONFIRMED
            </div>
          )}
          {signal.agent_votes.quant_validated === null && (
            <div className="text-xs font-mono px-2 py-0.5 rounded border flex items-center gap-1 bg-muted/30 text-muted-foreground border-border/40">
              QUANT UNMEASURED
            </div>
          )}
          {signal.agent_votes.risk_approved !== undefined && (
            <div className={cn(
              "text-xs font-mono px-2 py-0.5 rounded border flex items-center gap-1",
              signal.agent_votes.risk_approved ? "bg-bull/10 text-bull border-bull/20" : "bg-bear/10 text-bear border-bear/20"
            )}>
              <Shield className="h-3 w-3" />
              RISK {signal.agent_votes.risk_approved ? "APPROVED" : "REJECTED"}
            </div>
          )}
          {signal.strategy_sources?.length > 0 && signal.strategy_sources.slice(0, 3).map((s) => (
            <span key={s} className="text-[13px] font-mono bg-secondary text-secondary-foreground px-1.5 py-0.5 rounded border border-border/50">
              {s.replace(/_/g, " ")}
            </span>
          ))}
          {(signal.strategy_sources?.length ?? 0) > 3 && (
            <span className="text-[13px] font-mono text-muted-foreground">+{signal.strategy_sources.length - 3} more</span>
          )}
        </div>

        {/* Reasoning chain (expandable) */}
        {expanded && signal.reasoning_chain?.length > 0 && (
          <div className="mb-3 space-y-1 border border-border/50 rounded p-2 bg-muted/30">
            <div className="terminal-label mb-1">REASONING CHAIN</div>
            {signal.reasoning_chain.map((step, i) => (
              <div key={i} className="text-xs text-muted-foreground flex gap-2 font-mono">
                <span className="text-primary/60 w-4 shrink-0">{i + 1}.</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col gap-1.5 pt-2 border-t border-border/50">
          {executeError && (
            <div className="text-[14px] font-mono text-bear bg-bear/10 border border-bear/30 rounded px-2 py-1">
              {executeError}
            </div>
          )}
          {executed && (
            <div className="text-[14px] font-mono text-bull bg-bull/10 border border-bull/30 rounded px-2 py-1">
              Paper trade opened — check Portfolio
            </div>
          )}
          <div className="flex items-center justify-between">
            <button
              className="flex items-center gap-1 text-[14px] font-mono text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {expanded ? "HIDE" : "REASONING"}
            </button>
            <div className="flex gap-2">
              <button className="text-[14px] font-mono px-2 py-1 rounded border border-border/50 text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1">
                <Target className="h-2.5 w-2.5" /> BACKTEST
              </button>
              <button
                onClick={handleExecute}
                disabled={loading || executed}
                className={cn(
                  "text-[14px] font-mono px-3 py-1 rounded border font-bold transition-colors",
                  (loading || executed) ? "opacity-50 cursor-not-allowed" : "",
                  isBullish
                    ? "bg-bull/10 border-bull/30 text-bull hover:bg-bull/20"
                    : "bg-bear/10 border-bear/30 text-bear hover:bg-bear/20"
                )}
              >
                {loading ? "..." : executed ? "EXECUTED" : "PAPER TRADE"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

/* ── Sub-components ────────────────────────────────────────────── */

function ProbabilityDonut({ score, isBullish }: { score: number; isBullish?: boolean }) {
  const isBull = isBullish ?? score >= 50;
  const color = isBull ? "#00c55a" : "#e63946";
  const bgColor = isBull ? "#e6394620" : "#00c55a20";
  const radius = 18;
  const circ = 2 * Math.PI * radius;
  const dash = (score / 100) * circ;
  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="52" height="52" viewBox="0 0 52 52">
        <circle cx="26" cy="26" r={radius} fill="none" stroke={bgColor} strokeWidth="4" />
        <circle
          cx="26" cy="26" r={radius}
          fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 26 26)"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-[13px] font-mono font-bold leading-none" style={{ color }}>{Math.round(score)}%</span>
        <span className="text-[11px] font-mono text-muted-foreground leading-none mt-0.5">
          {isBull ? "BULL" : "BEAR"}
        </span>
      </div>
    </div>
  );
}

function ProbabilityBar({ bullPct, bearPct, tall }: { bullPct: number; bearPct: number; tall?: boolean }) {
  return (
    <div className={cn("w-full flex rounded overflow-hidden", tall ? "h-2.5" : "h-1.5")}>
      <div className="bg-bull/70 transition-all" style={{ width: `${bullPct}%` }} />
      <div className="bg-bear/70 transition-all" style={{ width: `${bearPct}%` }} />
    </div>
  );
}

function ConvictionBadge({ tier, size }: { tier: string; size?: "sm" }) {
  const isSm = size === "sm";
  return (
    <span className={cn(
      "font-mono font-bold rounded border",
      isSm ? "text-[11px] px-1 py-0.5" : "text-[13px] px-1.5 py-0.5",
      tier === "HIGH"     ? "bg-bull/10 text-bull border-bull/20" :
      tier === "MODERATE" ? "bg-warn/10 text-warn border-warn/20" :
      tier === "LOW"      ? "bg-muted text-muted-foreground border-border/30" :
                            "bg-muted text-muted-foreground border-border/30"
    )}>
      {tier}
    </span>
  );
}
