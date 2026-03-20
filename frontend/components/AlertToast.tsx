"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { X, Zap, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { type ScannerAlert } from "@/lib/useAlerts";

interface AlertToastProps {
  alert:      ScannerAlert;
  onDismiss:  () => void;
}

export function AlertToast({ alert, onDismiss }: AlertToastProps) {
  const router   = useRouter();
  const [visible, setVisible] = useState(false);
  const [timeLeft, setTimeLeft] = useState(25);
  const isLong = alert.direction === "LONG";

  // Animate in
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(t);
  }, []);

  // Auto-dismiss countdown
  useEffect(() => {
    if (timeLeft <= 0) { onDismiss(); return; }
    const t = setTimeout(() => setTimeLeft(prev => prev - 1), 1000);
    return () => clearTimeout(t);
  }, [timeLeft, onDismiss]);

  function handleViewIntel() {
    onDismiss();
    router.push("/news");
  }

  function handleDismiss() {
    setVisible(false);
    setTimeout(onDismiss, 300);
  }

  return (
    <div className={cn(
      "w-80 rounded border shadow-xl transition-all duration-300 overflow-hidden",
      "bg-[hsl(0_0%_4%)] border-primary/30",
      visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
    )}>
      {/* Progress bar */}
      <div className="h-0.5 bg-muted">
        <div
          className="h-full bg-primary transition-all duration-1000 ease-linear"
          style={{ width: `${(timeLeft / 25) * 100}%` }}
        />
      </div>

      <div className="p-3">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Zap className="h-3 w-3 text-primary animate-pulse" />
            <span className="text-[9px] font-mono font-bold text-primary tracking-widest">
              OPPORTUNITY DETECTED
            </span>
          </div>
          <button onClick={handleDismiss} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="h-3 w-3" />
          </button>
        </div>

        {/* Ticker + direction */}
        <div className="flex items-center gap-2 mb-1.5">
          <div className={cn(
            "flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] font-mono font-bold",
            isLong ? "bg-bull/10 border-bull/30 text-bull" : "bg-bear/10 border-bear/30 text-bear"
          )}>
            {isLong ? <TrendingUp className="h-2.5 w-2.5" /> : <TrendingDown className="h-2.5 w-2.5" />}
            {alert.direction}
          </div>
          <span className="font-mono text-sm font-bold text-foreground">{alert.ticker}</span>
          <span className={cn(
            "ml-auto text-[10px] font-mono font-bold",
            alert.confidence >= 80 ? "text-bull" : "text-warn"
          )}>
            {Math.round(alert.confidence)}%
          </span>
        </div>

        {/* Summary */}
        <p className="text-[10px] text-muted-foreground font-mono leading-relaxed mb-2 line-clamp-2">
          {alert.summary}
        </p>

        {/* Entry hint */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-[9px] font-mono text-muted-foreground">
            ENTRY HINT <span className="text-foreground font-semibold">
              {alert.entry_hint > 1000
                ? alert.entry_hint.toLocaleString("en-US", { maximumFractionDigits: 0 })
                : alert.entry_hint.toFixed(4)}
            </span>
          </span>
          <span className="text-[9px] font-mono text-muted-foreground">{timeLeft}s</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleViewIntel}
            className="flex-1 text-[9px] font-mono font-bold px-2 py-1.5 rounded border border-primary/40 text-primary hover:bg-primary/10 transition-colors"
          >
            VIEW INTEL →
          </button>
          <button
            onClick={handleDismiss}
            className="text-[9px] font-mono px-2 py-1.5 rounded border border-border/40 text-muted-foreground hover:text-foreground transition-colors"
          >
            DISMISS
          </button>
        </div>
      </div>
    </div>
  );
}


// ── Alert stack — renders up to 3 toasts stacked bottom-right ────────────────

interface AlertStackProps {
  alerts:    ScannerAlert[];
  onDismiss: (timestamp: string) => void;
}

export function AlertStack({ alerts, onDismiss }: AlertStackProps) {
  const visible = alerts.slice(0, 3);
  if (visible.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 items-end pointer-events-none">
      {visible.map((alert) => (
        <div key={alert.timestamp} className="pointer-events-auto">
          <AlertToast
            alert={alert}
            onDismiss={() => onDismiss(alert.timestamp)}
          />
        </div>
      ))}
    </div>
  );
}
