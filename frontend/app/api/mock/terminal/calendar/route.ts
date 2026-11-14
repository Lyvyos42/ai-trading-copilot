/** MOCK of GET /api/v1/terminal/calendar. See lib/mock/terminal.ts. */
import { NextResponse } from "next/server";
import { mockCalendar } from "@/lib/mock/terminal";

export async function GET() {
  return NextResponse.json(mockCalendar());
}
