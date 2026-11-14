/**
 * MOCK — Strategy Truth Lab.
 *
 * Stands in for the Python test engine until the backend exists. Rules:
 *  - the six verdicts in truth_lab_examples.json are REAL results from the
 *    owner's research lab and are served verbatim, never altered;
 *  - nothing here computes a result. Text that matches one of the six gets
 *    that strategy's rules back; a run returns the stored verdict only when
 *    the confirmed rules are exactly the tested ones. Anything else answers
 *    "unavailable" - the mock never invents a verdict.
 */
import fixture from "./truth_lab_examples.json";
import type {
  LabJobResponse,
  LabParseResponse,
  LabRule,
  LabStage,
  LabStageKey,
  LabVerdict,
} from "@/lib/terminal-api";

export const LAB_SOURCE: string = fixture.source;
export const LAB_EXAMPLES: LabVerdict[] = fixture.examples as LabVerdict[];

export function getExample(id: string | null | undefined): LabVerdict | null {
  if (!id) return null;
  return LAB_EXAMPLES.find((e) => e.id === id) ?? null;
}

export function toRules(texts: string[]): LabRule[] {
  return texts.map((text, i) => ({ id: `r${i + 1}`, text }));
}

/** MOCK: words that identify each stored strategy in free text. */
const KEYWORDS: Record<string, string[]> = {
  "noise-area-ustec": ["noise", "band", "vwap", "zarattini"],
  amd: ["asian", "sweep", "power of 3", "amd", "london"],
  "macd-ema200": ["macd", "200 ema", "ema200", "ema 200"],
  "friday-low": ["friday", "monday", "thursday"],
  "overnight-range": ["overnight range", "third", "adx"],
  "crowd-fade": ["crowd", "binance", "accounts", "crypto"],
};

/**
 * MOCK: what the parser had to assume for each stored strategy - the gaps
 * between the trader's sentence and the rules that were actually tested.
 */
const ASSUMPTIONS: Record<string, string[]> = {
  "noise-area-ustec": [
    "Checks only at HH:00 and HH:30, as in the published method.",
    "\"The close\" read as 16:00 New York.",
    "Trailing stop uses the band or VWAP, whichever is tighter.",
  ],
  amd: [
    "Asian range read as 19:00-00:00 New York.",
    "London window read as 02:00-05:00 New York.",
    "\"Closes back inside\" read as an M5 close.",
    "No target named: opposite side of the range or 2R, out by 12:00 New York.",
  ],
  "macd-ema200": [
    "MACD settings not named: standard 12, 26, 9.",
    "Mirror rule added for shorts.",
    "No stop named: 10-bar swing or the EMA200.",
    "Time cap of 50 bars added.",
  ],
  "friday-low": [
    "\"Visited\" read as Monday's regular session trading below Friday's low.",
    "A tradable version added: short at Monday's open to Friday's low, 1:1 stop.",
  ],
  "overnight-range": [
    "Overnight range read as 18:00-09:30 New York.",
    "\"The break\" read as an M5 close beyond the range.",
    "No stop named: mid-range.",
  ],
  "crowd-fade": [
    "\"Unusually long\" read as a z-score of 1.5 or more against 90 days.",
    "\"Most accounts\" read as the all-account long/short ratio.",
    "Symbols not named: BTC and ETH.",
  ],
};

function norm(s: string): string {
  return s.toLowerCase().replace(/\s+/g, " ").trim();
}

function matchExample(text: string): LabVerdict | null {
  const t = norm(text);
  const exact = LAB_EXAMPLES.find((e) => norm(e.asked) === t);
  if (exact) return exact;
  let best: LabVerdict | null = null;
  let bestScore = 0;
  for (const e of LAB_EXAMPLES) {
    const score = (KEYWORDS[e.id] ?? []).filter((k) => t.includes(k)).length;
    if (score > bestScore) {
      best = e;
      bestScore = score;
    }
  }
  return bestScore >= 2 ? best : null;
}

/** MOCK parser. The real one is a language model whose output the trader confirms. */
export function mockParse(text: string): LabParseResponse {
  const hit = matchExample(text);
  if (hit) {
    return { name: hit.name, rules: toRules(hit.rules), assumptions: ASSUMPTIONS[hit.id] ?? [] };
  }

  // Unknown strategy: split the sentence into clauses so the confirm step
  // still has something to edit. No intelligence is implied.
  const clauses = text
    .split(/[.;\n]+(?=\s|$)|,\s+|\s+then\s+/i)
    .map((c) => c.trim().replace(/^(and|then)\s+/i, ""))
    .filter((c) => c.length > 2)
    .slice(0, 8)
    .map((c) => c.charAt(0).toUpperCase() + c.slice(1));

  const t = norm(text);
  const assumptions: string[] = ["Times read as New York time."];
  if (!/\b(gold|xau|eur|usd|gbp|jpy|btc|eth|us500|ustec|us30|nasdaq|s&p|dax|oil)\b/.test(t)) {
    assumptions.push("No market named: the default basket would be used (gold, 6 FX pairs, 4 indices).");
  }
  if (!/\bstop\b/.test(t)) assumptions.push("No stop named: one must be added before a test can run.");
  if (!/\b(target|exit|close|flat|hold)\b/.test(t)) {
    assumptions.push("No exit named: one must be added before a test can run.");
  }

  return {
    name: "Untitled strategy",
    rules: toRules(clauses.length ? clauses : [text.trim()]),
    assumptions,
  };
}

// ─── Jobs ────────────────────────────────────────────────────────────────────

export const STAGE_KEYS: LabStageKey[] = ["freeze", "select", "sealed", "luck", "direction"];
/** MOCK pacing: the real test takes minutes; the mock steps every 800 ms. */
const STAGE_MS = 800;

function sameRules(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const nb = b.map(norm);
  return a.map(norm).every((r, i) => r === nb[i]);
}

/** The job id carries the whole state, so the mock needs no storage. */
export function mockRun(rules: LabRule[]): string {
  const texts = rules.map((r) => r.text);
  const hit = LAB_EXAMPLES.find((e) => sameRules(texts, e.rules));
  return `mock.${hit ? hit.id : "none"}.${Date.now().toString(36)}`;
}

export function mockJob(jobId: string, now = Date.now()): LabJobResponse | null {
  const m = /^mock\.([a-z0-9-]+)\.([a-z0-9]+)$/.exec(jobId);
  if (!m) return null;
  const example = getExample(m[1]);
  const started = parseInt(m[2], 36);
  if (!Number.isFinite(started)) return null;

  const elapsed = Math.max(0, now - started);
  const doneCount = Math.min(STAGE_KEYS.length, Math.floor(elapsed / STAGE_MS));
  const finished = doneCount >= STAGE_KEYS.length;

  // Rules outside the six stored results stop after the freeze: there is no
  // engine behind the mock, and it must not pretend there is.
  if (!example) {
    const frozen = elapsed >= STAGE_MS;
    const stages: LabStage[] = STAGE_KEYS.map((key, i) => ({
      key,
      state: i === 0 ? (frozen ? "done" : "running") : "pending",
    }));
    return {
      job_id: jobId,
      status: frozen ? "unavailable" : "running",
      stages,
      verdict: null,
      message: frozen
        ? "This preview has no test engine attached. It shows the six stored results only, and only for the exact rules that were tested. Your rules were not run."
        : undefined,
    };
  }

  const stages: LabStage[] = STAGE_KEYS.map((key, i) => ({
    key,
    state: i < doneCount ? "done" : i === doneCount ? "running" : "pending",
  }));
  return {
    job_id: jobId,
    status: finished ? "done" : "running",
    stages,
    verdict: finished ? example : null,
  };
}
