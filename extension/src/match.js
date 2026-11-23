// Pure helpers shared by the background worker, the pages and the tests.
// No network, no browser APIs.

/** Lowercase hostname without a trailing dot, or "" if the URL is not http(s). */
export function hostOf(url) {
  try {
    const u = new URL(url);
    if (u.protocol !== "http:" && u.protocol !== "https:") return "";
    return u.hostname.replace(/\.$/, "").toLowerCase();
  } catch {
    return "";
  }
}

/** The host and each parent domain: a.b.example.test -> [a.b.example.test, b.example.test, example.test]. */
export function candidates(host) {
  const labels = host.split(".").filter(Boolean);
  const out = [];
  for (let i = 0; i < labels.length - 1; i++) out.push(labels.slice(i).join("."));
  return out;
}

/** Return the listed indicator for a host, or null. `index` maps domain -> entry. */
export function lookup(index, host) {
  if (!host) return null;
  for (const c of candidates(host)) {
    if (Object.prototype.hasOwnProperty.call(index, c)) return index[c];
  }
  return null;
}

const RANK = { clear: 0, suspicious: 1, likely: 2, confirmed: 3 };

/** Build a compact lookup index from a LureRadar feed document. */
export function buildIndex(doc, minTier = "likely") {
  const index = {};
  for (const ind of doc.indicators ?? []) {
    if (ind.status && ind.status !== "active") continue;
    if ((RANK[ind.tier] ?? -1) < RANK[minTier]) continue;
    index[ind.domain.toLowerCase()] = {
      domain: ind.domain,
      tier: ind.tier,
      score: ind.score,
      signals: (ind.signals ?? []).filter((s) => s.weight > 0).slice(0, 4).map((s) => s.explanation),
      dispute: ind.dispute_url ?? "",
    };
  }
  return index;
}

/** Defang for display: https://a.b -> hxxps://a[.]b (dots in the host only). */
export function defang(url) {
  const m = /^(https?):\/\/([^/?#]*)(.*)$/i.exec(url);
  if (!m) return url.replace(/\./g, "[.]");
  const scheme = m[1].toLowerCase() === "https" ? "hxxps" : "hxxp";
  return `${scheme}://${m[2].replace(/\./g, "[.]")}${m[3]}`;
}
