"use client";

/*
 * What the big percentage on a signal means, and how often signals in its band have actually worked.
 * Data: GET /api/v1/performance/calibration/global (model-level counts per 10-point band; see
 * backend/app/services/calibration.py). Nothing here is estimated in the browser: when a band has
 * too few resolved signals the note says so instead of showing a rate.
 */
import { useEffect, useState } from "react";
import { API_URL, type Signal } from "@/lib/api";

type Band = { band: string; n: number; wins: number; observed_pct: number; lo_pct: number; hi_pct: number; enough: boolean };
type Calibration = {
  definitions: Record<string, string>;
  outcome_definition: string;
  band_width: number;
  min_n_to_compare: number;
  modes: Record<string, { vote_share: { n: number; bands: Band[] }; expired: number; ambiguous: number }>;
};

let cached: Promise<Calibration | null> | null = null;
function loadCalibration(): Promise<Calibration | null> {
  if (!cached) {
    cached = fetch(`${API_URL}/api/v1/performance/calibration/global`)
      .then(r => (r.ok ? r.json() : null))
      .catch(() => null);
  }
  return cached;
}

const EXPLAINER = "https://quantneuraledge.com/trading-copilot#confidence";

export default function ConfidenceNote({ signal, pct }: { signal: Signal; pct: number }) {
  const [cal, setCal] = useState<Calibration | null | undefined>(undefined);
  useEffect(() => {
    let alive = true;
    loadCalibration().then(c => { if (alive) setCal(c); });
    return () => { alive = false; };
  }, []);

  const mode = signal.signal_mode || "AI";
  const width = cal?.band_width ?? 10;
  const lo = Math.min(Math.floor(pct / width) * width, 100 - width);
  const bandName = `${lo}-${lo + width}`;
  const band = cal?.modes?.[mode]?.vote_share?.bands?.find(b => b.band === bandName);

  let record: string;
  if (cal === undefined) record = "Loading the track record for this band…";
  else if (cal === null) record = "Track record unavailable right now.";
  else if (!band || band.n === 0) record = `No resolved signals in the ${bandName}% band yet.`;
  else if (!band.enough) record = `Signals shown ${bandName}%: only ${band.n} resolved so far - not enough to compare.`;
  else record = `Signals shown ${bandName}%: ${band.n} resolved, ${band.wins} reached take-profit 1 before the stop (${band.observed_pct.toFixed(0)}%, 95% range ${band.lo_pct.toFixed(0)}-${band.hi_pct.toFixed(0)}%).`;

  return (
    <div className="mt-2 rounded border border-border/60 bg-background/40 px-2.5 py-2 text-[12px] leading-snug font-mono text-muted-foreground">
      <div>
        <span className="text-foreground">{Math.round(pct)}%</span> = share of the analysts&apos; votes on this side.{" "}
        <span className="text-warn">Not a measured probability.</span>
      </div>
      <div className="mt-1">{record}</div>
      <a href={EXPLAINER} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block text-primary/80 hover:text-primary underline-offset-2 hover:underline">
        What the percentage means
      </a>
    </div>
  );
}
