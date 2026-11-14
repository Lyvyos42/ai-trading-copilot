/** MOCK of GET /api/v1/terminal/activity-windows. See lib/mock/terminal.ts. */
import { NextResponse } from "next/server";
import { mockActivityWindows } from "@/lib/mock/terminal";

export async function GET() {
  return NextResponse.json(mockActivityWindows());
}
