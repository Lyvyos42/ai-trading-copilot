"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw, ExternalLink, Globe, TrendingUp, TrendingDown, Minus, AlertTriangle, DollarSign, Zap, Building2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { timeAgo } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

const CATEGORIES = ["ALL", "MARKETS", "MACRO", "EARNINGS", "FED", "GEOPOLITICAL", "CRISIS"] as const;

const CATEGORY_META: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; color: string }> = {
  MARKETS:      { label: "Markets",      icon: TrendingUp,     color: "text-primary border-primary/30 bg-primary/5" },
  MACRO:        { label: "Macro",        icon: Globe,          color: "text-info border-info/30 bg-info/5" },
  EARNINGS:     { label: "Earnings",     icon: DollarSign,     color: "text-bull border-bull/30 bg-bull/5" },
  FED:          { label: "Fed",          icon: Building2,      color: "text-warn border-warn/30 bg-warn/5" },
  GEOPOLITICAL: { label: "Geopolitical", icon: Globe,          color: "text-bear border-bear/30 bg-bear/5" },
  CRISIS:       { label: "Crisis",       icon: AlertTriangle,  color: "text-bear border-bear/50 bg-bear/10" },
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

  const loadNews = useCallback(async (category: string) => {
    setFetchError(null);
    try {
      const params = category !== "ALL" ? `?category=${category}&limit=100` : "?limit=100";
      const [artRes, sumRes] = await Promise.all([
        fetch(`${API}/api/v1/news${params}`),
        fetch(`${API}/api/v1/news/summary`),
      ]);
      if (artRes.ok) {
        const data = await artRes.json();
        setArticles(data);
      } else {
        setFetchError(`News feed returned ${artRes.status}`);
      }
      if (sumRes.ok) setSummary(await sumRes.json());
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : "Failed to reach backend");
    }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { setLoading(true); loadNews(activeCategory); }, [activeCategory, loadNews]);

  // Auto-refresh every 60s
  useEffect(() => {
    const id = setInterval(() => loadNews(activeCategory), 60_000);
    return () => clearInterval(id);
  }, [activeCategory, loadNews]);

  async function handleRefresh() {
    setRefreshing(true);
    await fetch(`${API}/api/v1/news/refresh`, { method: "POST" });
    // Scraper fetches 16 feeds concurrently — retry at 6s, 12s, 20s, 30s
    [6000, 12000, 20000, 30000].forEach((delay) => {
      setTimeout(() => loadNews(activeCategory), delay);
    });
    setTimeout(() => setRefreshing(false), 32000);
  }

  const crisisArticles  = articles.filter(a => a.category === "CRISIS");
  const normalArticles  = articles.filter(a => a.category !== "CRISIS");

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
            <span className="text-[9px] font-mono text-muted-foreground">
              {summary.total.toLocaleString()} articles
            </span>
            {summary.last_scraped && (
              <span className="text-[9px] font-mono text-muted-foreground">
                last update {timeAgo(summary.last_scraped)}
              </span>
            )}
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 text-[9px] font-mono font-bold px-2.5 py-1 rounded border border-primary/30 text-primary hover:bg-primary/10 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={cn("h-2.5 w-2.5", refreshing && "animate-spin")} />
            {refreshing ? "SCRAPING…" : "REFRESH"}
          </button>
        </div>
      </div>

      {/* ── CRISIS BANNER (only when crisis articles exist) ─────────── */}
      {crisisArticles.length > 0 && (
        <div className="flex items-center gap-3 px-4 py-2 bg-bear/10 border-b border-bear/30 shrink-0">
          <AlertTriangle className="h-3.5 w-3.5 text-bear shrink-0" />
          <span className="text-[10px] font-mono font-bold text-bear tracking-widest">ALERT</span>
          <span className="text-[10px] font-mono text-bear/80 truncate">
            {crisisArticles[0].headline}
          </span>
          <a
            href={crisisArticles[0].url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto text-[9px] font-mono text-bear hover:text-bear/70 flex items-center gap-1 shrink-0"
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
                "flex items-center gap-1.5 px-4 py-2.5 text-[10px] font-mono font-bold tracking-widest whitespace-nowrap border-b-2 transition-colors",
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

        {/* Article feed */}
        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center h-40">
              <div className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
                <span className="h-3 w-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
                LOADING INTEL FEED…
              </div>
            </div>
          )}

          {!loading && fetchError && (
            <div className="mx-4 mt-4 px-3 py-2 text-xs font-mono text-bear bg-bear/10 border border-bear/20">
              ERR — {fetchError}
            </div>
          )}

          {!loading && !fetchError && articles.length === 0 && (
            <div className="flex flex-col items-center justify-center h-60 gap-3">
              <Globe className="h-8 w-8 text-muted-foreground/20" />
              <div className="text-[10px] font-mono text-muted-foreground text-center">
                NO ARTICLES YET<br />
                <span className="text-[9px]">Click REFRESH to trigger the first scrape</span>
              </div>
            </div>
          )}

          {!loading && normalArticles.map((article, i) => (
            <ArticleRow key={article.id} article={article} index={i} />
          ))}
        </div>

        {/* RIGHT SIDEBAR — Source stats */}
        <div className="w-56 shrink-0 border-l border-border overflow-y-auto">
          <div className="terminal-header">
            <span className="terminal-label">SOURCES</span>
          </div>

          {summary?.categories.map(cat => {
            const meta = CATEGORY_META[cat.category];
            if (!meta) return null;
            const Icon = meta.icon;
            return (
              <button
                key={cat.category}
                onClick={() => setActive(cat.category)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2.5 border-b border-border/50 hover:bg-white/[0.02] transition-colors",
                  activeCategory === cat.category && "bg-primary/5"
                )}
              >
                <div className="flex items-center gap-2">
                  <Icon className={cn("h-3 w-3", meta.color.split(" ")[0])} />
                  <span className="text-[10px] font-mono font-bold text-foreground">{meta.label}</span>
                </div>
                <span className="text-[10px] font-mono text-muted-foreground">{cat.count}</span>
              </button>
            );
          })}

          <div className="terminal-header mt-2">
            <span className="terminal-label">SENTIMENT MIX</span>
          </div>
          <SentimentBar articles={articles} />
        </div>
      </div>
    </div>
  );
}

function ArticleRow({ article, index }: { article: Article; index: number }) {
  const catMeta  = CATEGORY_META[article.category];
  const sentMeta = SENTIMENT_META[article.sentiment as keyof typeof SENTIMENT_META] || SENTIMENT_META.NEUTRAL;
  const srcColor = SOURCE_COLORS[article.source] || "text-muted-foreground";
  const SentIcon = sentMeta.icon;

  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "block border-b border-border/50 px-4 py-3 hover:bg-white/[0.025] transition-colors group",
        index === 0 && "bg-white/[0.015]"
      )}
    >
      <div className="flex items-start gap-3">
        {/* Sentiment indicator */}
        <div className={cn("mt-0.5 shrink-0", sentMeta.color)}>
          <SentIcon className="h-3.5 w-3.5" />
        </div>

        <div className="flex-1 min-w-0">
          {/* Category + Source + Time */}
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            {catMeta && (
              <span className={cn(
                "text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border",
                catMeta.color
              )}>
                {catMeta.label.toUpperCase()}
              </span>
            )}
            <span className={cn("text-[9px] font-mono font-bold", srcColor)}>
              {article.source.toUpperCase()}
            </span>
            {article.published_at && (
              <span className="text-[9px] font-mono text-muted-foreground">
                {timeAgo(article.published_at)}
              </span>
            )}
            {article.tickers.length > 0 && article.tickers.slice(0, 3).map(t => (
              <span key={t} className="text-[8px] font-mono text-primary border border-primary/20 px-1 rounded bg-primary/5">
                {t}
              </span>
            ))}
          </div>

          {/* Headline */}
          <div className={cn(
            "text-sm font-medium leading-snug group-hover:text-primary transition-colors",
            index === 0 ? "text-foreground" : "text-foreground/90"
          )}>
            {article.headline}
          </div>

          {/* Summary */}
          {article.summary && (
            <div className="text-[11px] text-muted-foreground mt-1 leading-relaxed line-clamp-2">
              {article.summary}
            </div>
          )}
        </div>

        <ExternalLink className="h-3 w-3 text-muted-foreground/30 group-hover:text-muted-foreground shrink-0 mt-0.5 transition-colors" />
      </div>
    </a>
  );
}

function SentimentBar({ articles }: { articles: Article[] }) {
  if (!articles.length) return null;
  const pos = articles.filter(a => a.sentiment === "POSITIVE").length;
  const neg = articles.filter(a => a.sentiment === "NEGATIVE").length;
  const neu = articles.filter(a => a.sentiment === "NEUTRAL").length;
  const total = articles.length;

  return (
    <div className="px-3 py-3 space-y-2">
      {[
        { label: "BULLISH", count: pos, color: "bg-bull", textColor: "text-bull" },
        { label: "NEUTRAL", count: neu, color: "bg-muted-foreground", textColor: "text-muted-foreground" },
        { label: "BEARISH", count: neg, color: "bg-bear", textColor: "text-bear" },
      ].map(({ label, count, color, textColor }) => (
        <div key={label}>
          <div className="flex justify-between mb-1">
            <span className={cn("text-[9px] font-mono font-bold", textColor)}>{label}</span>
            <span className="text-[9px] font-mono text-muted-foreground">
              {total > 0 ? Math.round(count / total * 100) : 0}%
            </span>
          </div>
          <div className="h-1 bg-muted rounded overflow-hidden">
            <div
              className={cn("h-full rounded", color)}
              style={{ width: total > 0 ? `${count / total * 100}%` : "0%" }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
