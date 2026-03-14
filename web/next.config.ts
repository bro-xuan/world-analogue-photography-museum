import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: "/images/:path*",
        destination:
          "https://pub-e914a7872427409396b9b7adae62cd4f.r2.dev/images/:path*",
      },
    ];
  },
};

export default nextConfig;
