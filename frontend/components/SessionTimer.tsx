"use client";

import { Clock, Zap, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface SessionTimerProps {
  killZone: string;
  killZoneActive: boolean;
  minutesRemaining: number;
  marketPhase: string;
  sessionElapsed: number;
  utcTime: string;
}

const KILL_ZONE_COLORS: Record<string, string> = {
  TOKYO:   "text-purple-400 border-purple-400/30 bg-purple-400/5",
  LONDON:  "text-blue-400 border-blue-400/30 bg-blue-400/5",
  NY_OPEN: "text-bull border-bull/30 bg-bull/5",
  OVERLAP: "text-amber-400 border-amber-400/30 bg-amber-400/5",
  NONE:    "text-muted-foreground border-border/50 bg-muted/10",
};

export function SessionTimer({ killZone, killZoneActive, minutesRemaining, marketPhase, sessionElapsed, utcTime }: SessionTimerProps) {
  const hours = Math.floor(sessionElapsed / 60);
  const mins = sessionElapsed % 60;

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Clock className="h-3.5 w-3.5 text-primary" />
          <span className="text-[14px] font-mono font-bold text-muted-foreground tracking-widest">SESSION TIMER</span>
        </div>
        <span className="text-[13px] font-mono text-muted-foreground">{utcTime}</span>
      </div>

      {/* Kill Zone Status */}
      <div className={cn(
        "rounded border px-3 py-2 mb-3",
        KILL_ZONE_COLORS[killZone] || KILL_ZONE_COLORS.NONE
      )}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {killZoneActive ? (
              <Zap className="h-3 w-3 animate-pulse" />
            ) : (
              <AlertTriangle className="h-3 w-3 opacity-50" />
            )}
            <span className="text-[13px] font-mono font-bold">
              {killZoneActive ? killZone.replace("_", " ") : "NO KILL ZONE"}
            </span>
          </div>
          {killZoneActive && (
            <span className={cn(
              "text-[14px] font-mono font-bold",
              minutesRemaining < 10 ? "text-bear animate-pulse" : ""
            )}>
              {minutesRemaining}m left
            </span>
          )}
        </div>
      </div>

      {/* Session elapsed + phase */}
      <div className="flex items-center justify-between text-[13px] font-mono">
        <span className="text-muted-foreground">
          Session: <span className="text-foreground font-bold">{hours}h {mins}m</span>
        </span>
        <span className="text-muted-foreground">
          Phase: <span className="text-foreground">{marketPhase.replace(/_/g, " ")}</span>
        </span>
      </div>
    </div>
  );
}
