"use client";
import { useState } from "react";
import { X, Zap, TrendingUp, Crown, Loader2 } from "lucide-react";
import { createCheckout } from "@/lib/api";

interface UpgradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  feature: string;           // e.g. "Unlimited AI Signals"
  requiredTier: "free" | "retail" | "pro";
  reason?: string;           // optional description
}

const TIER_INFO = {
  free: {
    label: "FREE",
    slug: "free",
    price: "$0",
    color: "text-muted-foreground",
    borderColor: "border-border",
    icon: Zap,
    features: ["2 AI signals/day", "Paper trading", "Basic charts", "Market intel"],
  },
  retail: {
    label: "RETAIL",
    slug: "retail",
    price: "$49/mo",
    color: "text-primary",
    borderColor: "border-primary/50",
    icon: TrendingUp,
    features: ["Unlimited signals", "All 80+ strategies", "All asset classes", "Real-time data", "Full backtest"],
  },
  pro: {
    label: "PRO",
    slug: "pro",
    price: "$149/mo",
    color: "text-yellow-400",
    borderColor: "border-yellow-400/50",
    icon: Crown,
    features: ["Everything in Retail", "Custom agent tuning", "API access", "Webhook execution", "Priority support"],
  },
};

export function UpgradeModal({ isOpen, onClose, feature, requiredTier, reason }: UpgradeModalProps) {
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const info = TIER_INFO[requiredTier];
  const Icon = info.icon;

  async function handleUpgrade() {
    if (info.slug === "free") return;
    setLoading(true);
    try {
      const { checkout_url } = await createCheckout(info.slug);
      window.location.href = checkout_url;
    } catch {
      // Fall back to pricing page if checkout fails (e.g. not logged in)
      window.location.href = "/pricing";
    }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-full max-w-md bg-[hsl(0_0%_5%)] border border-border rounded-xl p-6 shadow-2xl">
        {/* Close */}
        <button onClick={onClose} className="absolute top-4 right-4 text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className={`h-9 w-9 rounded-lg border ${info.borderColor} bg-background flex items-center justify-center`}>
            <Icon className={`h-4 w-4 ${info.color}`} />
          </div>
          <div>
            <div className="text-[14px] font-mono text-muted-foreground">UPGRADE REQUIRED</div>
            <div className="font-mono text-sm font-bold text-foreground">{feature}</div>
          </div>
        </div>

        {reason && (
          <p className="text-xs text-muted-foreground mb-4 leading-relaxed">{reason}</p>
        )}

        {/* Plan card */}
        <div className={`p-4 rounded-lg border ${info.borderColor} bg-white/[0.02] mb-4`}>
          <div className="flex items-center justify-between mb-3">
            <span className={`text-xs font-mono font-bold ${info.color}`}>{info.label} PLAN</span>
            <span className={`text-sm font-mono font-bold ${info.color}`}>{info.price}</span>
          </div>
          <ul className="space-y-1.5">
            {info.features.map((f) => (
              <li key={f} className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className={`h-1 w-1 rounded-full ${info.color} bg-current`} />
                {f}
              </li>
            ))}
          </ul>
        </div>

        {/* CTAs */}
        <div className="flex gap-2">
          <a
            href="/pricing"
            className={`flex-1 py-2 rounded-md border ${info.borderColor} ${info.color} text-[13px] font-mono font-bold text-center hover:bg-white/5 transition-colors`}
          >
            SEE ALL PLANS
          </a>
          <button
            onClick={handleUpgrade}
            disabled={loading}
            className="flex-1 py-2 rounded-md bg-primary/10 border border-primary/30 text-primary text-[13px] font-mono font-bold text-center hover:bg-primary/20 transition-colors disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin mx-auto" /> : "UPGRADE NOW"}
          </button>
        </div>

        <p className="text-[14px] text-muted-foreground text-center mt-3">
          Secure checkout powered by Stripe. Questions? <a href="mailto:quantneuraledge@gmail.com" className="text-primary hover:underline">quantneuraledge@gmail.com</a>
        </p>
      </div>
    </div>
  );
}
