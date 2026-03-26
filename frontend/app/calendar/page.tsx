"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { getCalendarEvents, wakeBackend, type CalendarEvent } from "@/lib/api";

const IMPACT_STYLE: Record<string, string> = {
  HIGH: "bg-bear/20 text-bear border-bear/30",
  MEDIUM: "bg-warn/20 text-warn border-warn/30",
  LOW: "bg-muted text-muted-foreground border-border/30",
};

const CATEGORY_EMOJI: Record<string, string> = {
  employment: "JOBS",
  inflation: "CPI",
  growth: "GDP",
  consumer: "RETAIL",
  manufacturing: "PMI",
  central_bank: "FED",
};

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [weeks, setWeeks] = useState(2);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { wakeBackend(); }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getCalendarEvents(weeks)
      .then((res) => setEvents(res.events))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [weeks]);

  // Group events by date
  const grouped: Record<string, CalendarEvent[]> = {};
  for (const e of events) {
    (grouped[e.date] ||= []).push(e);
  }

  const today = new Date().toISOString().split("T")[0];

  return (
    <div className="min-h-screen pt-24 pb-12 px-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-mono font-bold text-foreground">Economic Calendar</h1>
          <p className="text-xs font-mono text-muted-foreground mt-0.5">
            Major US macro events — FOMC, CPI, NFP, GDP, PMI
          </p>
        </div>
        <div className="flex items-center gap-1">
          {[1, 2, 4, 8].map((w) => (
            <button
              key={w}
              onClick={() => setWeeks(w)}
              className={cn(
                "text-[10px] font-mono font-bold px-2.5 py-1 rounded border transition-colors",
                weeks === w
                  ? "bg-primary/10 border-primary/50 text-primary"
                  : "border-border/40 text-muted-foreground hover:text-foreground"
              )}
            >
              {w}W
            </button>
          ))}
        </div>
      </div>

      {/* Impact legend */}
      <div className="flex items-center gap-3 mb-4">
        <span className="text-[9px] font-mono text-muted-foreground">IMPACT:</span>
        {(["HIGH", "MEDIUM", "LOW"] as const).map((level) => (
          <span key={level} className={cn("text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border", IMPACT_STYLE[level])}>
            {level}
          </span>
        ))}
      </div>

      {loading ? (
        <div className="panel p-12 flex items-center justify-center">
          <div className="live-dot" />
        </div>
      ) : error ? (
        <div className="panel p-6 text-center">
          <span className="text-bear font-mono text-xs">{error}</span>
        </div>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="panel p-12 text-center">
          <span className="text-muted-foreground font-mono text-xs">NO EVENTS IN RANGE</span>
        </div>
      ) : (
        <div className="space-y-1">
          {Object.entries(grouped).map(([dateStr, dayEvents]) => {
            const isToday = dateStr === today;
            const isPast = dateStr < today;
            const dayLabel = new Date(dateStr + "T12:00:00").toLocaleDateString("en-US", {
              weekday: "short",
              month: "short",
              day: "numeric",
            });

            return (
              <div key={dateStr} className={cn("panel", isToday && "ring-1 ring-primary/30")}>
                {/* Day header */}
                <div className={cn(
                  "flex items-center gap-2 px-4 py-2 border-b border-border/30",
                  isToday ? "bg-primary/5" : isPast ? "bg-muted/20" : ""
                )}>
                  <span className={cn(
                    "text-[11px] font-mono font-bold",
                    isToday ? "text-primary" : isPast ? "text-muted-foreground" : "text-foreground"
                  )}>
                    {dayLabel}
                  </span>
                  {isToday && (
                    <span className="text-[8px] font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded">TODAY</span>
                  )}
                  <span className="text-[9px] font-mono text-muted-foreground ml-auto">{dayEvents.length} event{dayEvents.length > 1 ? "s" : ""}</span>
                </div>

                {/* Events table */}
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border/20">
                      <th className="text-[8px] font-mono text-muted-foreground py-1 px-4 text-left w-14">TIME</th>
                      <th className="text-[8px] font-mono text-muted-foreground py-1 px-2 text-left">EVENT</th>
                      <th className="text-[8px] font-mono text-muted-foreground py-1 px-2 text-center w-16">IMPACT</th>
                      <th className="text-[8px] font-mono text-muted-foreground py-1 px-2 text-right w-16">PREV</th>
                      <th className="text-[8px] font-mono text-muted-foreground py-1 px-2 text-right w-16">FCST</th>
                      <th className="text-[8px] font-mono text-muted-foreground py-1 px-2 text-right w-16">ACT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dayEvents.map((evt, i) => (
                      <tr key={i} className={cn(
                        "border-b border-border/10",
                        isPast ? "opacity-50" : "",
                        evt.impact === "HIGH" && !isPast ? "bg-bear/3" : ""
                      )}>
                        <td className="text-[10px] font-mono text-muted-foreground py-1.5 px-4">{evt.time}</td>
                        <td className="py-1.5 px-2">
                          <div className="flex items-center gap-2">
                            <span className="text-[8px] font-mono font-bold text-primary/60 bg-primary/5 px-1 rounded">
                              {CATEGORY_EMOJI[evt.category] || evt.category}
                            </span>
                            <span className="text-[11px] font-mono text-foreground">{evt.name}</span>
                          </div>
                        </td>
                        <td className="text-center py-1.5 px-2">
                          <span className={cn("text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border", IMPACT_STYLE[evt.impact])}>
                            {evt.impact}
                          </span>
                        </td>
                        <td className="text-[10px] font-mono text-muted-foreground text-right py-1.5 px-2">{evt.previous || "—"}</td>
                        <td className="text-[10px] font-mono text-foreground text-right py-1.5 px-2 font-bold">{evt.forecast || "—"}</td>
                        <td className={cn(
                          "text-[10px] font-mono text-right py-1.5 px-2 font-bold",
                          evt.actual ? "text-primary" : "text-muted-foreground"
                        )}>
                          {evt.actual || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
