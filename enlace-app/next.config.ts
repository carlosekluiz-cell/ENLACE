import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // pdfkit resolves its built-in font metrics (.afm) from node_modules at
  // runtime — keep it external so the server bundle doesn't strand them.
  serverExternalPackages: ["pdfkit"],
};

export default nextConfig;
