/** MOCK of GET /api/v1/terminal/positioning. See lib/mock/terminal.ts. */
import { NextResponse } from "next/server";
import { RESEARCH_PUBLIC } from "@/lib/visibility";
import { mockPositioning } from "@/lib/mock/terminal";

export async function GET() {
  if (!RESEARCH_PUBLIC) return NextResponse.json({ detail: "Not found." }, { status: 404 });
  return NextResponse.json(mockPositioning());
}
