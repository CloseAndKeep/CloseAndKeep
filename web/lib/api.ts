export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function isLocalWebHost(): boolean {
  if (typeof window === "undefined") return false;
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1";
}

/** User-facing text when fetch() fails before an HTTP response (offline, CORS, wrong URL, API down). */
export function fetchErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof TypeError && error.message === "Failed to fetch") {
    if (typeof window !== "undefined" && !isLocalWebHost()) {
      return "We could not reach the server. The site may be missing a configured API URL, the API may be down, or access may be blocked. Please try again later.";
    }
    return "Cannot reach the API. Start the backend (port 8000 by default), set NEXT_PUBLIC_API_BASE_URL if it runs elsewhere, and ensure CORS_ORIGINS on the API includes the exact URL you use for the app (localhost vs 127.0.0.1 must match).";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}
