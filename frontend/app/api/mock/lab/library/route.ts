/** MOCK of GET /api/v1/lab/library: the published sealed tests. See lib/mock/lab.ts. */
import { NextResponse } from "next/server";
import { RESEARCH_PUBLIC } from "@/lib/visibility";
import { LAB_EXAMPLES, LAB_SOURCE } from "@/lib/mock/lab";

export async function GET() {
  if (!RESEARCH_PUBLIC) return NextResponse.json({ detail: "Not found." }, { status: 404 });
  // The six results are real; only the transport is mocked.
  return NextResponse.json({
    is_mock: true,
    source: LAB_SOURCE,
    as_of: "2026-11-14T00:00:00Z",
    examples: LAB_EXAMPLES,
  });
}
