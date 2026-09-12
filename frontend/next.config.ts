import type { NextConfig } from "next";

// Même origine : le navigateur appelle /api/v1/* sur Next.js, qui relaie vers FastAPI.
// Le cookie de session voyage automatiquement, sans CORS. Seul /api/v1 est relayé : la doc
// Swagger (/api/docs, dev uniquement) se consulte directement sur le port de FastAPI.
// ATTENTION : API_URL est lu au BUILD (rewrites figés par `next build`), pas au runtime.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${API_URL}/api/v1/:path*` }];
  },
};

export default nextConfig;
