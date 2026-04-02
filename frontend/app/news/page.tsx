"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw, ExternalLink, Globe, TrendingUp, TrendingDown, Minus, AlertTriangle, DollarSign, Zap, Building2, BellRing, BarChart3, PieChart, Hash, Calendar, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { timeAgo } from "@/lib/utils";
import { ScannerPanel } from "@/components/ScannerPanel";
import { supabase } from "@/lib/supabase";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getAuthToken(): Promise<string | null> {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) return session.access_token;
  } catch {}
  return typeof window !== "undefined" ? localStorage.getItem("token") : null;
}

interface ScannerAlert {
  id:         string;
  ticker:     string;
  direction:  string;
  confidence: number;
  summary:    string;
  entry_hint: number;
  created_at: string;
  read:       boolean;
}

interface Article {
  id:              string;
  headline:        string;
  summary:         string | null;
  source:          string;
  url:             string;
  published_at:    string | null;
  scraped_at:      string | null;
  category:        string;
  sentiment:       string;
  sentiment_score: number;
  tickers:         string[];
}

interface Summary {
  total:        number;
  categories:   { category: string; count: number; latest_at: string | null }[];
  last_scraped: string | null;
}

interface EconRelease {
  name: string;
  date: string;
  release_id: number | null;
}

interface MacroIndicator {
  value: number;
  date: string;
  trend: string;
}

interface CongressTrade {
  representative: string;
  ticker: string;
  transaction: string;
  amount: string;
  date: string;
  party: string;
  district: string;
}

interface InsiderTrade {
  insider: string;
  ticker: string;
  title: string;
  transaction_type: string;
  shares: number;
  price: number;
  value: number;
  date: string;
}

const CATEGORIES = ["ALL", "MARKETS", "MACRO", "EARNINGS", "FED", "GEOPOLITICAL", "CRISIS", "ECON_CAL", "ALT_DATA"] as const;

const CATEGORY_META: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; color: string; barColor: string }> = {
  MARKETS:      { label: "Markets",      icon: TrendingUp,     color: "text-primary border-primary/30 bg-primary/5",   barColor: "bg-primary" },
  MACRO:        { label: "Macro",        icon: Globe,          color: "text-info border-info/30 bg-info/5",             barColor: "bg-info" },
  EARNINGS:     { label: "Earnings",     icon: DollarSign,     color: "text-bull border-bull/30 bg-bull/5",             barColor: "bg-bull" },
  FED:          { label: "Fed",          icon: Building2,      color: "text-warn border-warn/30 bg-warn/5",             barColor: "bg-warn" },
  GEOPOLITICAL: { label: "Geopolitical", icon: Globe,          color: "text-bear border-bear/30 bg-bear/5",             barColor: "bg-bear" },
  CRISIS:       { label: "Crisis",       icon: AlertTriangle,  color: "text-bear border-bear/50 bg-bear/10",            barColor: "bg-bear" },
  ECON_CAL:     { label: "Econ Cal",    icon: Calendar,       color: "text-primary border-primary/30 bg-primary/5",   barColor: "bg-primary" },
  ALT_DATA:     { label: "Alt Data",    icon: Users,          color: "text-warn border-warn/30 bg-warn/5",             barColor: "bg-warn" },
};

const SENTIMENT_META = {
  POSITIVE: { icon: TrendingUp,   color: "text-bull",  label: "+" },
  NEGATIVE: { icon: TrendingDown, color: "text-bear",  label: "−" },
  NEUTRAL:  { icon: Minus,        color: "text-muted-foreground", label: "·" },
};

const SOURCE_COLORS: Record<string, string> = {
  "Reuters":       "text-[#ff8000]",
  "CNBC":          "text-[#0081c8]",
  "CNBC Markets":  "text-[#0081c8]",
  "MarketWatch":   "text-[#2db04b]",
  "Yahoo Finance": "text-[#6001d2]",
  "WSJ Markets":   "text-[#004d6d]",
  "BBC Business":  "text-[#bb1919]",
  "BBC World":     "text-[#bb1919]",
  "AP News":       "text-[#cc0000]",
  "AP Finance":    "text-[#cc0000]",
  "Federal Reserve": "text-warn",
};

export default function NewsPage() {
  const [articles, setArticles]     = useState<Article[]>([]);
  const [summary, setSummary]       = useState<Summary | null>(null);
  const [activeCategory, setActive] = useState<string>("ALL");
  const [loading, setLoading]       = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [waking, setWaking]         = useState(false);
  const [scanAlerts, setScanAlerts] = useState<ScannerAlert[]>([]);
  const [econReleases, setEconReleases] = useState<EconRelease[]>([]);
  const [macroSnapshot, setMacroSnapshot] = useState<Record<string, MacroIndicator>>({});
  const [congressTrades, setCongressTrades] = useState<CongressTrade[]>([]);
  const [insiderTrades, setInsiderTrades] = useState<InsiderTrade[]>([]);
  const [altDataLoading, setAltDataLoading] = useState(false);
  const [econLoading, setEconLoading] = useState(false);

  // Load recent scanner alerts on mount
  useEffect(() => {
    async function loadAlerts() {
      try {
        const token = await getAuthToken();
        if (!token) return;
        const res = await fetch(`${API}/api/v1/alerts?limit=10`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) setScanAlerts(await res.json());
      } catch { /* not premium or not logged in — skip */ }
    }
    loadAlerts();
  }, []);

  const loadNews = useCallback(async (category: string) => {
    setFetchError(null);
    const params = category !== "ALL" ? `?category=${category}&limit=100` : "?limit=100";

    async function tryFetch(_attempt: number) {
      const [artRes, sumRes] = await Promise.all([
        fetch(`${API}/api/v1/news${params}`),
        fetch(`${API}/api/v1/news/summary`),
      ]);
      if (artRes.ok) setArticles(await artRes.json());
      else setFetchError(`News feed returned ${artRes.status}`);
      if (sumRes.ok) setSummary(await sumRes.json());
    }

    try {
      await tryFetch(0);
    } catch {
      setWaking(true);
      for (let attempt = 1; attempt <= 2; attempt++) {
        await new Promise(r => setTimeout(r, 22_000));
        try {
          await tryFetch(attempt);
          setWaking(false);
          setLoading(false);
          setRefreshing(false);
          return;
        } catch {}
      }
      setWaking(false);
      setFetchError(`Backend unreachable — is the server running? [${API}]`);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  // Load special tab data when selected
  useEffect(() => {
    if (activeCategory === "ECON_CAL") {
      setEconLoading(true);
      fetch(`${API}/api/v1/news/economic-calendar`)
        .then(r => r.json())
        .then(data => {
          setEconReleases(data.releases || []);
          setMacroSnapshot(data.macro_snapshot || {});
        })
        .catch(() => {})
        .finally(() => setEconLoading(false));
      return;
    }
    if (activeCategory === "ALT_DATA") {
      setAltDataLoading(true);
      fetch(`${API}/api/v1/news/alternative-data`)
        .then(r => r.json())
        .then(data => {
          setCongressTrades(data.congressional_trades || []);
          setInsiderTrades(data.insider_trades || []);
        })
        .catch(() => {})
        .finally(() => setAltDataLoading(false));
      return;
    }
  }, [activeCategory]);

  useEffect(() => { setLoading(true); loadNews(activeCategory); }, [activeCategory, loadNews]);

  useEffect(() => {
    const id = setInterval(() => loadNews(activeCategory), 60_000);
    return () => clearInterval(id);
  }, [activeCategory, loadNews]);

  async function handleRefresh() {
    setRefreshing(true);
    await fetch(`${API}/api/v1/news/refresh`, { method: "POST" });
    [6000, 12000, 20000, 30000].forEach((delay) => {
      setTimeout(() => loadNews(activeCategory), delay);
    });
    setTimeout(() => setRefreshing(false), 32000);
  }

  const crisisArticles = articles.filter(a => a.category === "CRISIS");
  const normalArticles = articles.filter(a => a.category !== "CRISIS");

  // Compute infographic data
  const posCount = articles.filter(a => a.sentiment === "POSITIVE").length;
  const negCount = articles.filter(a => a.sentiment === "NEGATIVE").length;
  const neuCount = articles.filter(a => a.sentiment === "NEUTRAL").length;
  const totalArticles = articles.length || 1;

  // Trending tickers: count mentions across all articles
  const tickerCounts: Record<string, number> = {};
  articles.forEach(a => a.tickers.forEach(t => { tickerCounts[t] = (tickerCounts[t] || 0) + 1; }));
  const trendingTickers = Object.entries(tickerCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  // Sources breakdown
  const sourceCounts: Record<string, number> = {};
  articles.forEach(a => { sourceCounts[a.source] = (sourceCounts[a.source] || 0) + 1; });
  const topSources = Object.entries(sourceCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  return (
    <div className="h-[calc(100vh-72px)] flex flex-col bg-background overflow-hidden">

      {/* ── TOP INTEL BAR ──────────────────────────────────────────── */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-border bg-[hsl(0_0%_3%)] shrink-0">
        <div className="flex items-center gap-2">
          <span className="live-dot" />
          <span className="terminal-label text-primary">MARKET INTELLIGENCE</span>
        </div>

        {summary && (
          <div className="flex items-center gap-3 ml-4">
            <span className="text-[13px] font-mono text-muted-foreground">
              {summary.total.toLocaleString()} articles
            </span>
            {summary.last_scraped && (
              <span className="text-[13px] font-mono text-muted-foreground">
                last update {timeAgo(summary.last_scraped)}
              </span>
            )}
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 text-[13px] font-mono font-bold px-2.5 py-1 rounded border border-primary/30 text-primary hover:bg-primary/10 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={cn("h-2.5 w-2.5", refreshing && "animate-spin")} />
            {refreshing ? "SCRAPING…" : "REFRESH"}
          </button>
        </div>
      </div>

      {/* ── WAKING BANNER ───────────────────────────────────────────── */}
      {waking && (
        <div className="flex items-center gap-3 px-4 py-2 bg-warn/10 border-b border-warn/30 shrink-0">
          <Zap className="h-3.5 w-3.5 text-warn shrink-0 animate-pulse" />
          <span className="text-[14px] font-mono font-bold text-warn tracking-widest">WAKING BACKEND</span>
          <span className="text-[14px] font-mono text-warn/80">
            Render free tier — cold start in progress, retrying…
          </span>
        </div>
      )}

      {/* ── CRISIS BANNER ─────────────────────────────────────────── */}
      {crisisArticles.length > 0 && (
        <div className="flex items-center gap-3 px-4 py-2 bg-bear/10 border-b border-bear/30 shrink-0">
          <AlertTriangle className="h-3.5 w-3.5 text-bear shrink-0" />
          <span className="text-[14px] font-mono font-bold text-bear tracking-widest">ALERT</span>
          <span className="text-[14px] font-mono text-bear/80 truncate">
            {crisisArticles[0].headline}
          </span>
          <a
            href={crisisArticles[0].url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto text-[13px] font-mono text-bear hover:text-bear/70 flex items-center gap-1 shrink-0"
          >
            READ <ExternalLink className="h-2.5 w-2.5" />
          </a>
        </div>
      )}

      {/* ── CATEGORY FILTER TABS ────────────────────────────────────── */}
      <div className="flex items-center border-b border-border bg-[hsl(0_0%_3%)] shrink-0 overflow-x-auto">
        {CATEGORIES.map((cat) => {
          const meta = cat !== "ALL" ? CATEGORY_META[cat] : null;
          const count = cat === "ALL"
            ? summary?.total
            : summary?.categories.find(c => c.category === cat)?.count;

          return (
            <button
              key={cat}
              onClick={() => setActive(cat)}
              className={cn(
                "flex items-center gap-1.5 px-4 py-2.5 text-[14px] font-mono font-bold tracking-widest whitespace-nowrap border-b-2 transition-colors",
                activeCategory === cat
                  ? "text-primary border-primary bg-primary/5"
                  : "text-muted-foreground border-transparent hover:text-foreground hover:border-border"
              )}
            >
              {meta?.icon && <meta.icon className="h-2.5 w-2.5" />}
              {cat === "ALL" ? "ALL INTEL" : meta?.label}
              {count !== undefined && (
                <span className={cn(
                  "text-[8px] font-mono px-1 rounded",
                  activeCategory === cat ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                )}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── MAIN CONTENT ─────────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* LEFT — Infographics + Card Grid */}
        <div className="flex-1 overflow-y-auto">

          {loading && (
            <div className="flex items-center justify-center h-40">
              <div className="flex items-center gap-2 text-[14px] font-mono text-muted-foreground">
                <span className="h-3 w-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
                LOADING INTEL FEED…
              </div>
            </div>
          )}

          {!loading && fetchError && (
            <div className="mx-4 mt-4 px-3 py-2 text-xs font-mono text-bear bg-bear/10 border border-bear/20 rounded">
              ERR — {fetchError}
            </div>
          )}

          {!loading && !fetchError && articles.length === 0 && (
            <div className="flex flex-col items-center justify-center h-60 gap-3">
              <Globe className="h-8 w-8 text-muted-foreground/20" />
              <div className="text-[14px] font-mono text-muted-foreground text-center">
                NO ARTICLES YET<br />
                <span className="text-[13px]">Click REFRESH to trigger the first scrape</span>
              </div>
            </div>
          )}

          {/* ── INFOGRAPHICS ROW ────────────────────────────────────── */}
          {!loading && articles.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 p-4 border-b border-border bg-[hsl(0_0%_2%)]">

              {/* Sentiment Donut */}
              <div className="rounded-lg border border-border bg-background p-4">
                <div className="flex items-center gap-1.5 mb-3">
                  <PieChart className="h-3 w-3 text-primary" />
                  <span className="text-[13px] font-mono font-bold text-muted-foreground tracking-widest">SENTIMENT</span>
                </div>
                <div className="flex items-center gap-4">
                  <SentimentDonut positive={posCount} neutral={neuCount} negative={negCount} />
                  <div className="space-y-1.5">
                    {[
                      { label: "Bullish", count: posCount, color: "bg-bull", textColor: "text-bull" },
                      { label: "Neutral", count: neuCount, color: "bg-muted-foreground", textColor: "text-muted-foreground" },
                      { label: "Bearish", count: negCount, color: "bg-bear", textColor: "text-bear" },
                    ].map(({ label, count, color, textColor }) => (
                      <div key={label} className="flex items-center gap-2">
                        <div className={cn("h-2 w-2 rounded-full", color)} />
                        <span className={cn("text-[13px] font-mono", textColor)}>{label}</span>
                        <span className="text-[13px] font-mono text-muted-foreground ml-auto">{Math.round(count / totalArticles * 100)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Category Distribution */}
              <div className="rounded-lg border border-border bg-background p-4">
                <div className="flex items-center gap-1.5 mb-3">
                  <BarChart3 className="h-3 w-3 text-primary" />
                  <span className="text-[13px] font-mono font-bold text-muted-foreground tracking-widest">CATEGORIES</span>
                </div>
                <div className="space-y-2">
                  {summary?.categories
                    .filter(c => CATEGORY_META[c.category])
                    .sort((a, b) => b.count - a.count)
                    .slice(0, 5)
                    .map(cat => {
                      const meta = CATEGORY_META[cat.category];
                      const maxCount = Math.max(...(summary?.categories.map(c => c.count) || [1]));
                      return (
                        <div key={cat.category}>
                          <div className="flex items-center justify-between mb-0.5">
                            <span className={cn("text-[8px] font-mono font-bold", meta.color.split(" ")[0])}>{meta.label}</span>
                            <span className="text-[8px] font-mono text-muted-foreground">{cat.count}</span>
                          </div>
                          <div className="h-1.5 bg-muted/30 rounded-full overflow-hidden">
                            <div
                              className={cn("h-full rounded-full transition-all duration-500", meta.barColor)}
                              style={{ width: `${(cat.count / maxCount) * 100}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>

              {/* Trending Tickers */}
              <div className="rounded-lg border border-border bg-background p-4">
                <div className="flex items-center gap-1.5 mb-3">
                  <Hash className="h-3 w-3 text-primary" />
                  <span className="text-[13px] font-mono font-bold text-muted-foreground tracking-widest">TRENDING TICKERS</span>
                </div>
                {trendingTickers.length === 0 ? (
                  <div className="text-[13px] font-mono text-muted-foreground/50">No ticker mentions yet</div>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {trendingTickers.map(([ticker, count], i) => (
                      <div
                        key={ticker}
                        className={cn(
                          "flex items-center gap-1 px-2 py-1 rounded border font-mono",
                          i === 0
                            ? "border-primary/40 bg-primary/10 text-primary"
                            : i < 3
                              ? "border-primary/20 bg-primary/5 text-primary/80"
                              : "border-border/50 bg-muted/20 text-muted-foreground"
                        )}
                      >
                        <span className="text-[13px] font-bold">{ticker}</span>
                        <span className="text-[7px] opacity-60">{count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Sources Breakdown */}
              <div className="rounded-lg border border-border bg-background p-4">
                <div className="flex items-center gap-1.5 mb-3">
                  <Globe className="h-3 w-3 text-primary" />
                  <span className="text-[13px] font-mono font-bold text-muted-foreground tracking-widest">TOP SOURCES</span>
                </div>
                <div className="space-y-1.5">
                  {topSources.map(([source, count]) => {
                    const srcColor = SOURCE_COLORS[source] || "text-muted-foreground";
                    return (
                      <div key={source} className="flex items-center justify-between">
                        <span className={cn("text-[13px] font-mono font-bold truncate", srcColor)}>{source}</span>
                        <span className="text-[13px] font-mono text-muted-foreground ml-2 shrink-0">{count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* ── NEWS CARD GRID ──────────────────────────────────────── */}
          {!loading && normalArticles.length > 0 && activeCategory !== "ECON_CAL" && activeCategory !== "ALT_DATA" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 p-4">
              {normalArticles.map((article) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          )}

          {/* ── ECONOMIC CALENDAR PANEL ────────────────────────────── */}
          {activeCategory === "ECON_CAL" && (
            <div className="p-4 space-y-4">
              {econLoading ? (
                <div className="flex items-center justify-center h-40">
                  <div className="flex items-center gap-2 text-[14px] font-mono text-muted-foreground">
                    <span className="h-3 w-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
                    LOADING ECONOMIC DATA…
                  </div>
                </div>
              ) : (
                <>
                  {/* Macro Snapshot */}
                  {Object.keys(macroSnapshot).length > 0 && (
                    <div className="rounded-lg border border-border bg-background p-4">
                      <div className="flex items-center gap-1.5 mb-3">
                        <BarChart3 className="h-3 w-3 text-primary" />
                        <span className="text-[13px] font-mono font-bold text-muted-foreground tracking-widest">LIVE MACRO INDICATORS (FRED)</span>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
                        {Object.entries(macroSnapshot).map(([key, ind]) => {
                          const labels: Record<string, string> = {
                            gdp_growth: "GDP Growth", cpi_yoy: "CPI Index", fed_funds: "Fed Funds Rate",
                            unemployment: "Unemployment", yield_10y: "10Y Yield", yield_2y: "2Y Yield",
                            yield_curve_spread: "Yield Spread", initial_claims: "Jobless Claims",
                            pce_inflation: "PCE Index", ism_manufacturing: "Mfg Employment",
                          };
                          const trendColor = ind.trend === "RISING" ? "text-bull" : ind.trend === "FALLING" ? "text-bear" : "text-muted-foreground";
                          const isPercent = ["gdp_growth", "fed_funds", "unemployment", "yield_10y", "yield_2y", "yield_curve_spread"].includes(key);
                          return (
                            <div key={key} className="rounded border border-border/60 bg-background p-3">
                              <div className="text-[8px] font-mono text-muted-foreground tracking-widest mb-1">
                                {labels[key] || key.toUpperCase()}
                              </div>
                              <div className="text-[14px] font-mono font-bold text-foreground">
                                {isPercent ? `${ind.value.toFixed(2)}%` : key === "initial_claims" ? ind.value.toLocaleString() : ind.value.toFixed(1)}
                              </div>
                              <div className={cn("text-[8px] font-mono font-bold mt-0.5", trendColor)}>
                                {ind.trend} <span className="text-muted-foreground font-normal">· {ind.date}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Upcoming Releases */}
                  <div className="rounded-lg border border-border bg-background p-4">
                    <div className="flex items-center gap-1.5 mb-3">
                      <Calendar className="h-3 w-3 text-primary" />
                      <span className="text-[13px] font-mono font-bold text-muted-foreground tracking-widest">UPCOMING DATA RELEASES</span>
                    </div>
                    {econReleases.length === 0 ? (
                      <div className="text-[13px] font-mono text-muted-foreground/50 py-4 text-center">
                        No upcoming releases found. FRED API key may not be configured.
                      </div>
                    ) : (
                      <div className="space-y-1">
                        {econReleases.map((r, i) => (
                          <div key={`${r.name}-${r.date}-${i}`} className="flex items-center gap-3 px-3 py-2 rounded border border-border/40 hover:border-primary/20 transition-colors">
                            <div className="text-[13px] font-mono text-primary font-bold w-24 shrink-0">{r.date}</div>
                            <div className="text-[13px] font-mono text-foreground flex-1">{r.name}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {/* ── ALTERNATIVE DATA PANEL ─────────────────────────────── */}
          {activeCategory === "ALT_DATA" && (
            <div className="p-4 space-y-4">
              {altDataLoading ? (
                <div className="flex items-center justify-center h-40">
                  <div className="flex items-center gap-2 text-[14px] font-mono text-muted-foreground">
                    <span className="h-3 w-3 rounded-full border-2 border-warn/30 border-t-warn animate-spin" />
                    LOADING ALTERNATIVE DATA…
                  </div>
                </div>
              ) : (
                <>
                  {/* Congressional Trades */}
                  <div className="rounded-lg border border-border bg-background p-4">
                    <div className="flex items-center gap-1.5 mb-3">
                      <Building2 className="h-3 w-3 text-warn" />
                      <span className="text-[13px] font-mono font-bold text-muted-foreground tracking-widest">CONGRESSIONAL TRADES</span>
                      <span className="text-[8px] font-mono text-warn/60 ml-1">QUIVERQUANT</span>
                    </div>
                    {congressTrades.length === 0 ? (
                      <div className="text-[13px] font-mono text-muted-foreground/50 py-4 text-center">
                        No data available. QuiverQuant API key may not be configured.
                      </div>
                    ) : (
                      <div className="space-y-1">
                        {congressTrades.map((t, i) => {
                          const isBuy = t.transaction.toLowerCase().includes("purchase");
                          return (
                            <div key={`congress-${i}`} className="flex items-center gap-2 px-3 py-2 rounded border border-border/40 hover:border-primary/20 transition-colors">
                              <span className={cn(
                                "text-[8px] font-mono font-bold px-1.5 py-0.5 rounded",
                                isBuy ? "bg-bull/10 text-bull" : "bg-bear/10 text-bear"
                              )}>
                                {isBuy ? "BUY" : "SELL"}
                              </span>
                              <span className="text-[13px] font-mono text-primary font-bold w-14 shrink-0">{t.ticker}</span>
                              <span className="text-[13px] font-mono text-foreground flex-1 truncate">{t.representative}</span>
                              <span className="text-[8px] font-mono text-muted-foreground shrink-0">
                                ({t.party}) {t.amount}
                              </span>
                              <span className="text-[13px] font-mono text-muted-foreground shrink-0">{t.date}</span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Insider Trades */}
                  <div className="rounded-lg border border-border bg-background p-4">
                    <div className="flex items-center gap-1.5 mb-3">
                      <Users className="h-3 w-3 text-warn" />
                      <span className="text-[13px] font-mono font-bold text-muted-foreground tracking-widest">INSIDER TRANSACTIONS</span>
                      <span className="text-[8px] font-mono text-warn/60 ml-1">SEC FILINGS</span>
                    </div>
                    {insiderTrades.length === 0 ? (
                      <div className="text-[13px] font-mono text-muted-foreground/50 py-4 text-center">
                        No data available. QuiverQuant API key may not be configured.
                      </div>
                    ) : (
                      <div className="space-y-1">
                        {insiderTrades.map((t, i) => {
                          const isBuy = t.transaction_type.toLowerCase().includes("buy") || t.transaction_type.toLowerCase().includes("purchase");
                          return (
                            <div key={`insider-${i}`} className="flex items-center gap-2 px-3 py-2 rounded border border-border/40 hover:border-primary/20 transition-colors">
                              <span className={cn(
                                "text-[8px] font-mono font-bold px-1.5 py-0.5 rounded",
                                isBuy ? "bg-bull/10 text-bull" : "bg-bear/10 text-bear"
                              )}>
                                {isBuy ? "BUY" : "SELL"}
                              </span>
                              <span className="text-[13px] font-mono text-primary font-bold w-14 shrink-0">{t.ticker}</span>
                              <span className="text-[13px] font-mono text-foreground flex-1 truncate" title={t.title}>
                                {t.insider}
                              </span>
                              <span className="text-[13px] font-mono text-muted-foreground shrink-0">
                                {t.shares.toLocaleString()} shares
                              </span>
                              <span className="text-[13px] font-mono text-muted-foreground shrink-0">{t.date}</span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* RIGHT SIDEBAR — Scanner + Alerts */}
        <div className="hidden lg:block w-64 shrink-0 border-l border-border overflow-y-auto">

          {/* Agent Alerts feed */}
          <div className="terminal-header">
            <BellRing className="h-2.5 w-2.5 text-primary" />
            <span className="terminal-label ml-1">AGENT ALERTS</span>
            {scanAlerts.filter(a => !a.read).length > 0 && (
              <span className="ml-auto text-[8px] font-mono font-bold px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                {scanAlerts.filter(a => !a.read).length} NEW
              </span>
            )}
          </div>

          {scanAlerts.length === 0 ? (
            <div className="px-3 py-3 text-[8px] font-mono text-muted-foreground/60">
              No alerts yet. Configure the scanner below.
            </div>
          ) : (
            <div>
              {scanAlerts.slice(0, 5).map(alert => {
                const isLong = alert.direction === "LONG";
                return (
                  <div key={alert.id} className={cn(
                    "px-3 py-2 border-b border-border/40 text-[8px] font-mono",
                    !alert.read && "bg-primary/[0.03]"
                  )}>
                    <div className="flex items-center justify-between mb-0.5">
                      <div className="flex items-center gap-1">
                        <span className={cn(
                          "px-1 py-0.5 rounded font-bold",
                          isLong ? "bg-bull/10 text-bull" : "bg-bear/10 text-bear"
                        )}>
                          {alert.direction}
                        </span>
                        <span className="font-bold text-foreground">{alert.ticker}</span>
                      </div>
                      <span className={cn(
                        "font-bold",
                        alert.confidence >= 80 ? "text-bull" : "text-warn"
                      )}>
                        {Math.round(alert.confidence)}%
                      </span>
                    </div>
                    <div className="text-muted-foreground line-clamp-2 leading-relaxed">{alert.summary}</div>
                    <div className="text-muted-foreground/50 mt-0.5">{timeAgo(alert.created_at)}</div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Scanner config panel */}
          <div className="terminal-header mt-1">
            <Zap className="h-2.5 w-2.5 text-primary" />
            <span className="terminal-label ml-1">SCANNER CONFIG</span>
          </div>
          <ScannerPanel onConfigChange={async () => {
            const token = await getAuthToken();
            if (!token) return;
            fetch(`${API}/api/v1/alerts?limit=10`, { headers: { Authorization: `Bearer ${token}` } })
              .then(r => r.json()).then(setScanAlerts).catch(() => {});
          }} />
        </div>
      </div>
    </div>
  );
}

/* ── Article Card Component ────────────────────────────────────────────────── */

function ArticleCard({ article }: { article: Article }) {
  const catMeta  = CATEGORY_META[article.category];
  const sentMeta = SENTIMENT_META[article.sentiment as keyof typeof SENTIMENT_META] || SENTIMENT_META.NEUTRAL;
  const srcColor = SOURCE_COLORS[article.source] || "text-muted-foreground";
  const SentIcon = sentMeta.icon;

  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block rounded-lg border border-border/60 bg-background hover:border-primary/30 hover:bg-white/[0.02] transition-all duration-200"
    >
      <div className="p-4">
        {/* Top row: category + sentiment + source + time */}
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          {catMeta && (
            <span className={cn(
              "text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border",
              catMeta.color
            )}>
              {catMeta.label.toUpperCase()}
            </span>
          )}
          <div className={cn("flex items-center gap-0.5", sentMeta.color)}>
            <SentIcon className="h-2.5 w-2.5" />
          </div>
          <span className={cn("text-[13px] font-mono font-bold", srcColor)}>
            {article.source.toUpperCase()}
          </span>
          {article.published_at && (
            <span className="text-[13px] font-mono text-muted-foreground ml-auto">
              {timeAgo(article.published_at)}
            </span>
          )}
        </div>

        {/* Headline */}
        <div className="text-[13px] font-medium leading-snug text-foreground/90 group-hover:text-primary transition-colors line-clamp-2 mb-2">
          {article.headline}
        </div>

        {/* Summary */}
        {article.summary && (
          <div className="text-[13px] text-muted-foreground leading-relaxed line-clamp-2 mb-3">
            {article.summary}
          </div>
        )}

        {/* Bottom row: tickers + external link */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {article.tickers.slice(0, 4).map(t => (
            <span key={t} className="text-[8px] font-mono text-primary border border-primary/20 px-1.5 py-0.5 rounded bg-primary/5 font-bold">
              {t}
            </span>
          ))}
          <ExternalLink className="h-2.5 w-2.5 text-muted-foreground/20 group-hover:text-muted-foreground ml-auto shrink-0 transition-colors" />
        </div>
      </div>
    </a>
  );
}

/* ── Sentiment Donut (pure CSS) ────────────────────────────────────────────── */

function SentimentDonut({ positive, neutral, negative }: { positive: number; neutral: number; negative: number }) {
  const total = positive + neutral + negative || 1;
  const posAngle = (positive / total) * 360;
  const neuAngle = (neutral / total) * 360;
  const negAngle = (negative / total) * 360;

  // CSS conic-gradient donut
  const gradient = `conic-gradient(
    hsl(var(--bull)) 0deg ${posAngle}deg,
    hsl(var(--muted-foreground)) ${posAngle}deg ${posAngle + neuAngle}deg,
    hsl(var(--bear)) ${posAngle + neuAngle}deg ${posAngle + neuAngle + negAngle}deg
  )`;

  const dominantPct = Math.round(Math.max(positive, neutral, negative) / total * 100);
  const dominantLabel = positive >= neutral && positive >= negative ? "Bull" : negative >= neutral ? "Bear" : "Flat";

  return (
    <div className="relative h-16 w-16 shrink-0">
      <div
        className="h-full w-full rounded-full"
        style={{ background: gradient }}
      />
      {/* Inner cutout */}
      <div className="absolute inset-[5px] rounded-full bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="text-[13px] font-mono font-bold text-foreground">{dominantPct}%</div>
          <div className="text-[7px] font-mono text-muted-foreground">{dominantLabel}</div>
        </div>
      </div>
    </div>
  );
}
