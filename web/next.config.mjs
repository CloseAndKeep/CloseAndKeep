/** @type {import('next').NextConfig} */

/**
 * BACKEND_URL must be an absolute origin (e.g. https://api.example.com) or Next throws
 * "Invalid rewrite" at build time. Values like api.example.com (no scheme) fail.
 */
function readBackendOrigin() {
  let raw = process.env.BACKEND_URL?.trim();
  if (!raw) {
    return "";
  }
  if (
    (raw.startsWith('"') && raw.endsWith('"')) ||
    (raw.startsWith("'") && raw.endsWith("'"))
  ) {
    raw = raw.slice(1, -1).trim();
  }
  const normalized = raw.replace(/\/$/, "");
  try {
    const u = new URL(normalized);
    if (u.protocol !== "http:" && u.protocol !== "https:") {
      throw new Error("URL must use http or https");
    }
    if (u.pathname !== "/" || u.search || u.hash) {
      throw new Error("Use the API origin only (no path, query, or fragment)");
    }
    return normalized;
  } catch (cause) {
    throw new Error(
      `Invalid BACKEND_URL "${raw}". Set a full origin such as https://api.yourdomain.com (include https://, no trailing slash, no /path).`,
      { cause },
    );
  }
}

const backendOrigin = readBackendOrigin();

const nextConfig = {
  async rewrites() {
    if (!backendOrigin) {
      return [];
    }
    return [
      {
        source: "/__cak_api/:path*",
        destination: `${backendOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
