/** MOCK of GET /api/v1/terminal/odds. See lib/mock/terminal.ts. */
import { NextResponse } from "next/server";
import { mockOdds } from "@/lib/mock/terminal";

export async function GET() {
  return NextResponse.json(mockOdds());
}
