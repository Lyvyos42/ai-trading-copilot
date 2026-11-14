/** MOCK of GET /api/v1/terminal/positioning. See lib/mock/terminal.ts. */
import { NextResponse } from "next/server";
import { mockPositioning } from "@/lib/mock/terminal";

export async function GET() {
  return NextResponse.json(mockPositioning());
}
