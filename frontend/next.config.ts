import type { NextConfig } from "next";

// Même origine : le navigateur appelle /api/* sur Next.js, qui relaie vers FastAPI.
// Le cookie de session voyage automatiquement, sans CORS.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
