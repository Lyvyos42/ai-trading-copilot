/** MOCK of POST /api/v1/lab/run. See lib/mock/lab.ts. */
import { NextResponse } from "next/server";
import { RESEARCH_PUBLIC } from "@/lib/visibility";
import { mockRun } from "@/lib/mock/lab";
import type { LabRule } from "@/lib/terminal-api";

export async function POST(req: Request) {
  if (!RESEARCH_PUBLIC) return NextResponse.json({ detail: "Not found." }, { status: 404 });
  const body = await req.json().catch(() => null);
  const raw: unknown[] = Array.isArray(body?.rules) ? body.rules : [];
  const rules: LabRule[] = [];
  raw.forEach((r, i) => {
    const text = typeof (r as LabRule)?.text === "string" ? (r as LabRule).text.trim() : "";
    if (text) rules.push({ id: String((r as LabRule).id ?? `r${i + 1}`), text });
  });
  if (rules.length === 0) {
    return NextResponse.json({ detail: "Confirm at least one rule before running a test." }, { status: 422 });
  }
  return NextResponse.json({ job_id: mockRun(rules) });
}
