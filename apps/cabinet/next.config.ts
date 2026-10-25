import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Локальный preview в Cursor browser часто ходит на 127.0.0.1, а next dev — на localhost.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async headers() {
    return [{ source: "/:path*", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] }];
  },
};

export default nextConfig;
