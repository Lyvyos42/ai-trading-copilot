/** MOCK of GET /api/v1/lab/{id}. See lib/mock/lab.ts. */
import { NextResponse } from "next/server";
import { mockJob } from "@/lib/mock/lab";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  const job = mockJob(params.id);
  if (!job) return NextResponse.json({ detail: "Unknown job id." }, { status: 404 });
  return NextResponse.json(job);
}
