import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname),
  // next lint + mismatched eslint-config-next currently fails; typecheck covers CI.
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
