import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** Must match API `SESSION_COOKIE_NAME` (default in api/app/config.py). */
const SESSION_COOKIE = "closeandkeep_session";

/**
 * Soft edge gate for protected app routes when the session cookie is first-party
 * (same-origin `/__cak_api` proxy). Skipped on localhost and when
 * `NEXT_PUBLIC_API_BASE_URL` points the browser at a cross-origin API — in those
 * setups the cookie lives on the API host and AuthGuard remains the gate.
 */
export function middleware(request: NextRequest) {
  const host = request.nextUrl.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1";
  const crossOriginApi = Boolean(process.env.NEXT_PUBLIC_API_BASE_URL);

  if (isLocal || crossOriginApi) {
    return NextResponse.next();
  }

  const session = request.cookies.get(SESSION_COOKIE)?.value;
  if (!session) {
    const login = new URL("/login", request.url);
    const next = `${request.nextUrl.pathname}${request.nextUrl.search}`;
    login.searchParams.set("next", next);
    return NextResponse.redirect(login);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard",
    "/dashboard/:path*",
    "/prospects",
    "/prospects/:path*",
    "/orders",
    "/orders/:path*",
    "/follow-ups",
    "/follow-ups/:path*",
    "/billing",
    "/billing/:path*",
    "/api-keys",
    "/api-keys/:path*",
    "/integrations",
    "/integrations/:path*",
    "/gifts",
    "/gifts/:path*",
    "/admin",
    "/admin/:path*",
  ],
};
