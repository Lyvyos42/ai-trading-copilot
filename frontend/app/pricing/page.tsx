"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Zap, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { createCheckout, createPortal, getBillingStatus } from "@/lib/api";

const TIERS = [
  {
    name: "Free",
    slug: "free",
    price: 0,
    description: "Real signals from the full analyst pipeline",
    features: [
      "2 signals / day",
      "Consensus Score and reasoning on every signal",
      "Historical Outcome Rate by score band",
      "Community support",
    ],
    cta: "Start Free",
    variant: "outline" as const,
  },
  {
    name: "Retail",
    slug: "retail",
    price: 49,
    description: "More signals for individual traders",
    features: [
      "Signals from the full analyst pipeline",
      "25 built-in rule-based strategies",
      "All asset classes",
      "Real-time data",
      "3 signals / day",
      "Full reasoning chain",
      "Email support",
    ],
    cta: "Get Started — $49/mo",
    variant: "outline" as const,
  },
  {
    name: "Pro",
    slug: "pro",
    price: 149,
    description: "For serious and semi-pro traders",
    features: [
      "Everything in Retail",
      "10 signals / day",
      "Priority support",
    ],
    cta: "Go Pro — $149/mo",
    highlight: true,
    variant: "default" as const,
  },
  {
    name: "Enterprise",
    slug: "enterprise",
    price: 499,
    description: "For funds, prop firms, and RIAs",
    features: [
      "Everything in Pro",
      "30 signals / day",
      "Contact us for custom requirements",
    ],
    cta: "Contact Sales",
    variant: "outline" as const,
  },
];

const FAQ = [
  {
    q: "Is this financial advice?",
    a: "No. AI Trading Copilot provides signals and analysis only. It does not hold customer funds or execute trades. Users connect their own brokerage accounts. This is a software tool, not a financial advisor.",
  },
  {
    q: "How are signals generated?",
    a: "A 9-agent LangGraph pipeline runs: 8 analyst agents work in parallel (Fundamental, Technical, Sentiment, Macro, Order Flow, Regime, Correlation, Quant), then a bull/bear debate, then TraderAgent (Claude Opus 4) synthesizes the final probability signal. RiskManager and 15 hard veto rules validate every output.",
  },
  {
    q: "What strategies are included?",
    a: "25 built-in rule-based strategies - momentum, mean-reversion, session and calendar effects and market structure. The agents' prompts also draw on '151 Trading Strategies' (Kakushadze & Serur, 2018).",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes. No long-term contracts. Cancel from your account settings and you'll retain access until your billing period ends.",
  },
];

export default function PricingPage() {
  const [loading, setLoading] = useState<string | null>(null);

  async function handleSubscribe(tier: string) {
    setLoading(tier);
    try {
      const { checkout_url } = await createCheckout(tier);
      window.location.href = checkout_url;
    } catch (err: any) {
      alert(err.message || "Failed to start checkout. Please log in first.");
      setLoading(null);
    }
  }

  async function handleManage() {
    setLoading("manage");
    try {
      const { portal_url } = await createPortal();
      window.location.href = portal_url;
    } catch (err: any) {
      alert(err.message || "Failed to open billing portal.");
      setLoading(null);
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-12">
      <div className="text-center mb-12">
        <h1 className="text-3xl font-bold mb-3">Simple, Transparent Pricing</h1>
        <p className="text-muted-foreground max-w-lg mx-auto">
          Start with paper trading for free. Upgrade when you want real-time data, more strategies, and API access.
        </p>
      </div>

      {/* Pricing grid */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-16">
        {TIERS.map(({ name, slug, price, description, features, cta, highlight, variant }) => (
          <div
            key={name}
            className={`relative p-6 rounded-xl border flex flex-col ${highlight ? "border-primary/50 bg-primary/5 shadow-lg shadow-primary/10" : "border-border/50 bg-card"}`}
          >
            {highlight && (
              <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 flex items-center gap-1 px-3 py-1 bg-primary text-primary-foreground text-xs rounded-full font-medium">
                <Zap className="h-3 w-3" /> Most Popular
              </div>
            )}
            <div className="mb-5">
              <h2 className="font-bold text-lg mb-1">{name}</h2>
              <p className="text-xs text-muted-foreground mb-3">{description}</p>
              <div className="flex items-baseline gap-1">
                <span className="text-3xl font-bold">${price}</span>
                {price > 0 && <span className="text-sm text-muted-foreground">/mo</span>}
              </div>
            </div>
            <ul className="space-y-2 mb-6 flex-1">
              {features.map((f) => (
                <li key={f} className="flex items-start gap-2 text-xs">
                  <Check className="h-3.5 w-3.5 text-bull shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            {slug === "free" ? (
              <Link href="/login">
                <Button variant={variant} size="sm" className="w-full">
                  {cta}
                </Button>
              </Link>
            ) : (
              <Button
                variant={variant}
                size="sm"
                className="w-full"
                disabled={loading !== null}
                onClick={() => handleSubscribe(slug)}
              >
                {loading === slug ? (
                  <><Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> Redirecting...</>
                ) : (
                  cta
                )}
              </Button>
            )}
          </div>
        ))}
      </div>

      {/* Manage subscription */}
      <div className="text-center mb-16">
        <p className="text-sm text-muted-foreground mb-2">Already subscribed?</p>
        <Button variant="ghost" size="sm" onClick={handleManage} disabled={loading === "manage"}>
          {loading === "manage" ? (
            <><Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> Opening portal...</>
          ) : (
            "Manage Subscription"
          )}
        </Button>
      </div>

      {/* FAQ */}
      <div className="max-w-2xl mx-auto">
        <h2 className="text-xl font-bold mb-6 text-center">Frequently Asked Questions</h2>
        <div className="space-y-4">
          {FAQ.map(({ q, a }) => (
            <div key={q} className="p-4 rounded-lg border border-border/50 bg-card">
              <h3 className="font-semibold text-sm mb-2">{q}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{a}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
