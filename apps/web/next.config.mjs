import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);

/** @type {import("next").NextConfig} */
const nextConfig = {
  devIndicators: false,
  turbopack: {
    root: projectRoot,
  },
};

export default nextConfig;
