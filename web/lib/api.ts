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

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    const message =
      typeof detail === "string"
        ? detail
        : detail &&
            typeof detail === "object" &&
            "message" in detail &&
            typeof (detail as { message: unknown }).message === "string"
          ? (detail as { message: string }).message
          : fallback;
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export type ApiFetchOptions = RequestInit & {
  /** Default true — session cookies for first-party / proxied API calls. */
  credentials?: RequestCredentials;
  /** Used when the response body has no usable `detail` string. */
  errorMessage?: string;
  /** Default `json`. Use `blob` or `text` for non-JSON responses. */
  responseType?: "json" | "text" | "blob";
};

/**
 * Shared JSON API client: credentials, base URL, and consistent error messages.
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const {
    errorMessage = "Request failed.",
    credentials = "include",
    responseType = "json",
    ...init
  } = options;
  const url = path.startsWith("http") ? path : `${getApiBaseUrl()}${path.startsWith("/") ? "" : "/"}${path}`;

  let response: Response;
  try {
    response = await fetch(url, { ...init, credentials });
  } catch (error) {
    throw new Error(fetchErrorMessage(error, errorMessage));
  }

  if (!response.ok) {
    let detail: unknown = null;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = body.detail ?? null;
    } catch {
      detail = null;
    }
    throw new ApiError(response.status, detail, errorMessage);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (responseType === "blob") {
    return (await response.blob()) as T;
  }

  const text = await response.text();
  if (!text) {
    return undefined as T;
  }

  if (responseType === "text") {
    return text as T;
  }

  return JSON.parse(text) as T;
}
