import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Allow only same-origin relative paths for post-login redirects.
 * Rejects protocol-relative (`//evil.com`), absolute URLs, and backslash tricks.
 */
export function safeInternalPath(
  raw: string | null | undefined,
  fallback = "/dashboard",
): string {
  if (!raw) return fallback;
  const path = raw.trim();
  if (!path.startsWith("/") || path.startsWith("//") || path.startsWith("/\\")) {
    return fallback;
  }
  if (path.includes("://") || path.includes("\\")) {
    return fallback;
  }
  return path;
}
