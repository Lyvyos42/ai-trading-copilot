import Link from "next/link";
import { IconSignal, IconArrowRight, IconShield, IconTrendUp, IconAgents, IconBacktest, IconTerminal, GeoOctahedron, GeoCylinder, GeoCube, GeoSphere, GeoIcosahedron, GeoTorus, GeoPrism, GeoDodecahedron, GeoTetrahedron, GeoDiamond } from "@/components/icons/GeoIcons";

// ─── Data ────────────────────────────────────────────────────────────────────

const AGENTS = [
  { name: "Fundamental",    geo: GeoOctahedron,    color: "#D4A240", model: "sonnet-4-6" },
  { name: "Technical",      geo: GeoCylinder,       color: "#f59e0b", model: "sonnet-4-6" },
  { name: "Sentiment",      geo: GeoSphere,         color: "#7c3aed", model: "sonnet-4-6" },
  { name: "Macro",          geo: GeoIcosahedron,    color: "#06b6d4", model: "sonnet-4-6" },
  { name: "Order Flow",     geo: GeoPrism,          color: "#ec4899", model: "sonnet-4-6" },
  { name: "Regime",         geo: GeoDodecahedron,   color: "#8b5cf6", model: "sonnet-4-6" },
  { name: "Correlation",    geo: GeoTetrahedron,    color: "#14b8a6", model: "sonnet-4-6" },
  { name: "Quant",          geo: GeoDiamond,        color: "#3b82f6", model: "sonnet-4-6" },
  { name: "Risk",           geo: GeoTorus,          color: "#f97316", model: "sonnet-4-6" },
  { name: "Trader",         geo: GeoCube,           color: "#22c55e", model: "opus-4-6" },
];

const FEATURES = [
  {
    icon: IconAgents,
    title: "9 Specialized AI Agents",
    description: "Fundamental, Technical, Sentiment, Macro, Order Flow, Regime, Correlation, Quant analysts debate every signal. Final decision by TraderAgent powered by Claude Opus.",
  },
  {
    icon: IconBacktest,
    title: "80+ Quant Strategies",
    description: "Peer-reviewed strategies from Kakushadze & Serur 2018 — momentum, mean-reversion, carry, stat-arb, and more.",
  },
  {
    icon: IconTrendUp,
    title: "Multi-Asset Coverage",
    description: "Stocks, ETFs, Fixed Income, FX, Commodities, Crypto, Futures across all major global markets.",
  },
  {
    icon: IconTerminal,
    title: "Explainable Signals",
    description: "Full reasoning chain from each agent. See exactly which strategies triggered and why — no black boxes.",
  },
  {
    icon: IconSignal,
    title: "Real-Time Pipeline",
    description: "LangGraph multi-agent DAG processes signals in under 30 seconds. WebSocket stream for live alerts.",
  },
  {
    icon: IconShield,
    title: "Kelly Criterion Sizing",
    description: "Risk Manager enforces half-Kelly position sizing, max 15% drawdown circuit breaker, and correlation limits.",
  },
];

const TIERS = [
  {
    name: "Free",
    price: "$0",
    period: null,
    features: ["Paper trading", "2 signals / day", "1 asset class", "Delayed data"],
    cta: "Start Free",
    highlight: false,
    color: "hsl(var(--muted-foreground))",
  },
  {
    name: "Retail",
    price: "$49",
    period: "/mo",
    features: ["All 80+ strategies", "All asset classes", "Real-time data", "100 signals / day"],
    cta: "Get Started",
    highlight: false,
    color: "hsl(var(--primary))",
  },
  {
    name: "Pro",
    price: "$149",
    period: "/mo",
    features: ["Custom agent tuning", "API access", "Webhook execution", "Priority support"],
    cta: "Go Pro",
    highlight: true,
    color: "hsl(var(--bull))",
  },
  {
    name: "Enterprise",
    price: "$499",
    period: "/mo",
    features: ["Dedicated infra", "Custom models", "White-label option", "SLA guarantee"],
    cta: "Contact Sales",
    highlight: false,
    color: "#f59e0b",
    href: "mailto:quantneuraledge@gmail.com?subject=Enterprise%20Plan%20Inquiry",
  },
];

const STATS = [
  { value: "80+",   label: "Strategies" },
  { value: "9",     label: "AI Agents" },
  { value: "<30s",  label: "Per Signal" },
  { value: "8",     label: "Asset Classes" },
];

// ─── Component ───────────────────────────────────────────────────────────────

export default function HomePage() {
  return (
    <div
      className="min-h-screen"
      style={{ background: "hsl(var(--surface-0))" }}
    >

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="relative max-w-7xl mx-auto px-6 pt-20 pb-20">

        {/* Spatial background — grid of faint lines suggesting depth */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: `
              linear-gradient(hsl(0 0% 15% / 0.15) 1px, transparent 1px),
              linear-gradient(90deg, hsl(0 0% 15% / 0.15) 1px, transparent 1px)
            `,
            backgroundSize: "60px 60px",
            maskImage: "radial-gradient(ellipse 80% 70% at 50% 50%, black 20%, transparent 100%)",
          }}
        />

        {/* Status badge */}
        <div className="flex justify-center mb-8">
          <div
            className="inline-flex items-center gap-2 px-3 py-1.5"
            style={{
              border: "1px solid hsl(var(--primary) / 0.25)",
              borderRadius: "2px",
              background: "hsl(var(--primary) / 0.04)",
            }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: "hsl(var(--bull))", animation: "pulse-live 1.6s ease-in-out infinite" }}
            />
            <span
              className="text-[13px] font-bold tracking-[0.12em]"
              style={{
                fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                color: "hsl(var(--primary))",
              }}
            >
              9 AI AGENTS LIVE — LANGGRAPH + CLAUDE OPUS 4
            </span>
          </div>
        </div>

        {/* Hero text */}
        <div className="text-center max-w-3xl mx-auto mb-10 relative">
          <h1
            className="font-bold mb-5"
            style={{
              fontSize: "clamp(32px, 5vw, 52px)",
              lineHeight: 1.1,
              letterSpacing: "-0.04em",
              color: "hsl(var(--foreground))",
            }}
          >
            AI Multi-Agent
            <br />
            <span style={{ color: "hsl(var(--primary))" }}>Trading Copilot</span>
          </h1>
          <p
            className="text-base leading-relaxed max-w-xl mx-auto"
            style={{ color: "hsl(var(--muted-foreground))" }}
          >
            80+ peer-reviewed quantitative strategies. 9 specialized AI agents that debate every trade.
            Full reasoning chain. No black boxes.
          </p>
        </div>

        {/* CTA buttons */}
        <div className="flex flex-col sm:flex-row gap-2.5 justify-center mb-16">
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center gap-2 px-6 py-2.5 transition-all"
            style={{
              background: "hsl(var(--primary))",
              border: "1px solid hsl(var(--primary))",
              borderRadius: "2px",
              color: "hsl(0 0% 98%)",
              fontSize: "11px",
              fontWeight: 700,
              fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            <IconTerminal size={13} color="currentColor" />
            LAUNCH TERMINAL
            <IconArrowRight size={13} color="currentColor" />
          </Link>
          <Link
            href="/signals"
            className="inline-flex items-center justify-center gap-2 px-6 py-2.5 transition-all"
            style={{
              background: "transparent",
              border: "1px solid hsl(var(--border-strong))",
              borderRadius: "2px",
              color: "hsl(var(--foreground))",
              fontSize: "11px",
              fontWeight: 700,
              fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            <IconSignal size={13} color="currentColor" />
            GENERATE SIGNAL
          </Link>
        </div>

        {/* Agent geometry display — 6 rotating 3D shapes */}
        <div className="flex items-center justify-center gap-4 flex-wrap mb-16">
          {AGENTS.map((agent) => {
            const GeoComp = agent.geo;
            return (
              <div key={agent.name} className="flex flex-col items-center gap-2">
                <div
                  className="flex items-center justify-center"
                  style={{
                    width: 60,
                    height: 60,
                    background: `${agent.color}08`,
                    border: `1px solid ${agent.color}20`,
                    borderRadius: "3px",
                    /* Ambient occlusion */
                    boxShadow: `inset 0 -2px 4px ${agent.color}10, inset 0 1px 0 ${agent.color}18`,
                  }}
                >
                  <div style={{ animation: `rotate-idle-${agent.name === "Fundamental" ? "octahedron" : agent.name === "Technical" ? "cylinder" : agent.name === "Sentiment" ? "sphere" : agent.name === "Macro" ? "icosahedron" : agent.name === "Risk" ? "torus" : "cube"} ${agent.name === "Risk" ? "8s" : agent.name === "Technical" ? "10s" : agent.name === "Fundamental" ? "14s" : agent.name === "Sentiment" ? "16s" : agent.name === "Macro" ? "18s" : "12s"} linear infinite`, transformStyle: "preserve-3d" }}>
                    <GeoComp size={38} color={agent.color} strokeWidth={1.1} />
                  </div>
                </div>
                <div className="flex flex-col items-center gap-0.5">
                  <span
                    className="text-[13px] font-bold tracking-[0.08em]"
                    style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: agent.color }}
                  >
                    {agent.name.toUpperCase()}
                  </span>
                  <span
                    className="text-[8px]"
                    style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--muted-foreground) / 0.6)" }}
                  >
                    {agent.model}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Stats row */}
        <div
          className="grid grid-cols-2 md:grid-cols-4 gap-px max-w-2xl mx-auto"
          style={{
            background: "hsl(var(--border))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "2px",
            overflow: "hidden",
          }}
        >
          {STATS.map(({ value, label }) => (
            <div
              key={label}
              className="flex flex-col items-center justify-center py-4 px-2"
              style={{ background: "hsl(var(--surface-1))" }}
            >
              <div
                className="text-2xl font-bold mb-0.5"
                style={{
                  fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                  color: "hsl(var(--primary))",
                  letterSpacing: "-0.02em",
                }}
              >
                {value}
              </div>
              <div className="terminal-label">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Features ───────────────────────────────────────────────────────── */}
      <section
        className="max-w-7xl mx-auto px-6 py-20"
        style={{ borderTop: "1px solid hsl(var(--border))" }}
      >
        <div className="mb-12">
          <p
            className="text-[13px] font-bold tracking-[0.18em] mb-3"
            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--primary))" }}
          >
            CAPABILITIES
          </p>
          <h2
            className="font-bold max-w-lg"
            style={{ fontSize: "clamp(20px, 2.5vw, 28px)", letterSpacing: "-0.025em", color: "hsl(var(--foreground))" }}
          >
            9-agent pipeline combining peer-reviewed quant strategies with explainable AI consensus.
          </h2>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px"
          style={{
            background: "hsl(var(--border))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "2px",
            overflow: "hidden",
          }}
        >
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="p-5 group transition-colors feature-card"
            >
              <div
                className="h-8 w-8 flex items-center justify-center mb-3"
                style={{
                  background: "hsl(var(--primary) / 0.08)",
                  border: "1px solid hsl(var(--primary) / 0.2)",
                  borderRadius: "2px",
                  boxShadow: "inset 0 1px 0 hsl(var(--primary) / 0.15)",
                }}
              >
                <Icon size={14} color="hsl(var(--primary))" strokeWidth={1.5} />
              </div>
              <h3
                className="font-semibold mb-1.5"
                style={{ fontSize: "13px", color: "hsl(var(--foreground))" }}
              >
                {title}
              </h3>
              <p
                className="text-[13px] leading-relaxed"
                style={{ color: "hsl(var(--muted-foreground))" }}
              >
                {description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Pricing ────────────────────────────────────────────────────────── */}
      <section
        className="max-w-7xl mx-auto px-6 py-20"
        style={{ borderTop: "1px solid hsl(var(--border))" }}
      >
        <div className="mb-12">
          <p
            className="text-[13px] font-bold tracking-[0.18em] mb-3"
            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--primary))" }}
          >
            PRICING
          </p>
          <h2
            className="font-bold"
            style={{ fontSize: "clamp(20px, 2.5vw, 28px)", letterSpacing: "-0.025em", color: "hsl(var(--foreground))" }}
          >
            Start free. Upgrade when you are ready.
          </h2>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {TIERS.map(({ name, price, period, features, cta, highlight, color, ...rest }: any) => (
            <div
              key={name}
              className="panel panel-ao relative flex flex-col"
              style={{
                borderColor: highlight ? "hsl(var(--bull) / 0.35)" : undefined,
                background: highlight ? "hsl(var(--surface-2))" : undefined,
              }}
            >
              {highlight && (
                <div
                  className="absolute top-0 left-0 right-0 h-px"
                  style={{
                    background: "linear-gradient(90deg, transparent, hsl(var(--bull) / 0.7) 50%, transparent)",
                    zIndex: 2,
                  }}
                />
              )}

              {highlight && (
                <div
                  className="absolute -top-3 left-1/2 -translate-x-1/2 px-2.5 py-0.5 text-[8px] font-bold tracking-[0.1em]"
                  style={{
                    fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                    background: "hsl(var(--bull))",
                    color: "hsl(0 0% 5%)",
                    borderRadius: "2px",
                  }}
                >
                  MOST POPULAR
                </div>
              )}

              <div className="p-5 flex-1">
                <div className="mb-4">
                  <div
                    className="text-[13px] font-bold tracking-[0.12em] mb-2"
                    style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color }}
                  >
                    {name.toUpperCase()}
                  </div>
                  <div className="flex items-baseline gap-0.5">
                    <span
                      className="text-3xl font-bold"
                      style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", letterSpacing: "-0.03em", color: "hsl(var(--foreground))" }}
                    >
                      {price}
                    </span>
                    {period && (
                      <span
                        className="text-[13px]"
                        style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--muted-foreground))" }}
                      >
                        {period}
                      </span>
                    )}
                  </div>
                </div>

                <ul className="space-y-2 mb-5">
                  {features.map((f: string) => (
                    <li
                      key={f}
                      className="flex items-center gap-2 text-[13px]"
                      style={{ color: "hsl(var(--muted-foreground))" }}
                    >
                      {/* Geometric bullet — small square, not a circle */}
                      <div
                        className="h-1 w-1 shrink-0"
                        style={{ background: color, borderRadius: "0.5px" }}
                      />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="px-5 pb-5">
                <Link
                  href={rest.href || (name === "Free" ? "/login" : "/pricing")}
                  className="flex items-center justify-center gap-1.5 w-full py-2 transition-all text-[14px] font-bold tracking-[0.08em] uppercase"
                  style={{
                    fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                    border: `1px solid ${highlight ? "hsl(var(--bull))" : "hsl(var(--border-strong))"}`,
                    borderRadius: "2px",
                    background: highlight ? "hsl(var(--bull))" : "transparent",
                    color: highlight ? "hsl(0 0% 5%)" : "hsl(var(--foreground))",
                  }}
                >
                  {cta}
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>

    </div>
  );
}
