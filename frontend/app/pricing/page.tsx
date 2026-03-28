import Link from "next/link";
import { Check, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";

const EMAIL = "quantneuraledge@gmail.com";
const WA_NUMBER = "40770338051"; // WhatsApp number (no + or spaces)

function waLink(tier: string, price: number) {
  const msg = encodeURIComponent(
    `Hi! I'm interested in the AI Trading Copilot ${tier} plan ($${price}/mo). Can you help me get started?`
  );
  return `https://wa.me/${WA_NUMBER}?text=${msg}`;
}

function emailLink(tier: string, price: number) {
  const subject = encodeURIComponent(`AI Trading Copilot — ${tier} Plan`);
  const body = encodeURIComponent(
    `Hi,\n\nI'd like to subscribe to the ${tier} plan ($${price}/mo).\n\nPlease send me payment details.\n\nThank you.`
  );
  return `mailto:${EMAIL}?subject=${subject}&body=${body}`;
}

const TIERS = [
  {
    name: "Free",
    price: 0,
    description: "Explore the platform with demo signals",
    features: [
      "Demo signals (simulated)",
      "Paper trading mode",
      "2 signals / day",
      "1 asset class",
      "Community support",
    ],
    cta: "Start Free",
    href: "/login",
    variant: "outline" as const,
  },
  {
    name: "Retail",
    price: 49,
    description: "Real AI signals for individual traders",
    features: [
      "Real AI signals (9 agents)",
      "All 80+ strategies",
      "All asset classes",
      "Real-time data",
      "3 signals / day",
      "Full reasoning chain",
      "Email support",
    ],
    cta: "Get Started — $49/mo",
    href: waLink("Retail", 49),
    variant: "outline" as const,
  },
  {
    name: "Pro",
    price: 149,
    description: "For serious and semi-pro traders",
    features: [
      "Everything in Retail",
      "10 signals / day",
      "Custom agent tuning",
      "REST API access",
      "Webhook execution",
      "Priority support",
      "Portfolio analytics",
    ],
    cta: "Go Pro — $149/mo",
    href: waLink("Pro", 149),
    highlight: true,
    variant: "default" as const,
  },
  {
    name: "Enterprise",
    price: 499,
    description: "For funds, prop firms, and RIAs",
    features: [
      "Everything in Pro",
      "30 signals / day",
      "Dedicated infrastructure",
      "Custom model fine-tuning",
      "White-label deployment",
      "SLA (99.9% uptime)",
      "Dedicated account manager",
    ],
    cta: "Contact Sales",
    href: emailLink("Enterprise", 499),
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
    a: "80+ strategies from '151 Trading Strategies' (Kakushadze & Serur, 2018) — covering momentum, mean-reversion, carry, statistical arbitrage, sentiment NLP, macro momentum, and more.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes. No long-term contracts. Cancel from your account settings and you'll retain access until your billing period ends.",
  },
];

export default function PricingPage() {
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
        {TIERS.map(({ name, price, description, features, cta, href, highlight, variant }) => (
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
            <Link href={href} target={href.startsWith("http") ? "_blank" : undefined} rel={href.startsWith("http") ? "noopener noreferrer" : undefined}>
              <Button variant={variant} size="sm" className="w-full">
                {cta}
              </Button>
            </Link>
          </div>
        ))}
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
