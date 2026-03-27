"use client";
import { useState, useEffect, useCallback } from "react";
import { getMemories, deleteMemory, getMemoryStats, getMemoryPreferences, getAgentCorrections } from "@/lib/api";
import type { Memory, MemoryStats, UserPreferences, AgentCorrectionItem } from "@/lib/api";
import { PremiumGate } from "@/components/PremiumGate";

const TYPE_COLORS: Record<string, string> = {
  BEHAVIOURAL: "#D4A240",
  PERFORMANCE: "#22c55e",
  PSYCHOLOGICAL: "#f97316",
  ACCOUNT_STATE: "#3b82f6",
  PREFERENCE: "#8b5cf6",
  LEARNING: "#06b6d4",
  SESSION_CONTEXT: "#6b7280",
};

const IMPORTANCE_BADGE: Record<string, { bg: string; color: string }> = {
  HIGH: { bg: "hsl(0 70% 50% / 0.12)", color: "hsl(0 70% 60%)" },
  MEDIUM: { bg: "hsl(42 78% 50% / 0.12)", color: "hsl(42 78% 60%)" },
  LOW: { bg: "hsl(var(--border))", color: "hsl(var(--muted-foreground))" },
};

export default function MemoryPage() {
  return (
    <PremiumGate requiredTier="retail" feature="Memory Layer" reason="AI memory tracks your behavior and agent corrections to improve signal accuracy over time. Available on Retail and above.">
      <MemoryContent />
    </PremiumGate>
  );
}

function MemoryContent() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [corrections, setCorrections] = useState<AgentCorrectionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"memories" | "corrections" | "profile">("memories");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [memRes, statsRes, prefsRes, corrRes] = await Promise.allSettled([
        getMemories(),
        getMemoryStats(),
        getMemoryPreferences(),
        getAgentCorrections(30),
      ]);
      if (memRes.status === "fulfilled") setMemories(memRes.value.memories);
      if (statsRes.status === "fulfilled") setStats(statsRes.value);
      if (prefsRes.status === "fulfilled") setPrefs(prefsRes.value.preferences);
      if (corrRes.status === "fulfilled") setCorrections(corrRes.value.corrections);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleDelete(id: string) {
    try {
      await deleteMemory(id);
      setMemories(prev => prev.filter((_, i) => i !== memories.findIndex(m => (m as unknown as { id: string }).id === id)));
      load(); // refresh
    } catch {}
  }

  const panelStyle: React.CSSProperties = {
    background: "hsl(var(--surface-1))",
    border: "1px solid hsl(var(--border))",
    borderRadius: 6,
    padding: 16,
  };

  return (
    <div className="min-h-screen" style={{ background: "hsl(var(--surface-0))" }}>
      <section className="max-w-5xl mx-auto px-6 pt-16 pb-6">
        <p className="text-[13px] font-bold tracking-[0.18em] mb-3"
           style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--primary))" }}>
          MEMORY LAYER
        </p>
        <h1 className="font-bold mb-2"
            style={{ fontSize: "clamp(22px, 3.5vw, 32px)", letterSpacing: "-0.03em", color: "hsl(var(--foreground))" }}>
          What the platform knows about you
        </h1>
        <p className="text-xs mb-6" style={{ color: "hsl(var(--muted-foreground))", maxWidth: 560 }}>
          Every signal, every interaction, every pattern — stored as semantic memory.
          The more you use the platform, the smarter it gets. You can delete any memory at any time.
        </p>

        {/* Stats Row */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
            {[
              { label: "Memories", value: stats.memory_count, color: "hsl(var(--primary))" },
              { label: "Interactions", value: stats.interaction_count, color: "#22c55e" },
              { label: "Agent Corrections", value: stats.correction_count, color: "#f97316" },
              { label: "Status", value: stats.status === "active" ? "ACTIVE" : "WARMING UP", color: stats.status === "active" ? "#22c55e" : "#D4A240" },
            ].map(s => (
              <div key={s.label} style={panelStyle}>
                <div className="text-[13px] font-bold tracking-[0.14em] mb-1" style={{ color: "hsl(var(--muted-foreground))" }}>{s.label.toUpperCase()}</div>
                <div className="text-xl font-bold" style={{ color: s.color }}>{s.value}</div>
              </div>
            ))}
          </div>
        )}

        {/* Tab Nav */}
        <div className="flex gap-2 mb-6">
          {(["memories", "corrections", "profile"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className="text-[14px] font-bold tracking-[0.08em] uppercase px-4 py-2 transition-all"
              style={{
                borderRadius: 4,
                background: tab === t ? "hsl(var(--primary) / 0.1)" : "transparent",
                border: tab === t ? "1px solid hsl(var(--primary) / 0.25)" : "1px solid hsl(var(--border))",
                color: tab === t ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
              }}
            >{t}</button>
          ))}
        </div>

        {/* Memories Tab */}
        {tab === "memories" && (
          <div className="space-y-3">
            {loading && <div className="text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>Loading memories...</div>}
            {!loading && memories.length === 0 && (
              <div style={panelStyle}>
                <p className="text-sm" style={{ color: "hsl(var(--muted-foreground))" }}>
                  No memories yet. Generate some signals and the platform will start learning about you.
                </p>
              </div>
            )}
            {memories.map((m, i) => {
              const badge = IMPORTANCE_BADGE[m.importance] || IMPORTANCE_BADGE.LOW;
              return (
                <div key={i} style={panelStyle}>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[13px] font-bold tracking-[0.1em] px-2 py-0.5 rounded"
                        style={{ background: `${TYPE_COLORS[m.type] || "#666"}20`, color: TYPE_COLORS[m.type] || "#888", border: `1px solid ${TYPE_COLORS[m.type] || "#666"}30` }}>
                        {m.type}
                      </span>
                      <span className="text-[13px] font-bold tracking-[0.1em] px-2 py-0.5 rounded"
                        style={{ background: badge.bg, color: badge.color }}>
                        {m.importance}
                      </span>
                    </div>
                    <span className="text-[14px] shrink-0" style={{ color: "hsl(var(--muted-foreground))" }}>
                      {m.created_at ? new Date(m.created_at).toLocaleDateString() : ""}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed" style={{ color: "hsl(var(--foreground))" }}>{m.memory}</p>
                </div>
              );
            })}
          </div>
        )}

        {/* Corrections Tab */}
        {tab === "corrections" && (
          <div className="space-y-3">
            {corrections.length === 0 && (
              <div style={panelStyle}>
                <p className="text-sm" style={{ color: "hsl(var(--muted-foreground))" }}>
                  No corrections yet. Mark signal outcomes (WIN/LOSS) to generate agent corrections.
                </p>
              </div>
            )}
            {corrections.map(c => (
              <div key={c.id} style={panelStyle}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[13px] font-bold tracking-[0.1em] px-2 py-0.5 rounded"
                    style={{ background: "hsl(0 70% 50% / 0.1)", color: "hsl(0 70% 60%)", border: "1px solid hsl(0 70% 50% / 0.2)" }}>
                    {c.correction_type}
                  </span>
                  <span className="text-[14px] font-bold" style={{ color: "hsl(var(--primary))" }}>{c.agent_name}</span>
                  {c.ticker && <span className="text-[14px]" style={{ color: "hsl(var(--muted-foreground))" }}>{c.ticker}</span>}
                </div>
                <p className="text-xs leading-relaxed" style={{ color: "hsl(var(--foreground))" }}>{c.lesson}</p>
              </div>
            ))}
          </div>
        )}

        {/* Profile Tab */}
        {tab === "profile" && (
          <div style={panelStyle}>
            {!prefs ? (
              <p className="text-sm" style={{ color: "hsl(var(--muted-foreground))" }}>
                Not enough data to compute your trading profile yet. Keep generating signals!
              </p>
            ) : (
              <div className="space-y-4">
                <h3 className="text-sm font-bold" style={{ color: "hsl(var(--foreground))" }}>Your Trading Profile</h3>
                <div className="grid sm:grid-cols-2 gap-3">
                  {[
                    { label: "Favorite Tickers", value: prefs.favorite_tickers?.join(", ") || "—" },
                    { label: "Preferred Direction", value: prefs.preferred_direction || "—" },
                    { label: "Preferred Timeframe", value: prefs.preferred_timeframe || "—" },
                    { label: "Signal Count", value: String(prefs.signal_count || 0) },
                    { label: "Win Rate", value: prefs.win_rate != null ? `${(prefs.win_rate * 100).toFixed(1)}%` : "—" },
                    { label: "Avg Confidence", value: prefs.avg_confidence_pref != null ? `${prefs.avg_confidence_pref.toFixed(0)}%` : "—" },
                    { label: "Asset Classes", value: prefs.favorite_asset_classes?.join(", ") || "—" },
                    { label: "Last Updated", value: prefs.last_computed ? new Date(prefs.last_computed).toLocaleDateString() : "—" },
                  ].map(item => (
                    <div key={item.label}>
                      <div className="text-[13px] font-bold tracking-[0.14em] mb-1" style={{ color: "hsl(var(--muted-foreground))" }}>{item.label.toUpperCase()}</div>
                      <div className="text-sm font-semibold" style={{ color: "hsl(var(--foreground))" }}>{item.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
