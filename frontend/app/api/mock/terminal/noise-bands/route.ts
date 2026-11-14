/** MOCK of GET /api/v1/terminal/noise-bands?symbol=. See lib/mock/terminal.ts. */
import { NextResponse } from "next/server";
import { mockNoiseBands } from "@/lib/mock/terminal";
import { TERMINAL_SYMBOLS, type TerminalSymbol } from "@/lib/terminal-api";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const symbol = (new URL(req.url).searchParams.get("symbol") || "USTEC").toUpperCase();
  if (!TERMINAL_SYMBOLS.includes(symbol as TerminalSymbol)) {
    return NextResponse.json(
      { detail: `Unknown symbol. Use one of: ${TERMINAL_SYMBOLS.join(", ")}.` },
      { status: 422 },
    );
  }
  return NextResponse.json(mockNoiseBands(symbol as TerminalSymbol));
}
