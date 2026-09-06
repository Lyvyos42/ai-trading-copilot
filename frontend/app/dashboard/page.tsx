"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { CockpitHeader } from "@/components/CockpitHeader";
import { PreMarketBriefing } from "@/components/PreMarketBriefing";
import { SignalRadar } from "@/components/SignalRadar";
import { TradingCanvasHUD } from "@/components/TradingCanvasHUD";
import { TradingViewChart } from "@/components/TradingViewChart";
import { OrderFlowChart } from "@/components/OrderFlowChart";
import { AgentConsensusHUD } from "@/components/AgentConsensusHUD";
import { UpgradeModal } from "@/components/UpgradeModal";
import { useRequireAuth } from "@/lib/useAuth";
import {
  generateSignal,
  listSignals,
  getAgentStatus,
  wakeBackend,
  scanAsync,
  getScanStatus,
  type ScanResult,
  setActiveProfile as saveActiveProfile,
  type Signal,
  type AgentStatus,
} from "@/lib/api";
import { Radar, LineChart, Brain, Layers, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import dynamic from "next/dynamic";

const DepthSurface3D = dynamic(
  () => import("@/components/Microstructure3D").then((m) => m.DepthSurface3D),
  { ssr: false }
);
const LiquiditySurface3D = dynamic(
  () => import("@/components/Microstructure3D").then((m) => m.LiquiditySurface3D),
  { ssr: false }
);

const PROFILE_TIMEFRAMES: Record<string, { timeframe: string; chart: string }> = {
  balanced:      { timeframe: "1D",  chart: "1d" },
  swing:         { timeframe: "1D",  chart: "1d" },
  orb:           { timeframe: "15m", chart: "15m" },
  scalper:       { timeframe: "5m",  chart: "5m" },
  ict_smc:       { timeframe: "15m", chart: "15m" },
  vwap_pullback: { timeframe: "30m", chart: "30m" },
  news_catalyst: { timeframe: "1h",  chart: "1h" },
};

// Seed only. The live list is whatever the user has pinned in the watchlist
// bar; TradingCanvasHUD owns it and reports changes through onWatchlistChange.
// This was a hardcoded const that SCAN NOW sent regardless of what the bar
// showed - it scanned MSFT and USDJPY=X, which were not pinned, and skipped
// EURJPY=X, which was.
const WATCHLIST_SEED = [
  "AAPL", "BTC-USD", "NVDA", "XAUUSD", "EURUSD=X", "TSLA", "US500"
];

function _isExpired(s: Signal): boolean {
  if (!s.expiry_time) return false;
  return new Date(s.expiry_time).getTime() < Date.now();
}

function inferAssetClass(ticker: string): string {
  const u = ticker.toUpperCase();
  if (u.endsWith("-USD") || ["BTC", "ETH", "SOL"].some((c) => u.startsWith(c))) return "crypto";
  if (["XAUUSD", "XAGUSD", "GC=F", "SI=F"].includes(u)) return "commodities";
  if (u.endsWith("=X")) return "forex";
  if (["US500", "US100", "US30"].includes(u)) return "indices";
  return "stocks";
}

export default function DashboardPage() {
  const { isLoggedIn, loading: authLoading } = useRequireAuth();

  const [signals, setSignals] = useState<Signal[]>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("dashboard_signals");
      if (saved) {
        try {
          const parsed: Signal[] = JSON.parse(saved);
          return parsed.filter((s) => s.status === "ACTIVE" && !_isExpired(s));
        } catch {}
      }
    }
    return [];
  });

  const [adoptedSignals, setAdoptedSignals] = useState<Signal[]>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("adopted_signals");
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch {}
      }
    }
    return [];
  });

  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [activeTicker, setActiveTicker] = useState(() => {
    return (typeof window !== "undefined" && localStorage.getItem("dashboard_ticker")) || "AAPL";
  });

  const [activeProfile, setActiveProfile] = useState(() => {
    return (typeof window !== "undefined" && localStorage.getItem("dashboard_profile")) || "balanced";
  });

  const [chartInterval, setChartInterval] = useState(() => {
    const saved = typeof window !== "undefined" && localStorage.getItem("dashboard_profile");
    return PROFILE_TIMEFRAMES[saved || "balanced"]?.chart || "1d";
  });

  // Mirrors the pinned watchlist bar. Seeded from the key the HUD persists to
  // so the very first SCAN NOW - before any pin changes - already targets what
  // is on screen rather than a hardcoded list.
  const [watchlist, setWatchlist] = useState<string[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("cockpit_pinned_tabs");
        const parsed = saved ? JSON.parse(saved) : null;
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      } catch {}
    }
    return WATCHLIST_SEED;
  });

  // Chart canvas mode. Was a boolean that made the 3D surfaces REPLACE the
  // chart, so order flow and price could never be read together.
  const [canvasMode, setCanvasMode] = useState<"chart" | "split" | "flow">("chart");
  const show3D = canvasMode === "flow";
  const [chartType, setChartType] = useState<"tv" | "radar">("radar");
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [briefingOpen, setBriefingOpen] = useState(false);

  // Mobile View Tab: "radar" | "chart" | "agents"
  const [mobileTab, setMobileTab] = useState<"radar" | "chart" | "agents">("chart");

  // Save signals to localStorage
  useEffect(() => {
    const t = setTimeout(() => {
      localStorage.setItem("dashboard_signals", JSON.stringify(signals));
    }, 1000);
    return () => clearTimeout(t);
  }, [signals]);

  // Save adopted signals to localStorage
  useEffect(() => {
    localStorage.setItem("adopted_signals", JSON.stringify(adoptedSignals));
  }, [adoptedSignals]);

  // Save ticker and profile to localStorage
  useEffect(() => {
    localStorage.setItem("dashboard_ticker", activeTicker);
  }, [activeTicker]);

  useEffect(() => {
    localStorage.setItem("dashboard_profile", activeProfile);
    saveActiveProfile(activeProfile).catch(() => {});
  }, [activeProfile]);

  // Auto-switch chart timeframe when profile changes
  function handleProfileChange(slug: string) {
    setActiveProfile(slug);
    const tf = PROFILE_TIMEFRAMES[slug];
    if (tf) setChartInterval(tf.chart);
  }

  // Load signals from API
  // Set once the symbol on screen is the user's doing - either because they
  // picked it, or because the opening default has already been applied. It
  // stops the 30-second refresh from reasserting a default over a choice.
  const pickedTickerRef = useRef(false);

  const loadData = useCallback(async () => {
    const [sigs, agentData] = await Promise.allSettled([listSignals(20), getAgentStatus()]);
    if (sigs.status === "fulfilled") {
      const allFromApi = sigs.value;
      const activeOnly = allFromApi.filter((s) => s.status === "ACTIVE");
      const resolvedIds = new Set(
        allFromApi.filter((s) => s.status !== "ACTIVE").map((s) => s.signal_id)
      );

      setSignals((prev) => {
        const localById = new Map(prev.map((s) => [s.signal_id, s]));
        const merged = activeOnly.map((s) => {
          const local = localById.get(s.signal_id);
          return local ? { ...s, signal_mode: local.signal_mode } : s;
        });
        prev.forEach((s) => {
          if (
            s.status === "ACTIVE" &&
            !_isExpired(s) &&
            !resolvedIds.has(s.signal_id) &&
            !merged.some((m) => m.signal_id === s.signal_id)
          ) {
            merged.push(s);
          }
        });
        const seen = new Set<string>();
        return merged.filter((s) => {
          if (_isExpired(s)) return false;
          if (seen.has(s.ticker)) return false;
          seen.add(s.ticker);
          return true;
        });
      });

      // Keep the signal panel in step with the symbol on screen.
      //
      // This used to reach for activeOnly[0] and CHANGE THE SYMBOL whenever
      // the selected one had no signal. loadData runs every 30 seconds, so
      // choosing a symbol without an active setup - XAUUSD, say - held for at
      // most half a minute before the next poll dragged the chart back to
      // whichever symbol did have one. The user's own choice lost to a
      // background refresh, repeatedly, with nothing on screen to explain it.
      //
      // A default is only a default on the way in. After that the symbol
      // belongs to the user, and a symbol with no signal shows no signal
      // rather than borrowing another symbol's.
      if (activeOnly.length > 0) {
        const matchActive = activeOnly.find(
          (s) => s.ticker.toUpperCase() === activeTicker.toUpperCase()
        );
        if (matchActive) {
          setSelectedSignal(matchActive);
          pickedTickerRef.current = true;
        } else if (!pickedTickerRef.current && !selectedSignal) {
          pickedTickerRef.current = true;
          setSelectedSignal(activeOnly[0]);
          setActiveTicker(activeOnly[0].ticker);
        } else {
          setSelectedSignal(null);
        }
      }
    }
    if (agentData.status === "fulfilled") {
      setAgents(agentData.value.agents);
    }
  }, [selectedSignal, activeTicker]);

  useEffect(() => {
    if (!isLoggedIn) return;
    wakeBackend();
    loadData();
    const interval = setInterval(() => {
      if (!document.hidden) loadData();
    }, 30_000);
    return () => clearInterval(interval);
  }, [isLoggedIn, loadData]);

  // Handle Signal Selection from radar or list
  function handleSelectSignal(sig: Signal) {
    pickedTickerRef.current = true;
    setSelectedSignal(sig);
    setActiveTicker(sig.ticker);
    setAnalysisError(null);
    setMobileTab("chart");
  }

  // Handle direct Ticker Selection from Ribbon or Search
  function handleSelectTicker(tickerName: string) {
    const clean = tickerName.trim().toUpperCase();
    if (!clean) return;
    pickedTickerRef.current = true;
    setActiveTicker(clean);
    setAnalysisError(null);
    setMobileTab("chart");

    // Check if we have an active, non-expired cached signal for this symbol
    const existing = signals.find(
      (s) => s.ticker.toUpperCase() === clean && s.status === "ACTIVE" && !_isExpired(s)
    );
    if (existing) {
      setSelectedSignal(existing);
    } else {
      setSelectedSignal(null);
      handleGenerate(clean);
    }
  }

  // Toggle Adopt Signal (Pins to My Desk)
  function handleToggleAdopt(sig: Signal) {
    setAdoptedSignals((prev) => {
      const exists = prev.some((s) => s.signal_id === sig.signal_id);
      if (exists) {
        return prev.filter((s) => s.signal_id !== sig.signal_id);
      } else {
        return [sig, ...prev];
      }
    });
  }

  // Absorb a finished scan's signals into the list on screen.
  const absorbScanResults = useCallback((incoming: ScanResult[]) => {
    if (!incoming || incoming.length === 0) return;
    setSignals((prev) => {
      const map = new Map(prev.map((sg) => [sg.ticker, sg]));
      for (const sg of incoming) {
        const converted: Signal = {
          signal_id: sg.signal_id,
          ticker: sg.ticker,
          direction: sg.direction,
          confidence_score: sg.confidence_score,
          entry_price: sg.entry_price,
          stop_loss: sg.stop_loss,
          status: "ACTIVE",
          timeframe: PROFILE_TIMEFRAMES[activeProfile]?.timeframe || "1D",
          asset_class: inferAssetClass(sg.ticker),
          agent_votes: {},
          reasoning_chain: sg.summary ? [sg.summary] : [],
          strategy_sources: ["Confluence Screener"],
          timestamp: sg.timestamp || new Date().toISOString(),
          expiry_time: new Date(Date.now() + 24 * 3600 * 1000).toISOString(),
        };
        map.set(sg.ticker, converted);
      }
      return Array.from(map.values());
    });
  }, [activeProfile]);

  // Trigger Scanner
  //
  // The scan runs on the server and this polls it. It used to be a single
  // awaited request: leaving the dashboard unmounted the component while that
  // request was still open, so the result arrived nowhere, the button never
  // came out of its scanning state, and the work could be cancelled along with
  // the connection. Now the page can be left and come back to a scan that
  // carried on without it.
  async function handleScanNow() {
    setScanning(true);
    setAnalysisError(null);
    try {
      const job = await scanAsync(watchlist, true, activeProfile);
      if (job.state === "done") {
        absorbScanResults(job.signals);
        setScanning(false);
      } else if (job.state === "error") {
        setAnalysisError(job.error || "Scan failed");
        setScanning(false);
      }
      // "running" is left to the poller below.
    } catch (e) {
      setAnalysisError(e instanceof Error ? e.message : "Scan failed");
      setScanning(false);
    }
  }

  // Poll the server's scan job.
  //
  // This runs on mount too, not only after the button is pressed, so returning
  // to the dashboard mid-scan shows the scan that is actually in progress
  // rather than an idle button. It stops as soon as the job is not running.
  useEffect(() => {
    if (!isLoggedIn) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async (isFirst = false) => {
      try {
        const job = await getScanStatus();
        if (cancelled) return;

        if (job.state === "running") {
          setScanning(true);
          timer = setTimeout(() => poll(), 2000);
          return;
        }
        // Only adopt a finished job's signals if we were tracking it - on the
        // very first poll that means a scan this page did not start, which is
        // exactly the case worth picking up.
        if (job.state === "done") {
          absorbScanResults(job.signals);
        } else if (job.state === "error" && !isFirst) {
          setAnalysisError(job.error || "Scan failed");
        }
        setScanning(false);
      } catch {
        // A failing status endpoint should not pin the button on forever.
        if (!cancelled) setScanning(false);
      }
    };

    poll(true);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [isLoggedIn, absorbScanResults]);

  // Generate on-demand signal for ticker
  async function handleGenerate(t?: string) {
    const tickerToGen = (t || activeTicker).trim().toUpperCase();
    setLoading(true);
    setAnalysisError(null);
    setActiveTicker(tickerToGen);
    try {
      const signal = await generateSignal(
        tickerToGen,
        undefined,
        PROFILE_TIMEFRAMES[activeProfile]?.timeframe || "1D",
        activeProfile
      );

      if (signal.status !== "ACTIVE" && signal.status !== "NO_SIGNAL") {
        const why = (signal as { status_reasons?: string[] }).status_reasons;
        setAnalysisError(
          `${signal.ticker}: ${String(signal.status).replace(/_/g, " ").toLowerCase()}` +
            (why?.length ? ` — ${why[0]}` : "")
        );
      }

      setSignals((prev) => {
        return [signal, ...prev.filter((s) => s.ticker !== signal.ticker).slice(0, 15)];
      });
      setSelectedSignal(signal);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Analysis failed";
      setAnalysisError(msg);
    } finally {
      setLoading(false);
    }
  }

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <div className="live-dot mx-auto mb-3" />
          <p className="text-xs font-mono text-muted-foreground tracking-widest">
            AUTHENTICATING COMMAND HUD
          </p>
        </div>
      </div>
    );
  }

  if (!isLoggedIn) return null;

  return (
    <div className="flex flex-col h-[calc(100vh-var(--chrome-h))] bg-background overflow-hidden">
      {/* Top Header: Kill Zones, Clocks, Regime Status, Strategy Profile, Briefing Drawer Toggle */}
      <CockpitHeader
        activeProfile={activeProfile}
        onProfileChange={handleProfileChange}
        regimeText="VOL EXPANSION"
        regimeState="NEUTRAL"
        onToggleBriefing={() => setBriefingOpen(!briefingOpen)}
        briefingOpen={briefingOpen}
      />

      {/* Slide-over Daily Regime Briefing Modal */}
      <PreMarketBriefing isOpen={briefingOpen} onClose={() => setBriefingOpen(false)} />

      {/* Analysis Error Notification Banner */}
      {analysisError && (
        <div className="px-4 py-1.5 bg-warn/10 border-b border-warn/30 text-warn text-xs font-mono flex items-center justify-between z-30">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span>{analysisError}</span>
          </div>
          <button
            onClick={() => setAnalysisError(null)}
            className="text-[12px] uppercase font-bold hover:text-foreground"
          >
            DISMISS
          </button>
        </div>
      )}

      {/* Mobile Tab Switcher (Visible on small screens) */}
      <div className="lg:hidden flex items-center border-b border-border/40 bg-surface-2">
        <button
          onClick={() => setMobileTab("radar")}
          className={cn(
            "flex-1 py-1.5 text-xs font-mono font-bold flex items-center justify-center gap-1.5 border-r border-border/30",
            mobileTab === "radar" ? "text-primary bg-surface-1 border-b-2 border-b-primary" : "text-muted-foreground"
          )}
        >
          <Radar className="h-3.5 w-3.5" />
          <span>RADAR ({signals.length})</span>
        </button>
        <button
          onClick={() => setMobileTab("chart")}
          className={cn(
            "flex-1 py-1.5 text-xs font-mono font-bold flex items-center justify-center gap-1.5 border-r border-border/30",
            mobileTab === "chart" ? "text-primary bg-surface-1 border-b-2 border-b-primary" : "text-muted-foreground"
          )}
        >
          <LineChart className="h-3.5 w-3.5" />
          <span>CHART ({activeTicker})</span>
        </button>
        <button
          onClick={() => setMobileTab("agents")}
          className={cn(
            "flex-1 py-1.5 text-xs font-mono font-bold flex items-center justify-center gap-1.5",
            mobileTab === "agents" ? "text-primary bg-surface-1 border-b-2 border-b-primary" : "text-muted-foreground"
          )}
        >
          <Brain className="h-3.5 w-3.5" />
          <span>AGENTS</span>
        </button>
      </div>

      {/* Main 3-Pane Tactical Command Cockpit */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Left Pane: Confluence Radar & Signal Stream */}
        <aside
          className={cn(
            "w-full lg:w-[320px] xl:w-[360px] shrink-0 h-full flex flex-col",
            mobileTab !== "radar" && "hidden lg:flex"
          )}
        >
          <SignalRadar
            signals={signals}
            activeSignalId={selectedSignal?.signal_id || null}
            onSelectSignal={handleSelectSignal}
            adoptedSignals={adoptedSignals}
            onToggleAdopt={handleToggleAdopt}
            onScanNow={handleScanNow}
            scanning={scanning}
            onSelectTicker={handleSelectTicker}
          />
        </aside>

        {/* Center Pane: Deep Canvas Viewport */}
        <main
          className={cn(
            "flex-1 h-full flex flex-col min-w-0 overflow-hidden bg-surface-0",
            mobileTab !== "chart" && "hidden lg:flex"
          )}
        >
          {/* Floating Canvas HUD */}
          <TradingCanvasHUD
            ticker={activeTicker}
            onSelectTicker={handleSelectTicker}
            signal={selectedSignal}
            activeInterval={chartInterval}
            onIntervalChange={setChartInterval}
            show3D={show3D}
            canvasMode={canvasMode}
            chartType={chartType}
            onChartTypeChange={setChartType}
            onToggle3D={() =>
              setCanvasMode((m) => (m === "chart" ? "split" : m === "split" ? "flow" : "chart"))
            }
            onAdoptSignal={selectedSignal ? handleToggleAdopt : undefined}
            isAdopted={selectedSignal ? adoptedSignals.some((s) => s.signal_id === selectedSignal.signal_id) : false}
            onGenerate={handleGenerate}
            analyzing={loading}
            onWatchlistChange={setWatchlist}
          />

          {/* Chart / Order-flow canvas.
              Three modes rather than a boolean. The 3D surfaces used to
              REPLACE the chart, so price action and order-flow density could
              never be read against each other - which is the only reason to
              look at either. Split stacks them vertically: candles need width
              far more than height, depth surfaces read well short and wide. */}
          <div className="flex-1 w-full h-full relative overflow-hidden bg-background flex flex-col">
            {canvasMode !== "flow" && (
              <div className={cn(
                "relative w-full min-h-0",
                canvasMode === "split" ? "h-[58%] border-b border-border/40" : "flex-1"
              )}>
                {chartType === "radar" ? (
                  <OrderFlowChart
                    ticker={activeTicker}
                    interval={chartInterval}
                    fillContainer={true}
                  />
                ) : (
                  <TradingViewChart
                    ticker={activeTicker}
                    interval={chartInterval}
                    fillContainer={true}
                  />
                )}
              </div>
            )}

            {canvasMode !== "chart" && (
              <div className={cn(
                "w-full min-h-0 flex flex-col bg-background",
                canvasMode === "split" ? "flex-1" : "h-full"
              )}>
                <div className="flex items-center justify-between px-3 py-1.5 border-b border-border/40 shrink-0">
                  <span className="text-xs font-mono font-bold text-primary">
                    MICROSTRUCTURE 3D ORDER FLOW DENSITY
                    <span className="ml-2 text-muted-foreground font-normal">{activeTicker}</span>
                  </span>
                  <button
                    onClick={() => setCanvasMode("chart")}
                    className="text-[12px] font-mono px-2 py-0.5 rounded border border-border/40 bg-surface-2 text-muted-foreground hover:text-foreground"
                  >
                    RETURN TO CANDLE VIEW
                  </button>
                </div>
                {/* min-h-0 on both the row and each cell: without it the canvas
                    children refuse to shrink and push the page taller than the
                    viewport, which is the scroll defect fixed in 596e79d. */}
                <div className="flex-1 min-h-0 grid grid-cols-1 xl:grid-cols-2 gap-2 p-2">
                  <div className="rounded border border-border/40 overflow-hidden min-h-0">
                    <DepthSurface3D ticker={activeTicker} />
                  </div>
                  <div className="rounded border border-border/40 overflow-hidden min-h-0">
                    <LiquiditySurface3D ticker={activeTicker} />
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>

        {/* Right Pane: 9-Agent Consensus Brain */}
        <aside
          className={cn(
            "w-full lg:w-[340px] xl:w-[380px] shrink-0 h-full flex flex-col",
            mobileTab !== "agents" && "hidden lg:flex"
          )}
        >
          <AgentConsensusHUD
            signal={selectedSignal}
            activeTicker={activeTicker}
            onGenerate={handleGenerate}
            loading={loading}
          />
        </aside>
      </div>

      {/* Upgrade Modal */}
      {upgradeOpen && (
        <UpgradeModal
          isOpen={upgradeOpen}
          onClose={() => setUpgradeOpen(false)}
          feature="Pro Confluence Signals"
          requiredTier="retail"
        />
      )}
    </div>
  );
}
