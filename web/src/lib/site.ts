// Build-time helpers shared by every page. Data comes from
// src/data/generated/*.json (scripts/build_site_data.py). import.meta.glob
// keeps the build working (with intentional empty states) when a file is missing.
import type { Tier } from "./checker";

const files = import.meta.glob("../data/generated/*.json", { eager: true, import: "default" }) as Record<string, unknown>;
function load<T>(name: string, fallback: T): T {
  return (files[`../data/generated/${name}.json`] as T | undefined) ?? fallback;
}

export interface FeedSignal { id: string; weight: number; explanation: string; evidence?: string[]; category?: string; live?: boolean }
export interface FeedIndicator {
  domain: string; url: string | null; tier: Tier; score: number; first_seen: string; last_seen: string;
  status: string; sources: string[]; packs: string[]; signals: FeedSignal[]; dispute_url: string;
}
export interface FeedDoc { generated_at?: string; schema_version?: string; count?: number; indicators: FeedIndicator[] }
export interface Stats {
  generated_at?: string; count?: number; active_listed?: number; suspicious?: number; stale?: number;
  new_24h?: number; new_7d?: number; by_tier?: Record<string, number>; by_source?: Record<string, number>;
  top_signals?: { id: string; count: number }[];
}
export interface Meta { demo: boolean; demo_note: string; generated_at?: string; version: string; repo_url: string; built_at?: string }

export const meta = load<Meta>("meta", { demo: true, demo_note: "No data generated yet", version: "0.1.0", repo_url: "https://github.com/AbdelrahmanMostafa-Eng/LureRadar" });
export const latest = load<FeedDoc>("latest", { indicators: [] });
export const all = load<FeedDoc>("all", { indicators: [] });
export const stats = load<Stats>("stats", {});
export const pcwatch = load<Record<string, any>>("pc-watch", {});
export const packs = load<any[]>("packs", []);
export const signalsDoc = load<{ id: string; title: string; weight: string; description: string }[]>("signals", []);
export const methodology = load<Record<string, any> | null>("methodology", null);
export const docsIndex = load<{ slug: string; file: string; title: string }[]>("docs", []);

export const base = import.meta.env.BASE_URL.endsWith("/") ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`;
export const href = (path = ""): string => base + path.replace(/^\//, "");
export const abs = (path = ""): string => new URL(href(path), import.meta.env.SITE).toString();
export const REPO_URL = meta.repo_url;
export function issueUrl(template: string, title?: string): string {
  return `${REPO_URL}/issues/new?template=${template}${title ? `&title=${encodeURIComponent(title)}` : ""}`;
}

export function defang(value: string): string {
  const text = (value || "").trim();
  const m = /^([a-z][a-z0-9+.-]*):\/\/([^/?#]*)(.*)$/i.exec(text);
  const host = (h: string) => h.replaceAll(".", "[.]");
  if (m) {
    const scheme = m[1].toLowerCase() === "https" ? "hxxps" : m[1].toLowerCase() === "http" ? "hxxp" : m[1];
    return `${scheme}://${host(m[2])}${m[3]}`;
  }
  const i = text.indexOf("/");
  return i === -1 ? host(text) : `${host(text.slice(0, i))}${text.slice(i)}`;
}

export function fmtUtc(iso?: string | null): string {
  if (!iso) return "never";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return `${d.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}
export const fmtDate = (iso?: string | null): string => (iso ? String(iso).slice(0, 10) : "unknown");

export const TIER_LABEL: Record<string, string> = { clear: "Clear", suspicious: "Suspicious", likely: "Likely lure", confirmed: "Confirmed lure" };
export const TIER_COLOR: Record<string, string> = { clear: "var(--radar)", suspicious: "var(--amber)", likely: "var(--danger)", confirmed: "var(--danger)" };

export const weightClass = (w: number): string => (w >= 20 ? "w-pos" : w > 0 ? "w-mid" : w < 0 ? "w-neg" : "w-zero");
export const signed = (w: number): string => (w > 0 ? `+${w}` : String(w));

/** JSON safe to embed in <script type="application/json">. */
export const safeJson = (data: unknown): string => JSON.stringify(data).replace(/</g, "\\u003c");

/** Deterministic angle (0-360) and radius (0.25-0.92) for a domain on the radar. */
export function polar(domain: string): { angle: number; r: number } {
  let h = 2166136261;
  for (const ch of domain) {
    h ^= ch.codePointAt(0)!;
    h = Math.imul(h, 16777619) >>> 0;
  }
  return { angle: h % 360, r: 0.28 + ((h >>> 9) % 640) / 1000 };
}

export const NAV = [
  { path: "", label: "Home" },
  { path: "radar/", label: "Radar" },
  { path: "check/", label: "Check a link" },
  { path: "feeds/", label: "Blocklists" },
  { path: "pc-watch/", label: "PC Watch" },
  { path: "methodology/", label: "Methodology" },
  { path: "packs/", label: "Packs" },
  { path: "docs/", label: "Docs" },
  { path: "report/", label: "Report" },
  { path: "about/", label: "About" },
];
/** The few destinations shown in the desktop header; the rest live in the menu and footer. */
export const PRIMARY_NAV = ["radar/", "feeds/", "pc-watch/", "methodology/", "docs/"].map(
  (path) => NAV.find((n) => n.path === path)!,
);
