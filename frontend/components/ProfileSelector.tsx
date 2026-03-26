"use client";

import { useState, useEffect, useRef } from "react";
import { ChevronDown } from "lucide-react";
import { listProfiles, setActiveProfile, type StrategyProfile } from "@/lib/api";
import { cn } from "@/lib/utils";

const PROFILE_ICONS: Record<string, string> = {
  balanced:      "=",
  ict_smc:       "$",
  orb:           ">",
  vwap_pullback: "~",
  swing:         "W",
  scalper:       "Z",
  news_catalyst: "!",
};

interface ProfileSelectorProps {
  value: string;
  onChange: (slug: string) => void;
  compact?: boolean;
}

export function ProfileSelector({ value, onChange, compact }: ProfileSelectorProps) {
  const [profiles, setProfiles] = useState<StrategyProfile[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listProfiles().then(setProfiles).catch(() => {});
  }, []);

  // Close on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  const active = profiles.find((p) => p.slug === value) || profiles.find((p) => p.is_default);
  const label = active?.name || "Balanced";
  const icon = PROFILE_ICONS[value] || "=";

  const handleSelect = (slug: string) => {
    onChange(slug);
    setOpen(false);
    // Persist to backend (fire-and-forget)
    setActiveProfile(slug).catch(() => {});
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-1.5 rounded border transition-colors font-mono",
          compact
            ? "px-2 py-0.5 text-[10px]"
            : "px-3 py-1 text-xs",
          "border-primary/30 text-primary hover:bg-primary/10"
        )}
      >
        <span className="font-bold">{icon}</span>
        <span className="font-bold truncate max-w-[100px]">{label}</span>
        <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
      </button>

      {open && profiles.length > 0 && (
        <div className="absolute z-50 mt-1 w-64 rounded border border-border bg-background shadow-xl">
          {profiles.map((p) => (
            <button
              key={p.slug}
              onClick={() => handleSelect(p.slug)}
              className={cn(
                "w-full text-left px-3 py-2 transition-colors flex items-start gap-2",
                p.slug === value
                  ? "bg-primary/10 text-primary"
                  : "text-foreground hover:bg-muted"
              )}
            >
              <span className="font-mono font-bold text-xs mt-0.5 w-4 shrink-0">
                {PROFILE_ICONS[p.slug] || "="}
              </span>
              <div className="min-w-0">
                <div className="text-xs font-mono font-bold truncate">{p.name}</div>
                <div className="text-[9px] text-muted-foreground leading-tight mt-0.5">
                  {p.description}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
