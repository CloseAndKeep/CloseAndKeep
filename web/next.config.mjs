/** @type {import('next').NextConfig} */
const backendUrl = process.env.BACKEND_URL?.replace(/\/$/, "");

const nextConfig = {
  async rewrites() {
    if (!backendUrl) {
      return [];
    }
    return [
      {
        source: "/__cak_api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
