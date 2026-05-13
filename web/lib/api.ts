const LOCAL_DEV_API = "http://localhost:8000";
/** Same-origin path proxied by Next to the FastAPI backend when `BACKEND_URL` is set (see `next.config.mjs`). */
const INTERNAL_PROXY_PREFIX = "/__cak_api";

/**
 * Base URL for browser `fetch` calls. Prefer `NEXT_PUBLIC_API_BASE_URL` when set; otherwise on
 * deployed hosts the app uses the internal proxy so you only need server-side `BACKEND_URL` on Vercel.
 */
export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (configured) {
    return configured;
  }
  if (typeof window === "undefined") {
    return LOCAL_DEV_API;
  }
  const { hostname, origin } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return LOCAL_DEV_API;
  }
  return `${origin}${INTERNAL_PROXY_PREFIX}`;
}

function isLocalWebHost(): boolean {
  if (typeof window === "undefined") return false;
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1";
}

/** User-facing text when fetch() fails before an HTTP response (offline, CORS, wrong URL, API down). */
export function fetchErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof TypeError && error.message === "Failed to fetch") {
    if (typeof window !== "undefined" && !isLocalWebHost()) {
      return "We could not reach the server. On Vercel, set BACKEND_URL to your API origin (or set NEXT_PUBLIC_API_BASE_URL) and redeploy; the API host may also be down.";
    }
    return "Cannot reach the API. Start the backend (port 8000 by default), set NEXT_PUBLIC_API_BASE_URL if it runs elsewhere, and ensure CORS_ORIGINS on the API includes the exact URL you use for the app (localhost vs 127.0.0.1 must match).";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}
