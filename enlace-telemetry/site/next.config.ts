import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep the native Postgres client out of the bundle; load it at runtime.
  serverExternalPackages: ["pg"],
};

export default nextConfig;
