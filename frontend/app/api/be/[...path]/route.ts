/** Same-origin proxy to the backend, for clients that block cross-origin writes.
 *
 *  WHY THIS EXISTS
 *
 *  Measured against production on 2026-09-05, from the browser that was
 *  failing, at the same moment and on the same page:
 *
 *    GET    /api/v1/signals?limit=50   -> 200, panel populated
 *    DELETE /api/v1/signals/reset      -> never left the client
 *    POST   /api/v1/signals/reset      -> never left the client
 *
 *  And from outside that browser, with a full Chrome header set, Origin,
 *  Referer and sec-fetch-*:
 *
 *    preflight OPTIONS (DELETE)        -> 200, allow-methods includes DELETE
 *    DELETE /api/v1/signals/reset      -> 401 in 0.30s
 *    POST   /api/v1/signals/reset      -> 401 in 0.30s
 *
 *  So the server, Cloudflare and CORS all permit the request; the client
 *  drops it. Once POST failed as well as DELETE it stopped being about the
 *  verb: reads pass and WRITES are blocked. That is what privacy extensions
 *  and endpoint-security web shields do to CROSS-ORIGIN state-changing
 *  requests, as a blunt anti-CSRF measure. The page is served from
 *  app.quantneuraledge.com and the API lives on onrender.com, so every write
 *  the app makes is cross-origin.
 *
 *  We do not control the user's browser and neither will our customers'
 *  browsers be under our control, so the fix is to stop making cross-origin
 *  writes. A request to /api/be/... is same-origin, and Next forwards it
 *  server-side where no extension is watching.
 *
 *  NOT AN OPEN RELAY: the destination is pinned to NEXT_PUBLIC_API_URL. Only
 *  the path is taken from the caller, and it is rejected unless it starts
 *  with /api/, so this cannot be pointed at an arbitrary host.
 */
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Render's free tier can take ~50s to wake. Vercel's function limit is lower
// than that on some plans, so this is capped just under a typical 60s ceiling
// and returns a truthful message rather than a platform error page.
const UPSTREAM_TIMEOUT_MS = 55_000;

async function forward(req: NextRequest, path: string[]) {
  const suffix = "/" + (path || []).join("/");
  if (!suffix.startsWith("/api/")) {
    return NextResponse.json({ detail: "Only /api/ paths may be proxied." }, { status: 400 });
  }

  const target = `${API_URL}${suffix}${req.nextUrl.search}`;

  // Forward only what the API needs. Hop-by-hop headers and the browser's
  // own Host/Origin must not be replayed upstream.
  const headers = new Headers();
  const auth = req.headers.get("authorization");
  if (auth) headers.set("authorization", auth);
  const ctype = req.headers.get("content-type");
  if (ctype) headers.set("content-type", ctype);
  headers.set("accept", req.headers.get("accept") || "application/json");

  const method = req.method.toUpperCase();
  const hasBody = !["GET", "HEAD"].includes(method);
  let body: string | undefined;
  if (hasBody) {
    const raw = await req.text();
    if (raw) body = raw;
  }

  try {
    const res = await fetch(target, {
      method,
      headers,
      body,
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      cache: "no-store",
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: {
        "content-type": res.headers.get("content-type") || "application/json",
        "cache-control": "no-store",
      },
    });
  } catch (err) {
    const detail = err instanceof Error && err.name === "TimeoutError"
      ? `The API did not respond within ${UPSTREAM_TIMEOUT_MS / 1000}s. `
        + `It may be waking from sleep - try again in a moment.`
      : `Could not reach the API from the server: `
        + `${err instanceof Error ? err.message : String(err)}`;
    return NextResponse.json({ detail }, { status: 502 });
  }
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
