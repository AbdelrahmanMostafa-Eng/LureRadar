// LureRadar site configuration.
// The canonical public URL is defined here and in src/lureradar/config.py
// (a Python test keeps the two in sync). Override at build time with
// LURERADAR_BASE_URL, e.g. for a custom domain or local audits.
import { defineConfig } from "astro/config";

const DEFAULT_BASE_URL = "https://lureradar.vercel.app/";

const raw = (process.env.LURERADAR_BASE_URL || DEFAULT_BASE_URL).trim();
const url = new URL(raw.endsWith("/") ? raw : `${raw}/`);

export default defineConfig({
  site: url.origin,
  base: url.pathname,
  trailingSlash: "always",
  output: "static",
  build: { format: "directory", inlineStylesheets: "always" },
  compressHTML: true,
  devToolbar: { enabled: false },
});
