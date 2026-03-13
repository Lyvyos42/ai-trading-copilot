import Link from "next/link";
import { ArrowRight, Brain, Shield, BarChart2, Zap, TrendingUp, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";

const FEATURES = [
  {
    icon: Brain,
    title: "6 Specialized AI Agents",
    description: "Fundamental, Technical, Sentiment, Macro analysts debate every signal. Final decision by TraderAgent powered by Claude Opus 4.",
  },
  {
    icon: BarChart2,
    title: "80+ Quant Strategies",
    description: "Peer-reviewed strategies from '151 Trading Strategies' (Kakushadze & Serur, 2018) — momentum, mean-reversion, carry, stat-arb, and more.",
  },
  {
    icon: TrendingUp,
    title: "Multi-Asset Coverage",
    description: "Stocks, ETFs, Fixed Income, FX, Commodities, Crypto, Futures across all major global markets.",
  },
  {
    icon: Shield,
    title: "Explainable Signals",
    description: "Full reasoning chain from each agent. See exactly which strategies triggered and why — no black boxes.",
  },
  {
    icon: Activity,
    title: "Real-Time Pipeline",
    description: "LangGraph multi-agent DAG processes signals in <30 seconds. WebSocket stream for live alerts.",
  },
  {
    icon: Zap,
    title: "Kelly Criterion Sizing",
    description: "Risk Manager enforces half-Kelly position sizing, max 15% drawdown circuit breaker, and correlation limits.",
  },
];

const TIERS = [
  {
    name: "Free",
    price: "$0",
    features: ["Paper trading", "3 strategies", "1 asset class", "Delayed data"],
    cta: "Start Free",
    highlight: false,
  },
  {
    name: "Retail",
    price: "$49",
    period: "/mo",
    features: ["All 80+ strategies", "All asset classes", "Real-time data", "100 signals/day"],
    cta: "Get Started",
    highlight: false,
  },
  {
    name: "Pro",
    price: "$199",
    period: "/mo",
    features: ["Custom agent tuning", "API access", "Webhook execution", "Priority support"],
    cta: "Go Pro",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "$499",
    period: "/mo",
    features: ["Dedicated infra", "Custom models", "White-label", "SLA guarantee"],
    cta: "Contact Sales",
    highlight: false,
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative max-w-7xl mx-auto px-4 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/30 bg-primary/5 text-primary text-xs font-medium mb-6">
          <Activity className="h-3 w-3 animate-pulse" />
          6 AI Agents Live — LangGraph + Claude Opus 4
        </div>
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold text-foreground mb-6 leading-tight">
          AI Multi-Agent<br />
          <span className="text-primary">Trading Copilot</span>
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto mb-8">
          80+ peer-reviewed quantitative strategies. 6 specialized AI agents that debate every trade.
          Full reasoning chain. No black boxes.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link href="/dashboard">
            <Button size="lg" className="gap-2 w-full sm:w-auto">
              Launch Dashboard <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="/signals">
            <Button size="lg" variant="outline" className="gap-2 w-full sm:w-auto">
              <Zap className="h-4 w-4" /> Generate Signal
            </Button>
          </Link>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-6 mt-16 max-w-lg mx-auto">
          {[
            { value: "80+", label: "Strategies" },
            { value: "6", label: "AI Agents" },
            { value: "<30s", label: "Per Signal" },
          ].map(({ value, label }) => (
            <div key={label} className="text-center">
              <div className="text-2xl font-bold text-primary font-mono">{value}</div>
              <div className="text-xs text-muted-foreground mt-1">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="max-w-7xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <h2 className="text-2xl font-bold mb-3">Why AI Trading Copilot?</h2>
          <p className="text-muted-foreground">The only platform combining peer-reviewed quant strategies with multi-agent explainable AI.</p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <div key={title} className="p-5 rounded-lg border border-border/50 bg-card hover:border-primary/30 transition-colors">
              <div className="h-8 w-8 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center mb-3">
                <Icon className="h-4 w-4 text-primary" />
              </div>
              <h3 className="font-semibold text-sm mb-2">{title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="max-w-7xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <h2 className="text-2xl font-bold mb-3">Transparent Pricing</h2>
          <p className="text-muted-foreground">Start free with paper trading. Upgrade when you're ready to go live.</p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {TIERS.map(({ name, price, period, features, cta, highlight }) => (
            <div
              key={name}
              className={`p-5 rounded-lg border ${highlight ? "border-primary/50 bg-primary/5" : "border-border/50 bg-card"} relative`}
            >
              {highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-primary text-primary-foreground text-xs rounded-full font-medium">
                  Most Popular
                </div>
              )}
              <div className="mb-4">
                <div className="text-sm text-muted-foreground mb-1">{name}</div>
                <div className="text-3xl font-bold">
                  {price}
                  {period && <span className="text-sm font-normal text-muted-foreground">{period}</span>}
                </div>
              </div>
              <ul className="space-y-2 mb-5">
                {features.map((f) => (
                  <li key={f} className="text-xs text-muted-foreground flex items-center gap-1.5">
                    <div className="h-1 w-1 rounded-full bg-primary shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
              <Link href="/login">
                <Button
                  variant={highlight ? "default" : "outline"}
                  size="sm"
                  className="w-full text-xs"
                >
                  {cta}
                </Button>
              </Link>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
