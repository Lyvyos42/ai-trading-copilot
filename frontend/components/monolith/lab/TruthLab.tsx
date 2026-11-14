"use client";

/**
 * Strategy Truth Lab — the whole flow on one screen:
 *   01 describe  ->  02 confirm the rules  ->  03 sealed test  ->  04 verdict
 * with the library of tested strategies below.
 *
 * The step that matters is 02. Nothing is tested until the trader has read
 * the exact rules and confirmed them; that is what the competitors skip.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { cn } from "@/lib/utils";
import {
  terminalApi,
  TerminalApiError,
  VERDICT_LABELS,
  type LabJobResponse,
  type LabRule,
  type LabStage,
  type LabStageKey,
  type LabVerdict,
} from "@/lib/terminal-api";
import { Panel, PanelError, Skeleton, VERDICT_META, VerdictBadge } from "@/components/monolith/primitives";
import {
  IconArrowRight,
  IconCheck,
  IconLock,
  IconPlus,
  IconSpinner,
  IconX,
} from "@/components/icons/GeoIcons";

type Phase = "describe" | "parsing" | "confirm" | "running" | "verdict" | "unavailable";

const STEPS: { n: string; label: string }[] = [
  { n: "01", label: "Describe" },
  { n: "02", label: "Confirm" },
  { n: "03", label: "Test" },
  { n: "04", label: "Verdict" },
];

const STAGE_COPY: Record<LabStageKey, { title: string; body: string }> = {
  freeze: {
    title: "Rules frozen",
    body: "Tested exactly as you confirmed them. No tuning after this point.",
  },
  select: {
    title: "Picked on the early years",
    body: "Any choice between variants is made on the early years only.",
  },
  sealed: {
    title: "Checked once on the later years",
    body: "The later years stay sealed until this single run.",
  },
  luck: {
    title: "Luck correction",
    body: "The bar rises with every variant that was tried.",
  },
  direction: {
    title: "Direction check",
    body: "The edge must come from the direction of the trade, not from when it was taken.",
  },
};

const STAGE_ORDER: LabStageKey[] = ["freeze", "select", "sealed", "luck", "direction"];

function phaseStep(phase: Phase): number {
  if (phase === "describe" || phase === "parsing") return 0;
  if (phase === "confirm") return 1;
  if (phase === "running") return 2;
  return 3;
}

function asRules(texts: string[]): LabRule[] {
  return texts.map((text, i) => ({ id: `r${i + 1}`, text }));
}

export function TruthLab({
  initialExample,
  initialStep,
}: {
  /** Deep link: /lab?example=<id> opens a stored result. */
  initialExample?: string;
  /** Deep link: /lab?example=<id>&step=rules opens the confirmation step. */
  initialStep?: string;
}) {
  const {
    data: library,
    error: libraryError,
    mutate: retryLibrary,
  } = useSWR("lab/library", () => terminalApi.lab.library(), { revalidateOnFocus: false });

  const [text, setText] = useState("");
  const [phase, setPhase] = useState<Phase>("describe");
  const [name, setName] = useState("");
  const [rules, setRules] = useState<LabRule[]>([]);
  const [assumptions, setAssumptions] = useState<string[]>([]);
  const [job, setJob] = useState<LabJobResponse | null>(null);
  const [verdict, setVerdict] = useState<LabVerdict | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const textRef = useRef<HTMLTextAreaElement>(null);
  const rulesHeadRef = useRef<HTMLDivElement>(null);
  const verdictRef = useRef<HTMLDivElement>(null);
  const nextRuleId = useRef(100);
  const runToken = useRef(0);
  const deepLinked = useRef(false);

  const cancelRun = useCallback(() => {
    runToken.current += 1;
  }, []);

  useEffect(() => cancelRun, [cancelRun]);

  // ── 01 -> 02 ───────────────────────────────────────────────────────────────
  const parse = useCallback(
    async (raw: string) => {
      const t = raw.trim();
      if (t.length < 12) {
        setParseError("Too short to read. Describe an entry, a stop and an exit in a sentence or two.");
        textRef.current?.focus();
        return;
      }
      cancelRun();
      setParseError(null);
      setRunError(null);
      setVerdict(null);
      setJob(null);
      setPhase("parsing");
      try {
        const res = await terminalApi.lab.parse({ text: t });
        setName(res.name);
        setRules(res.rules);
        setAssumptions(res.assumptions);
        setPhase("confirm");
        requestAnimationFrame(() => rulesHeadRef.current?.focus());
      } catch (e) {
        setParseError(
          e instanceof TerminalApiError
            ? e.message
            : "Could not read the strategy. Check your connection and try again.",
        );
        setPhase("describe");
        textRef.current?.focus();
      }
    },
    [cancelRun],
  );

  // ── 02 -> 03 -> 04 ─────────────────────────────────────────────────────────
  const run = useCallback(async () => {
    const confirmed = rules.map((r) => ({ ...r, text: r.text.trim() })).filter((r) => r.text);
    if (confirmed.length === 0) {
      setRunError("Add at least one rule before running a test.");
      return;
    }
    cancelRun();
    const token = runToken.current;
    setRunError(null);
    setRules(confirmed);
    setVerdict(null);
    setJob(null);
    setPhase("running");
    try {
      const { job_id } = await terminalApi.lab.run({ rules: confirmed, asked: text.trim(), name });
      for (;;) {
        const j = await terminalApi.lab.job(job_id);
        if (token !== runToken.current) return;
        setJob(j);
        if (j.status === "done" && j.verdict) {
          setVerdict(j.verdict);
          setPhase("verdict");
          requestAnimationFrame(() => verdictRef.current?.focus());
          return;
        }
        if (j.status === "unavailable" || j.status === "error" || j.status === "done") {
          setPhase("unavailable");
          requestAnimationFrame(() => verdictRef.current?.focus());
          return;
        }
        await new Promise((r) => setTimeout(r, 350));
        if (token !== runToken.current) return;
      }
    } catch (e) {
      if (token !== runToken.current) return;
      setRunError(
        e instanceof TerminalApiError ? e.message : "The test did not start. Check your connection and try again.",
      );
      setPhase("confirm");
    }
  }, [rules, text, name, cancelRun]);

  // ── Library: open a stored result ──────────────────────────────────────────
  const openStored = useCallback(
    (ex: LabVerdict, focus = true) => {
      cancelRun();
      setText(ex.asked);
      setName(ex.name);
      setRules(asRules(ex.rules));
      setAssumptions([]);
      setParseError(null);
      setRunError(null);
      setJob(null);
      setVerdict(ex);
      setPhase("verdict");
      const token = runToken.current;
      terminalApi.lab
        .parse({ text: ex.asked })
        .then((res) => {
          if (token === runToken.current) setAssumptions(res.assumptions);
        })
        .catch(() => {
          /* the assumptions are a bonus here; the verdict stands without them */
        });
      if (focus) {
        requestAnimationFrame(() => {
          verdictRef.current?.scrollIntoView({ block: "nearest" });
          verdictRef.current?.focus({ preventScroll: true });
        });
      }
    },
    [cancelRun],
  );

  const reset = useCallback(() => {
    cancelRun();
    setText("");
    setName("");
    setRules([]);
    setAssumptions([]);
    setJob(null);
    setVerdict(null);
    setParseError(null);
    setRunError(null);
    setPhase("describe");
    requestAnimationFrame(() => textRef.current?.focus());
  }, [cancelRun]);

  const editRules = useCallback(() => {
    cancelRun();
    setJob(null);
    setVerdict(null);
    setRunError(null);
    setPhase("confirm");
    requestAnimationFrame(() => rulesHeadRef.current?.focus());
  }, [cancelRun]);

  // Deep links, once the library has loaded.
  useEffect(() => {
    if (deepLinked.current || !library || !initialExample) return;
    const ex = library.examples.find((e) => e.id === initialExample);
    deepLinked.current = true;
    if (!ex) return;
    if (initialStep === "rules") {
      setText(ex.asked);
      void parse(ex.asked);
    } else {
      openStored(ex, false);
    }
  }, [library, initialExample, initialStep, parse, openStored]);

  const step = phaseStep(phase);
  const locked = phase === "running" || phase === "verdict" || phase === "unavailable";
  const stages: LabStage[] =
    phase === "verdict"
      ? STAGE_ORDER.map((key) => ({ key, state: "done" }))
      : job
        ? job.stages
        : STAGE_ORDER.map((key, i) => ({ key, state: phase === "running" && i === 0 ? "running" : "pending" }));

  const announce =
    phase === "parsing"
      ? "Reading your strategy."
      : phase === "confirm"
        ? `${rules.length} rules understood. Review and confirm them.`
        : phase === "running"
          ? "Sealed test running."
          : phase === "verdict" && verdict
            ? `Verdict: ${verdict.verdict}. ${verdict.headline}`
            : phase === "unavailable"
              ? "The test was not run."
              : "";

  return (
    <div>
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>

      {/* ── Page header ─────────────────────────────────────────────────── */}
      <header className="grid gap-x-8 gap-y-3 border-b border-border px-3 py-3 md:px-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0">
          <h1 className="text-[20px] font-extrabold italic leading-6 tracking-[-0.04em] text-primary">
            TRUTH LAB
            <span className="font-light not-italic text-muted-foreground">.SEALED_TESTS</span>
          </h1>
          <p className="mt-1 max-w-[96ch] text-[13px] leading-5 text-muted-foreground">
            <span className="font-bold text-foreground">The anti-overfitting backtester.</span> Describe a strategy,
            confirm the exact rules, and get a verdict measured on years the rules have never seen.
          </p>
        </div>

        <ol className="grid grid-cols-4 border border-border-strong lg:w-[440px]" aria-label="Progress">
          {STEPS.map((s, i) => {
            const state = i < step ? "done" : i === step ? "current" : "todo";
            return (
              <li
                key={s.n}
                aria-current={state === "current" ? "step" : undefined}
                className={cn(
                  "flex items-center justify-center gap-1.5 px-1 py-1.5 text-[10px] font-extrabold uppercase tracking-[0.1em]",
                  i > 0 && "border-l border-border-strong",
                  state === "current" && "bg-primary text-black",
                  state === "done" && "bg-primary/10 text-primary",
                  state === "todo" && "text-muted-foreground",
                )}
              >
                {state === "done" ? <IconCheck size={11} strokeWidth={2} /> : <span className="m-num">{s.n}</span>}
                <span>{s.label}</span>
                <span className="sr-only">
                  {state === "done" ? "(done)" : state === "current" ? "(current step)" : ""}
                </span>
              </li>
            );
          })}
        </ol>
      </header>

      {/* ── Workbench: 2 × 2 on desktop, one column on phones ───────────── */}
      <div className="grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:grid-rows-[auto_1fr]">
        {/* 01 DESCRIBE */}
        <Panel
          id="describe"
          step="01"
          title="Describe"
          className="border-b border-border lg:col-start-1 lg:row-start-1 lg:border-r"
          bodyClassName="flex flex-col gap-3 p-3"
          right={<span className="m-label hidden sm:inline">Plain English</span>}
        >
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void parse(text);
            }}
            noValidate
          >
            <div>
              <label htmlFor="lab-text" className="m-label mb-1 block">
                Your strategy, in your own words
              </label>
              <div className={cn("m-field", parseError && "border-bear")}>
                <textarea
                  id="lab-text"
                  ref={textRef}
                  rows={4}
                  maxLength={2000}
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    if (parseError) setParseError(null);
                  }}
                  aria-invalid={parseError ? true : undefined}
                  aria-describedby={parseError ? "lab-text-error lab-text-help" : "lab-text-help"}
                  placeholder="Buy when price closes above yesterday's high, stop under today's low, exit at the close."
                  className="block resize-y px-3 py-2 text-[16px] leading-6 md:text-[13px] md:leading-5"
                />
              </div>
              {parseError && (
                <p id="lab-text-error" role="alert" className="mt-1.5 text-[12px] leading-4 text-bear">
                  {parseError}
                </p>
              )}
              <p id="lab-text-help" className="mt-1.5 text-[12px] leading-4 text-muted-foreground">
                A language model turns your words into rules, and you confirm them. The test itself is rule-based
                Python.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="submit"
                disabled={phase === "parsing" || phase === "running"}
                className={cn(
                  "m-btn min-h-[44px] flex-1 sm:flex-none md:min-h-0",
                  step === 0 ? "m-btn-primary" : "m-btn-ghost",
                )}
              >
                {phase === "parsing" ? (
                  <>
                    <IconSpinner size={12} strokeWidth={2} className="m-spin" /> Reading
                  </>
                ) : step === 0 ? (
                  <>
                    Read my rules <IconArrowRight size={12} strokeWidth={2} />
                  </>
                ) : (
                  "Read again"
                )}
              </button>
              {step > 0 && (
                <button type="button" onClick={reset} className="m-btn m-btn-ghost min-h-[44px] md:min-h-0">
                  New test
                </button>
              )}
            </div>
          </form>

          <div>
            <div className="m-label mb-1.5">Or start from a strategy already tested</div>
            {libraryError ? (
              <PanelError what="the tested strategies" onRetry={() => void retryLibrary()} />
            ) : !library ? (
              <Skeleton rows={3} className="p-0" />
            ) : (
              <ul className="grid grid-cols-1 gap-px bg-border sm:grid-cols-2">
                {library.examples.map((ex) => (
                  <li key={ex.id} className="bg-surface-0">
                    <button
                      type="button"
                      title={ex.asked}
                      disabled={phase === "parsing" || phase === "running"}
                      onClick={() => {
                        setText(ex.asked);
                        setParseError(null);
                        textRef.current?.focus();
                      }}
                      className="flex min-h-[44px] w-full items-center gap-2 bg-surface-1 px-2.5 py-1.5 text-left text-[12px] font-semibold leading-4 text-foreground transition-colors hover:bg-surface-3 hover:text-primary disabled:cursor-not-allowed disabled:opacity-40 md:min-h-[32px]"
                    >
                      <IconPlus size={10} strokeWidth={2} className="shrink-0 text-primary" />
                      <span className="truncate">{ex.name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Panel>

        {/* 02 CONFIRM RULES */}
        <Panel
          id="rules"
          step="02"
          title="Rules as understood"
          className="border-b border-border lg:col-start-1 lg:row-start-2 lg:border-r"
          bodyClassName="flex flex-col"
          right={
            locked ? (
              <span className="m-chip m-chip-gold">
                <IconLock size={10} strokeWidth={1.8} /> Frozen
              </span>
            ) : phase === "confirm" ? (
              <span className="m-chip m-chip-gold">Awaiting your confirmation</span>
            ) : null
          }
        >
          <div ref={rulesHeadRef} tabIndex={-1} className="flex flex-1 flex-col outline-none">
            {rules.length === 0 ? (
              <div className="flex flex-1 flex-col justify-center gap-2 p-4">
                {phase === "parsing" ? (
                  <Skeleton rows={4} className="p-0" />
                ) : (
                  <>
                    <p className="text-[14px] font-bold leading-5 text-foreground">Nothing to confirm yet.</p>
                    <p className="max-w-[52ch] text-[13px] leading-5 text-muted-foreground">
                      After step 01 the exact rules appear here, one per line, with everything that had to be assumed.
                      You can edit, remove or add rules. Nothing is tested until you confirm.
                    </p>
                  </>
                )}
              </div>
            ) : (
              <>
                {name && (
                  <div className="flex items-baseline justify-between gap-3 border-b border-border px-3 py-2">
                    <h3 className="min-w-0 truncate text-[13px] font-bold leading-5 text-foreground">{name}</h3>
                    <span className="m-num shrink-0 text-[11px] text-muted-foreground">
                      {rules.length} {rules.length === 1 ? "rule" : "rules"}
                    </span>
                  </div>
                )}
                <ol className="divide-y divide-border">
                  {rules.map((r, i) => (
                    <li key={r.id} className="flex items-start gap-2 px-3 py-1.5">
                      <span className="m-num w-5 shrink-0 pt-[7px] text-[11px] font-bold leading-4 text-primary">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      {locked ? (
                        <p className="m-num min-w-0 flex-1 py-[5px] text-[12px] leading-5 text-foreground">{r.text}</p>
                      ) : (
                        <>
                          <div className="m-field min-w-0 flex-1">
                            <textarea
                              rows={Math.max(1, Math.ceil(r.text.length / 48))}
                              value={r.text}
                              aria-label={`Rule ${i + 1}`}
                              onChange={(e) =>
                                setRules((prev) => prev.map((x) => (x.id === r.id ? { ...x, text: e.target.value } : x)))
                              }
                              className="m-num block resize-none px-2 py-1 text-[16px] leading-5 [field-sizing:content] md:text-[12px]"
                            />
                          </div>
                          <button
                            type="button"
                            aria-label={`Remove rule ${i + 1}`}
                            onClick={() => setRules((prev) => prev.filter((x) => x.id !== r.id))}
                            className="flex h-[44px] w-[44px] shrink-0 items-center justify-center text-muted-foreground transition-colors hover:bg-bear/10 hover:text-bear md:h-[30px] md:w-[30px]"
                          >
                            <IconX size={12} />
                          </button>
                        </>
                      )}
                    </li>
                  ))}
                </ol>

                {!locked && (
                  <div className="border-t border-border px-3 py-2">
                    <button
                      type="button"
                      className="m-btn m-btn-ghost m-btn-sm min-h-[44px] md:min-h-0"
                      onClick={() => {
                        nextRuleId.current += 1;
                        setRules((prev) => [...prev, { id: `n${nextRuleId.current}`, text: "" }]);
                      }}
                    >
                      <IconPlus size={10} strokeWidth={2} /> Add rule
                    </button>
                  </div>
                )}

                {assumptions.length > 0 && (
                  <div className="border-t border-border px-3 py-2.5">
                    <div className="m-label mb-1.5 text-warn">Assumed, because your text did not say</div>
                    <ul className="space-y-1">
                      {assumptions.map((a) => (
                        <li key={a} className="flex gap-2 text-[12px] leading-[18px] text-foreground">
                          <span className="mt-[8px] h-px w-2 shrink-0 bg-warn" aria-hidden="true" />
                          {a}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-border bg-surface-1 px-3 py-2.5">
                  {locked ? (
                    <>
                      <button type="button" onClick={editRules} className="m-btn m-btn-ghost min-h-[44px] md:min-h-0">
                        Edit rules
                      </button>
                      <p className="min-w-0 flex-1 text-[12px] leading-4 text-muted-foreground">
                        Editing a rule makes it a new strategy and needs a new test.
                      </p>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => void run()}
                        className="m-btn m-btn-primary min-h-[44px] flex-1 sm:flex-none md:min-h-0"
                      >
                        <IconLock size={12} strokeWidth={2} /> Confirm and run sealed test
                      </button>
                      <p className="min-w-0 flex-1 basis-[180px] text-[12px] leading-4 text-muted-foreground">
                        These exact rules are what gets tested. Fix anything that was misread first.
                      </p>
                    </>
                  )}
                  {runError && (
                    <p role="alert" className="basis-full text-[12px] leading-4 text-bear">
                      {runError}
                    </p>
                  )}
                </div>
              </>
            )}
          </div>
        </Panel>

        {/* 03 SEALED TEST */}
        <Panel
          id="protocol"
          step="03"
          title="Sealed test"
          className="border-b border-border lg:col-start-2 lg:row-start-1"
          bodyClassName="flex flex-col"
          right={<span className="m-label hidden sm:inline">10+ years, one look</span>}
        >
          <SealedTimeline stages={stages} />
          <ol className="grid flex-1 auto-rows-fr divide-y divide-border">
            {stages.map((s, i) => (
              <li
                key={s.key}
                className={cn(
                  "grid grid-cols-[16px_20px_minmax(0,1fr)] items-center gap-x-2 px-3 py-[7px]",
                  s.state === "running" && "bg-primary/5",
                )}
              >
                <span className="flex h-5 items-center justify-center">
                  {s.state === "done" ? (
                    <IconCheck size={13} strokeWidth={2} className="text-primary" />
                  ) : s.state === "running" ? (
                    <IconSpinner size={13} strokeWidth={2} className="m-spin text-primary" />
                  ) : (
                    <span className="h-[7px] w-[7px] border border-muted-foreground" aria-hidden="true" />
                  )}
                </span>
                <span className="m-num text-[11px] font-bold leading-5 text-muted-foreground">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="min-w-0 text-[12px] leading-5">
                  <span className={cn("font-bold", s.state === "pending" ? "text-foreground" : "text-primary")}>
                    {STAGE_COPY[s.key].title}.
                  </span>{" "}
                  <span className="text-muted-foreground">{STAGE_COPY[s.key].body}</span>
                  <span className="sr-only">
                    {s.state === "done" ? " Done." : s.state === "running" ? " In progress." : " Not started."}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </Panel>

        {/* 04 VERDICT */}
        <Panel
          id="verdict"
          step="04"
          title="Verdict"
          className="border-b border-border lg:col-start-2 lg:row-start-2"
          bodyClassName="flex flex-col"
          right={verdict ? <span className="m-label hidden sm:inline">Measured, not predicted</span> : null}
        >
          <div ref={verdictRef} tabIndex={-1} className="flex flex-1 flex-col outline-none">
            {phase === "verdict" && verdict ? (
              <VerdictCard verdict={verdict} onNew={reset} />
            ) : phase === "unavailable" ? (
              <div className="flex flex-1 flex-col gap-3 p-4">
                <div className="flex items-center gap-2">
                  <span className="m-chip">Not run</span>
                  <span className="m-label">No verdict was produced</span>
                </div>
                <p className="max-w-[60ch] text-[14px] leading-[22px] text-foreground">
                  {job?.message ?? "The test could not be completed."}
                </p>
                <div className="mt-auto flex flex-wrap gap-2">
                  <button type="button" onClick={editRules} className="m-btn m-btn-ghost min-h-[44px] md:min-h-0">
                    Edit rules
                  </button>
                  <button type="button" onClick={reset} className="m-btn m-btn-ghost min-h-[44px] md:min-h-0">
                    New test
                  </button>
                </div>
              </div>
            ) : phase === "running" ? (
              <div className="flex flex-1 flex-col justify-center gap-3 p-4">
                <div className="flex items-center gap-2 text-primary">
                  <IconSpinner size={14} strokeWidth={2} className="m-spin" />
                  <span className="text-[11px] font-extrabold uppercase tracking-[0.2em]">Sealed test running</span>
                </div>
                <p className="max-w-[52ch] text-[13px] leading-5 text-muted-foreground">
                  The later years are opened once. Whatever they show is the verdict, pass or fail.
                </p>
                <Skeleton rows={3} className="p-0" />
              </div>
            ) : (
              <VerdictLegend />
            )}
          </div>
        </Panel>
      </div>

      {/* ── Library ─────────────────────────────────────────────────────── */}
      <Panel
        id="library"
        title="Tested strategies"
        right={
          library ? (
            <span className="m-num hidden text-[11px] text-muted-foreground sm:inline">{library.source}</span>
          ) : null
        }
      >
        {libraryError ? (
          <PanelError what="the tested strategies" onRetry={() => void retryLibrary()} />
        ) : !library ? (
          <Skeleton rows={4} />
        ) : (
          <>
            <VerdictTally examples={library.examples} />
            {/* Six results: 3 × 2, 2 × 3 or 1 × 6 - never a part-filled row. */}
            <ul className="grid auto-rows-fr grid-cols-1 gap-px bg-border md:grid-cols-2 xl:grid-cols-3">
              {library.examples.map((ex) => (
                <li key={ex.id} className="flex bg-surface-0">
                  <LibraryCard
                    ex={ex}
                    current={phase === "verdict" && verdict?.id === ex.id}
                    onOpen={() => openStored(ex)}
                  />
                </li>
              ))}
            </ul>
          </>
        )}
      </Panel>
    </div>
  );
}

// ─── Sealed timeline ──────────────────────────────────────────────────────────

function SealedTimeline({ stages }: { stages: LabStage[] }) {
  const state = (k: LabStageKey) => stages.find((s) => s.key === k)?.state ?? "pending";
  const select = state("select");
  const sealed = state("sealed");
  return (
    <div className="border-b border-border px-3 py-2.5" aria-hidden="true">
      <div className="grid grid-cols-[minmax(0,62fr)_minmax(0,38fr)] gap-px">
        <div
          className={cn(
            "flex h-7 items-center justify-between gap-2 border px-2",
            select === "pending" ? "border-border-strong bg-surface-2" : "border-primary/40 bg-primary/10",
          )}
          style={
            select === "pending"
              ? undefined
              : { backgroundImage: "repeating-linear-gradient(135deg, hsl(38 78% 55% / 0.12) 0 1px, transparent 1px 6px)" }
          }
        >
          <span className="truncate text-[10px] font-extrabold uppercase tracking-[0.14em] text-foreground">
            Early years
          </span>
          <span className="m-label hidden truncate sm:inline">rules picked here</span>
        </div>
        <div
          className={cn(
            "flex h-7 items-center justify-between gap-2 border px-2",
            sealed === "pending" ? "border-border-strong bg-black" : "border-primary bg-primary text-black",
          )}
        >
          <span
            className={cn(
              "flex items-center gap-1.5 truncate text-[10px] font-extrabold uppercase tracking-[0.14em]",
              sealed === "pending" ? "text-primary" : "text-black",
            )}
          >
            <IconLock size={10} strokeWidth={2} />
            {sealed === "pending" ? (
              <>
                <span className="hidden sm:inline">Later years,&nbsp;</span>sealed
              </>
            ) : sealed === "running" ? (
              "Opening once"
            ) : (
              "Opened once"
            )}
          </span>
        </div>
      </div>
      <div className="m-num mt-1 flex justify-between text-[10px] leading-4 text-muted-foreground">
        <span>start of data</span>
        <span>today</span>
      </div>
    </div>
  );
}

// ─── Verdict card ─────────────────────────────────────────────────────────────

function VerdictCard({ verdict, onNew }: { verdict: LabVerdict; onNew: () => void }) {
  const m = VERDICT_META[verdict.verdict];
  const years = verdict.years ? Object.entries(verdict.years) : [];
  const positive = years.filter(([, v]) => v > 0).length;

  const facts: { label: string; value: string }[] = [
    { label: "Symbols", value: verdict.symbols },
    { label: "Period", value: verdict.period },
  ];
  // Only numbers the lab actually recorded. Always an even count, so the
  // two-column grid has no empty cell.
  if (verdict.trades_per_day != null && years.length > 0) {
    facts.push({ label: "Trades per day", value: verdict.trades_per_day.toFixed(1) });
    facts.push({ label: "Years positive", value: `${positive} of ${years.length}` });
  }

  return (
    <article key={verdict.id} className="m-rise flex flex-1 flex-col" aria-label={`Verdict: ${verdict.verdict}`}>
      {/* Verdict band */}
      <div className={cn("relative border-b border-border px-4 py-3", m.bg)}>
        <span className={cn("absolute inset-y-0 left-0 w-[3px]", m.bar)} aria-hidden="true" />
        <div className="flex items-center gap-3">
          <m.Icon size={30} strokeWidth={1.6} className={cn("shrink-0", m.text)} />
          <div className="min-w-0">
            <p
              className={cn(
                "text-[22px] font-extrabold italic leading-7 tracking-[-0.03em] sm:text-[26px] sm:leading-8",
                m.text,
              )}
            >
              {verdict.verdict}
            </p>
            <p className="text-[12px] leading-4 text-muted-foreground">{m.gloss}</p>
          </div>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div>
          <h3 className="text-[15px] font-bold leading-5 text-foreground">{verdict.name}</h3>
          <p className="mt-1 text-[13px] leading-5 text-muted-foreground">&ldquo;{verdict.asked}&rdquo;</p>
        </div>

        <div className="border border-border-strong bg-black px-3 py-2">
          <div className="m-label">Measured</div>
          <p className="m-num mt-0.5 text-[13px] font-bold leading-5 text-foreground">{verdict.headline}</p>
        </div>

        <div className={cn("grid gap-3", years.length > 0 && "xl:grid-cols-2")}>
          <dl className="grid auto-rows-fr grid-cols-2 gap-px border border-border bg-border">
            {facts.map((f) => (
              <div key={f.label} className="min-w-0 bg-surface-1 px-3 py-2">
                <dt className="m-label">{f.label}</dt>
                <dd className="m-num mt-0.5 text-[12px] font-bold leading-[18px] text-foreground">{f.value}</dd>
              </div>
            ))}
          </dl>
          {years.length > 0 && <YearBars years={years} unit={verdict.years_unit ?? ""} />}
        </div>

        <div className="border-l border-primary bg-primary/5 px-3 py-2">
          <div className="m-label text-primary">Why</div>
          <p className="mt-0.5 text-[14px] leading-[22px] text-foreground">{verdict.why}</p>
        </div>

        <div className="mt-auto flex flex-wrap items-center justify-between gap-x-4 gap-y-2 pt-1">
          <p className="text-[12px] leading-4 text-muted-foreground">
            A measured result on past data. Information, not advice.
          </p>
          <button type="button" onClick={onNew} className="m-btn m-btn-ghost min-h-[44px] md:min-h-0">
            Test another
          </button>
        </div>
      </div>
    </article>
  );
}

function YearBars({ years, unit }: { years: [string, number][]; unit: string }) {
  const max = Math.max(...years.map(([, v]) => Math.abs(v)), 1e-9);
  return (
    <figure className="flex flex-col">
      <figcaption className="sr-only">Result in each year, {unit}</figcaption>
      <div
        className="grid flex-1 gap-px border border-border bg-border"
        style={{ gridTemplateColumns: `repeat(${years.length}, minmax(0, 1fr))` }}
      >
        {years.map(([y, v]) => (
          <div key={y} className="flex flex-col items-center bg-surface-1 px-1 pb-1.5 pt-2">
            <div className="flex h-9 w-full items-end justify-center">
              <div
                className={cn("w-full max-w-[40px]", v > 0 ? "bg-primary" : "bg-bear")}
                style={{ height: `${Math.max(6, (Math.abs(v) / max) * 100)}%` }}
              />
            </div>
            <div className={cn("m-num mt-1 text-[11px] font-bold leading-4", v > 0 ? "text-primary" : "text-bear")}>
              {v > 0 ? "+" : ""}
              {v.toFixed(3)}
            </div>
            <div className="m-num text-[10px] leading-4 text-muted-foreground">{y}</div>
          </div>
        ))}
      </div>
      <p className="m-label mt-1" aria-hidden="true">
        Each year, {unit}
      </p>
    </figure>
  );
}

/** Shown before any verdict: what the four outcomes mean. */
function VerdictLegend() {
  return (
    <div className="flex flex-1 flex-col">
      <div className="px-4 pb-3 pt-4">
        <p className="text-[14px] font-bold leading-5 text-foreground">No verdict yet.</p>
        <p className="mt-1 max-w-[60ch] text-[13px] leading-5 text-muted-foreground">
          Every test ends in one of four verdicts. Most ideas fail, and the lab says so.
        </p>
      </div>
      <dl className="grid flex-1 auto-rows-fr grid-cols-1 gap-px border-t border-border bg-border sm:grid-cols-2">
        {VERDICT_LABELS.map((v) => {
          const m = VERDICT_META[v];
          return (
            <div key={v} className="flex gap-3 bg-surface-0 px-4 py-3">
              <m.Icon size={20} strokeWidth={1.5} className={cn("mt-0.5 shrink-0", m.text)} />
              <div className="min-w-0">
                <dt className={cn("text-[11px] font-extrabold uppercase leading-4 tracking-[0.14em]", m.text)}>{v}</dt>
                <dd className="mt-1 text-[12px] leading-[18px] text-muted-foreground">{m.gloss}</dd>
              </div>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

// ─── Library ──────────────────────────────────────────────────────────────────

function VerdictTally({ examples }: { examples: LabVerdict[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-border px-3 py-2">
      <span className="m-num text-[11px] font-bold text-foreground">{examples.length} tested</span>
      {VERDICT_LABELS.map((v) => {
        const n = examples.filter((e) => e.verdict === v).length;
        const m = VERDICT_META[v];
        return (
          <span key={v} className="flex items-center gap-1.5">
            <m.Icon size={12} strokeWidth={1.6} className={m.text} />
            <span className="m-num text-[11px] font-bold text-foreground">{n}</span>
            <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">{v}</span>
          </span>
        );
      })}
      <span className="basis-full text-[12px] leading-4 text-muted-foreground lg:ml-auto lg:basis-auto">
        Failures stay in the library. That is the point.
      </span>
    </div>
  );
}

function LibraryCard({ ex, current, onOpen }: { ex: LabVerdict; current: boolean; onOpen: () => void }) {
  const m = VERDICT_META[ex.verdict];
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-pressed={current}
      className={cn(
        "group relative flex w-full flex-col gap-2 px-3 pb-2.5 pt-3 text-left transition-colors hover:bg-surface-2",
        current ? "bg-surface-2" : "bg-surface-1",
      )}
    >
      <span className={cn("absolute inset-y-0 left-0 w-[2px]", current ? m.bar : "bg-transparent")} aria-hidden="true" />
      <span className="flex w-full items-start justify-between gap-2">
        <VerdictBadge verdict={ex.verdict} />
        <span className="m-num shrink-0 text-[10px] leading-[18px] text-muted-foreground">{ex.period}</span>
      </span>
      <span className="text-[14px] font-bold leading-5 text-foreground group-hover:text-primary">{ex.name}</span>
      <span className="text-[12px] leading-[18px] text-muted-foreground">{ex.asked}</span>
      <span className="m-num mt-auto border-t border-border pt-2 text-[12px] font-bold leading-[18px] text-foreground">
        {ex.headline}
      </span>
      <span className="flex w-full items-center justify-between gap-2">
        <span className="m-num min-w-0 truncate text-[11px] leading-4 text-muted-foreground">{ex.symbols}</span>
        <span className="flex shrink-0 items-center gap-1 text-[10px] font-extrabold uppercase tracking-[0.14em] text-primary">
          {current ? "Showing" : "Open verdict"}
          {!current && <IconArrowRight size={10} strokeWidth={2} />}
        </span>
      </span>
    </button>
  );
}
