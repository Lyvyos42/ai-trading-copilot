/** MOCK of POST /api/v1/lab/parse. See lib/mock/lab.ts. */
import { NextResponse } from "next/server";
import { RESEARCH_PUBLIC } from "@/lib/visibility";
import { mockParse } from "@/lib/mock/lab";

export async function POST(req: Request) {
  if (!RESEARCH_PUBLIC) return NextResponse.json({ detail: "Not found." }, { status: 404 });
  const body = await req.json().catch(() => null);
  const text = typeof body?.text === "string" ? body.text.trim() : "";
  if (text.length < 12) {
    return NextResponse.json(
      { detail: "Too short to read. Describe an entry, a stop and an exit in a sentence or two." },
      { status: 422 },
    );
  }
  if (text.length > 2000) {
    return NextResponse.json({ detail: "Keep the description under 2,000 characters." }, { status: 422 });
  }
  return NextResponse.json(mockParse(text));
}
