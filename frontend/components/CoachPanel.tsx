"use client";

import { Brain, AlertTriangle, CheckCircle2, Pause, HandMetal } from "lucide-react";
import { cn } from "@/lib/utils";

interface CoachPanelProps {
  tiltDetected: boolean;
  tiltType: string;
  tiltSeverity: number;
  message: string;
  recommendation: string;
  positiveNote: string | null;
}

const TILT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  REVENGE:     AlertTriangle,
  FOMO:        AlertTriangle,
  OVERTRADING: AlertTriangle,
  HESITATION:  Pause,
  ESCALATION:  AlertTriangle,
  OFF_HOURS:   AlertTriangle,
  NONE:        CheckCircle2,
};

const RECOMMENDATION_COLORS: Record<string, string> = {
  CONTINUE:    "text-bull border-bull/30 bg-bull/5",
  PAUSE_5MIN:  "text-warn border-warn/30 bg-warn/5",
  REDUCE_SIZE: "text-warn border-warn/30 bg-warn/5",
  END_SESSION: "text-bear border-bear/30 bg-bear/5",
};

export function CoachPanel({ tiltDetected, tiltType, tiltSeverity, message, recommendation, positiveNote }: CoachPanelProps) {
  const TiltIcon = TILT_ICONS[tiltType] || CheckCircle2;

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <div className="flex items-center gap-2 mb-3">
        <Brain className="h-3.5 w-3.5 text-primary" />
        <span className="text-[14px] font-mono font-bold text-muted-foreground tracking-widest">SESSION COACH</span>
        {tiltDetected && (
          <span className="ml-auto text-[8px] font-mono font-bold px-1.5 py-0.5 rounded bg-bear/10 text-bear border border-bear/30">
            TILT {tiltSeverity}/10
          </span>
        )}
      </div>

      {/* Main message */}
      <div className={cn(
        "rounded border px-3 py-2 mb-2",
        tiltDetected ? "border-warn/30 bg-warn/5" : "border-bull/20 bg-bull/5"
      )}>
        <div className="flex items-start gap-2">
          <TiltIcon className={cn("h-3 w-3 mt-0.5 shrink-0", tiltDetected ? "text-warn" : "text-bull")} />
          <p className="text-[13px] font-mono text-foreground/90 leading-relaxed">{message}</p>
        </div>
      </div>

      {/* Recommendation badge */}
      <div className={cn(
        "inline-flex items-center gap-1 px-2 py-1 rounded border text-[8px] font-mono font-bold",
        RECOMMENDATION_COLORS[recommendation] || RECOMMENDATION_COLORS.CONTINUE
      )}>
        {recommendation.replace(/_/g, " ")}
      </div>

      {/* Positive note */}
      {positiveNote && (
        <div className="mt-2 flex items-start gap-1.5">
          <HandMetal className="h-2.5 w-2.5 text-bull mt-0.5 shrink-0" />
          <span className="text-[13px] font-mono text-bull/80">{positiveNote}</span>
        </div>
      )}
    </div>
  );
}
