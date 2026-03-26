"use client";

import { useState, useEffect, useCallback } from "react";
import { Activity, Play, Square, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/useAuth";
import { SymbolSearch } from "@/components/SymbolSearch";
import { ProfileSelector } from "@/components/ProfileSelector";
import { SessionTimer } from "@/components/SessionTimer";
import { SessionPnL } from "@/components/SessionPnL";
import { SessionSignalCard } from "@/components/SessionSignalCard";
import { CoachPanel } from "@/components/CoachPanel";
import {
  startSession,
  runSessionAnalysis,
  getSessionStatus,
  stopSession,
  type SessionSignal,
  type SessionStatus,
} from "@/lib/api";

export default function SessionPage() {
  const { isLoggedIn, tier } = useAuth();
  const isPro = tier === "pro" || tier === "enterprise" || tier === "admin";

  const [activeTicker, setActiveTicker] = useState("AAPL");
  const [activeProfile, setActiveProfile] = useState(() => {
    if (typeof window !== "undefined") return localStorage.getItem("qne-profile") || "balanced";
    return "balanced";
  });

  const [sessionActive, setSessionActive] = useState(false);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null);
  const [signals, setSignals] = useState<SessionSignal[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const latestSignal = signals[signals.length - 1] || null;

  // Check session status on mount
  useEffect(() => {
    if (!isLoggedIn) return;
    getSessionStatus().then((status) => {
      if (status.active) {
        setSessionActive(true);
        setSessionStatus(status);
        setActiveTicker(status.ticker || "AAPL");
      }
    }).catch(() => {});
  }, [isLoggedIn]);

  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem("qne-profile", activeProfile);
  }, [activeProfile]);

  const handleStartSession = useCallback(async () => {
    if (!isLoggedIn || !isPro) return;
    setLoading(true);
    setError(null);
    try {
      await startSession(activeTicker, activeProfile);
      setSessionActive(true);
      setSignals([]);
      const status = await getSessionStatus();
      setSessionStatus(status);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start session");
    } finally {
      setLoading(false);
    }
  }, [isLoggedIn, isPro, activeTicker, activeProfile]);

  const handleStopSession = useCallback(async () => {
    setLoading(true);
    try {
      await stopSession();
      setSessionActive(false);
      setSessionStatus(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to stop session");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleAnalyze = useCallback(async () => {
    if (!sessionActive) return;
    setAnalyzing(true);
    setError(null);
    try {
      const result = await runSessionAnalysis();
      setSignals((prev) => [...prev, result]);
      const status = await getSessionStatus();
      setSessionStatus(status);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }, [sessionActive]);

  // Pro gate
  if (!isPro && isLoggedIn) {
    return (
      <div className="h-[calc(100vh-72px)] flex items-center justify-center bg-background">
        <div className="text-center max-w-md px-6">
          <Zap className="h-10 w-10 text-amber-400 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-foreground mb-2">Session Mode requires Pro</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Real-time intraday analysis with kill zone detection, psychological coaching,
            and session risk management.
          </p>
          <a
            href="/pricing"
            className="inline-flex items-center gap-2 px-4 py-2 rounded border border-amber-400/30 bg-amber-400/10 text-amber-400 text-sm font-mono font-bold hover:bg-amber-400/20 transition-colors"
          >
            Upgrade to Pro
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-72px)] flex flex-col bg-background overflow-hidden">

      {/* Session Control Bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-[hsl(0_0%_3%)] shrink-0">
        <div className="flex items-center gap-2">
          <span className={cn("h-2 w-2 rounded-full", sessionActive ? "bg-bull animate-pulse" : "bg-muted-foreground")} />
          <span className="text-[10px] font-mono font-bold text-primary tracking-widest">
            SESSION MODE
          </span>
        </div>

        {!sessionActive ? (
          <>
            <SymbolSearch value={activeTicker} onChange={setActiveTicker} />
            <ProfileSelector value={activeProfile} onChange={setActiveProfile} compact />
            <button
              onClick={handleStartSession}
              disabled={loading || !isLoggedIn}
              className="flex items-center gap-1.5 px-3 py-1 rounded text-[10px] font-mono font-bold border border-bull/50 text-bull hover:bg-bull/10 transition-colors disabled:opacity-40"
            >
              <Play className="h-3 w-3" />
              START SESSION
            </button>
          </>
        ) : (
          <>
            <span className="text-[11px] font-mono font-bold text-foreground">{activeTicker}</span>
            <span className="text-[9px] font-mono text-muted-foreground">{activeProfile.toUpperCase()}</span>
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1 rounded text-[10px] font-mono font-bold border transition-colors",
                analyzing
                  ? "border-border/40 text-muted-foreground/50 cursor-not-allowed"
                  : "border-primary/50 text-primary hover:bg-primary/10"
              )}
            >
              <Activity className={cn("h-3 w-3", analyzing && "animate-spin")} />
              {analyzing ? "ANALYZING…" : "RUN ANALYSIS"}
            </button>
            <button
              onClick={handleStopSession}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1 rounded text-[10px] font-mono font-bold border border-bear/50 text-bear hover:bg-bear/10 transition-colors ml-auto disabled:opacity-40"
            >
              <Square className="h-3 w-3" />
              END SESSION
            </button>
          </>
        )}
      </div>

      {error && (
        <div className="px-4 py-2 bg-bear/10 border-b border-bear/30 text-[10px] font-mono text-bear">
          {error}
        </div>
      )}

      {/* Main Content */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* Left — Signals feed */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {!sessionActive && signals.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
              <Zap className="h-10 w-10 text-primary/20" />
              <div className="text-[11px] font-mono text-muted-foreground max-w-sm">
                Start a session to begin real-time intraday analysis.
                Select a ticker and strategy profile, then click START SESSION.
              </div>
            </div>
          )}

          {signals.map((sig, i) => (
            <SessionSignalCard key={`${sig.timestamp}-${i}`} signal={sig} />
          ))}
        </div>

        {/* Right Sidebar — Timer + P&L + Coach */}
        <div className="hidden lg:flex w-72 shrink-0 border-l border-border flex-col gap-3 p-3 overflow-y-auto">

          <SessionTimer
            killZone={latestSignal?.kill_zone || "NONE"}
            killZoneActive={latestSignal?.kill_zone_active || false}
            minutesRemaining={latestSignal?.kill_zone_minutes_remaining || 0}
            marketPhase={latestSignal?.market_phase || "UNKNOWN"}
            sessionElapsed={sessionStatus ? Math.floor((Date.now() - new Date(sessionStatus.started_at || Date.now()).getTime()) / 60000) : 0}
            utcTime={new Date().toISOString().slice(11, 16) + " UTC"}
          />

          <SessionPnL
            pnl={sessionStatus?.pnl || 0}
            pnlPct={sessionStatus?.pnl_pct || 0}
            tradeCount={sessionStatus?.trade_count || 0}
            analysisCount={sessionStatus?.analysis_count || 0}
          />

          {latestSignal?.coach && (
            <CoachPanel
              tiltDetected={latestSignal.coach.tilt_detected}
              tiltType={latestSignal.coach.tilt_type}
              tiltSeverity={latestSignal.coach.tilt_severity}
              message={latestSignal.coach.message}
              recommendation={latestSignal.coach.recommendation}
              positiveNote={latestSignal.coach.positive_note}
            />
          )}

          {latestSignal?.reasoning_chain && latestSignal.reasoning_chain.length > 0 && (
            <div className="rounded-lg border border-border bg-background p-4">
              <div className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest mb-2">
                REASONING CHAIN
              </div>
              <div className="space-y-1">
                {latestSignal.reasoning_chain.map((step, i) => (
                  <div key={i} className="text-[9px] font-mono text-muted-foreground leading-relaxed">
                    {step}
                  </div>
                ))}
              </div>
              <div className="mt-2 text-[8px] font-mono text-muted-foreground/50">
                {latestSignal.pipeline_latency_ms}ms
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
