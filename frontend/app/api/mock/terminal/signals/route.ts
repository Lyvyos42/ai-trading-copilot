/** MOCK of GET /api/v1/terminal/signals. See lib/mock/terminal.ts. */
import { NextResponse } from "next/server";
import { mockSignals } from "@/lib/mock/terminal";

export async function GET() {
  return NextResponse.json(mockSignals());
}
