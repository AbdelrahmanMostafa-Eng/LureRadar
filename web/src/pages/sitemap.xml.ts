import type { APIRoute } from "astro";
import { listDocs } from "../lib/docs";

const PAGES = ["", "radar/", "check/", "feeds/", "pc-watch/", "methodology/", "packs/", "report/", "about/", "ethics/", "privacy/", "bot/", "docs/"];

export const GET: APIRoute = ({ site }) => {
  const base = import.meta.env.BASE_URL.endsWith("/") ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`;
  const paths = [...PAGES, ...listDocs().filter((d) => d.slug !== "index").map((d) => `docs/${d.slug}/`)];
  const urls = paths.map((p) => `  <url><loc>${new URL(base + p, site).toString()}</loc></url>`).join("\n");
  const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
  return new Response(body, { headers: { "Content-Type": "application/xml; charset=utf-8" } });
};
