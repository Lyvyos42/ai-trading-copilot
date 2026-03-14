import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const response = NextResponse.next();
  // Allow embedding from quantneuraledge.com (and Vercel previews)
  response.headers.set(
    "Content-Security-Policy",
    "frame-ancestors 'self' https://quantneuraledge.com https://*.quantneuraledge.com https://*.vercel.app"
  );
  response.headers.set("X-Frame-Options", "SAMEORIGIN");
  return response;
}

export const config = { matcher: "/(.*)" };
