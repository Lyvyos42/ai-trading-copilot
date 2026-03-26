import Link from "next/link";
import { IconSignal, IconArrowRight, IconShield, IconTrendUp, IconAgents, IconBacktest, IconTerminal } from "@/components/icons/GeoIcons";

const SECTIONS = [
  {
    icon: IconTerminal,
    title: "Dashboard",
    href: "/dashboard",
    description: "Your central hub. View watchlist tickers with live price data, a quick-glance signal feed, portfolio summary, and market overview. Add or remove tickers from your watchlist to customize your monitoring.",
    features: [
      "Watchlist with real-time price indicators",
      "Latest signal feed with probability scores",
      "Portfolio equity snapshot",
      "Quick-access navigation to all tools",
    ],
  },
  {
    icon: IconSignal,
    title: "Signal Generation",
    href: "/signals",
    description: "The core intelligence engine. Enter any ticker and timeframe to run a full 9-agent analysis pipeline. Each agent (Fundamental, Technical, Sentiment, Macro, Order Flow, Regime, Correlation, Quant, Risk Manager) independently evaluates the asset before the Trader agent produces a probability-based consensus.",
    features: [
      "Probability score (0-100) instead of simple BUY/SELL",
      "Research target and invalidation level",
      "Risk/Reward ratio calculation",
      "Bull case and bear case narratives from each agent",
      "Full reasoning chain — no black boxes",
      "Pipeline progress visualization in real-time",
    ],
  },
  {
    icon: IconAgents,
    title: "AI Agents",
    href: "/agents",
    description: "Meet the 9 specialized AI agents + Risk Gate powering every signal. View each agent's role, methodology, latency, accuracy, and current status. Includes Order Flow, Regime Change, Correlation, and Quant analysts alongside the core four.",
    features: [
      "9 analyst agents + Trader + Risk Gate (11 total components)",
      "Powered by Claude Opus 4 (Trader) and Claude Sonnet 4 (Analysts)",
      "LangGraph multi-agent DAG architecture with parallel execution",
      "Each agent has unique 3D geometry, latency trace, and strategy tags",
    ],
  },
  {
    icon: IconBacktest,
    title: "Backtest Engine",
    href: "/backtest",
    description: "Validate strategies against historical data before risking capital. Select a ticker, date range, and strategy, then view the equity curve, trade log, and performance metrics.",
    features: [
      "80+ peer-reviewed quantitative strategies",
      "Equity curve visualization",
      "Sharpe ratio, max drawdown, and win rate metrics",
      "Strategies from Kakushadze & Serur (2018)",
    ],
  },
  {
    icon: IconTrendUp,
    title: "Performance",
    href: "/performance",
    description: "Track your signal accuracy and portfolio performance over time. View historical signal outcomes, hit rates by asset class, and cumulative PnL charts.",
    features: [
      "Signal accuracy tracking by timeframe",
      "Performance breakdown by asset class",
      "Cumulative PnL visualization",
      "Historical signal outcome log",
    ],
  },
  {
    icon: IconShield,
    title: "Portfolio",
    href: "/portfolio",
    description: "Paper trading portfolio with virtual $100,000 starting balance. Track open positions, realized PnL, and equity curve. Practice trade execution without real capital at risk.",
    features: [
      "Virtual portfolio with $100K starting balance",
      "Open position tracking with live PnL",
      "Trade history and execution log",
      "Equity curve over time",
    ],
  },
  {
    icon: IconSignal,
    title: "Correlation Map",
    href: "/correlation",
    description: "Visual heatmap showing correlation coefficients between assets in your watchlist. Identify diversification opportunities and avoid overconcentration in correlated positions.",
    features: [
      "Interactive correlation heatmap",
      "Color-coded from negative (blue) to positive (red)",
      "Covers all asset classes in your watchlist",
      "Helps optimize portfolio diversification",
    ],
  },
  {
    icon: IconTerminal,
    title: "Economic Calendar",
    href: "/calendar",
    description: "Upcoming economic events with impact ratings. View scheduled releases like NFP, CPI, FOMC decisions, and earnings dates. Previous values and forecast consensus included.",
    features: [
      "High, medium, and low impact event filtering",
      "Previous value and forecast consensus",
      "Covers all major global economies",
      "Helps time entries around volatility events",
    ],
  },
  {
    icon: IconTerminal,
    title: "Trading Journal",
    href: "/journal",
    description: "Record your trades, notes, and lessons learned. Build a personal trading log to review your decision-making over time and identify patterns in your behavior.",
    features: [
      "Add journal entries with tags",
      "Link entries to specific signals",
      "Search and filter past entries",
      "Build a personal trading knowledge base",
    ],
  },
  {
    icon: IconTerminal,
    title: "News Intelligence",
    href: "/news",
    description: "Aggregated market news from major financial sources. Headlines are analyzed by the Sentiment agent and integrated into signal generation for real-time context.",
    features: [
      "Aggregated headlines from Reuters, CNBC, WSJ",
      "Sentiment scoring per headline",
      "Ticker-specific news filtering",
      "Integrated into the signal generation pipeline",
    ],
  },
];

export default function GuidePage() {
  return (
    <div
      className="min-h-screen"
      style={{ background: "hsl(var(--surface-0))" }}
    >
      {/* Header */}
      <section className="max-w-5xl mx-auto px-6 pt-16 pb-12">
        <p
          className="text-[9px] font-bold tracking-[0.18em] mb-3"
          style={{
            fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
            color: "hsl(var(--primary))",
          }}
        >
          DOCUMENTATION
        </p>
        <h1
          className="font-bold mb-4"
          style={{
            fontSize: "clamp(24px, 4vw, 36px)",
            letterSpacing: "-0.03em",
            color: "hsl(var(--foreground))",
          }}
        >
          Platform Guide
        </h1>
        <p
          className="text-sm leading-relaxed max-w-2xl"
          style={{ color: "hsl(var(--muted-foreground))" }}
        >
          A complete overview of every feature in the AI Trading Copilot. Learn
          how each tool works and how to get the most out of the platform.
        </p>
      </section>

      {/* Quick nav */}
      <section className="max-w-5xl mx-auto px-6 pb-10">
        <div
          className="flex flex-wrap gap-2"
        >
          {SECTIONS.map(({ title, href }) => (
            <a
              key={href}
              href={`#${title.toLowerCase().replace(/ /g, "-")}`}
              className="text-[10px] font-bold tracking-[0.06em] uppercase px-3 py-1.5 transition-colors"
              style={{
                fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                border: "1px solid hsl(var(--border))",
                borderRadius: "2px",
                color: "hsl(var(--muted-foreground))",
                background: "hsl(var(--surface-1))",
              }}
            >
              {title}
            </a>
          ))}
        </div>
      </section>

      {/* Sections */}
      <section className="max-w-5xl mx-auto px-6 pb-20">
        <div className="space-y-6">
          {SECTIONS.map(({ icon: Icon, title, href, description, features }) => (
            <div
              key={title}
              id={title.toLowerCase().replace(/ /g, "-")}
              className="panel panel-ao"
              style={{ scrollMarginTop: "90px" }}
            >
              <div className="p-5 sm:p-6">
                {/* Title row */}
                <div className="flex items-start gap-3 mb-4">
                  <div
                    className="h-8 w-8 flex items-center justify-center shrink-0 mt-0.5"
                    style={{
                      background: "hsl(var(--primary) / 0.08)",
                      border: "1px solid hsl(var(--primary) / 0.2)",
                      borderRadius: "2px",
                      boxShadow:
                        "inset 0 1px 0 hsl(var(--primary) / 0.15)",
                    }}
                  >
                    <Icon
                      size={14}
                      color="hsl(var(--primary))"
                      strokeWidth={1.5}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                      <h2
                        className="font-bold"
                        style={{
                          fontSize: "15px",
                          color: "hsl(var(--foreground))",
                          letterSpacing: "-0.02em",
                        }}
                      >
                        {title}
                      </h2>
                      <Link
                        href={href}
                        className="inline-flex items-center gap-1 text-[9px] font-bold tracking-[0.08em] uppercase transition-colors"
                        style={{
                          fontFamily:
                            "'BerkeleyMono', 'IBM Plex Mono', monospace",
                          color: "hsl(var(--primary))",
                          padding: "2px 8px",
                          border: "1px solid hsl(var(--primary) / 0.25)",
                          borderRadius: "2px",
                        }}
                      >
                        OPEN
                        <IconArrowRight size={9} color="currentColor" />
                      </Link>
                    </div>
                  </div>
                </div>

                {/* Description */}
                <p
                  className="text-[12px] leading-relaxed mb-4"
                  style={{ color: "hsl(var(--muted-foreground))" }}
                >
                  {description}
                </p>

                {/* Feature list */}
                <ul className="grid sm:grid-cols-2 gap-x-4 gap-y-1.5">
                  {features.map((f) => (
                    <li
                      key={f}
                      className="flex items-start gap-2 text-[11px]"
                      style={{ color: "hsl(var(--muted-foreground))" }}
                    >
                      <div
                        className="h-1 w-1 shrink-0 mt-1.5"
                        style={{
                          background: "hsl(var(--primary))",
                          borderRadius: "0.5px",
                        }}
                      />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Disclaimer */}
      <section
        className="max-w-5xl mx-auto px-6 pb-16"
        style={{ borderTop: "1px solid hsl(var(--border))" }}
      >
        <div className="pt-8">
          <p
            className="text-[10px] leading-relaxed max-w-2xl"
            style={{ color: "hsl(var(--muted-foreground) / 0.6)" }}
          >
            AI Trading Copilot is an analysis and decision-support tool. It does
            not constitute financial advice. All signals are generated by AI
            models and should be validated by your own analysis. Paper trading is
            for educational purposes. Trading financial markets carries
            substantial risk of loss.
          </p>
        </div>
      </section>
    </div>
  );
}
