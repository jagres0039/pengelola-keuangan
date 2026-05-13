/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // The API is served from the same origin via nginx reverse proxy.
  // In dev, point to local FastAPI on :8000.
  async rewrites() {
    const apiTarget =
      process.env.NEXT_PUBLIC_API_PROXY_TARGET || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiTarget}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
