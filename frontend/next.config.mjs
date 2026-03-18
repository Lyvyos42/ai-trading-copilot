/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000",
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          // Allow embedding from quantneuraledge.com and any vercel.app preview
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors 'self' https://quantneuraledge.com https://*.quantneuraledge.com https://*.vercel.app",
          },
          // Override Vercel's default DENY — SAMEORIGIN lets the CSP above do the work
          {
            key: "X-Frame-Options",
            value: "SAMEORIGIN",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
