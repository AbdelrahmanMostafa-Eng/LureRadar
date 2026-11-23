// LureRadar client-side checker: a faithful port of the Python OFFLINE engine
// (src/lureradar/scoring/engine.py and detectors/*) for URLs, domains and
// messages. It runs entirely in the browser. Rules are exported from the
// Python packages by scripts/build_site_data.py, and web/scripts/parity.mjs
// asserts that this port returns the same score and tier as Python on every
// parity case. Nothing a user types is ever sent anywhere.

export type Tier = "clear" | "suspicious" | "likely" | "confirmed";
export type Kind = "url" | "domain" | "text";

export interface Signal {
  id: string;
  weight: number;
  explanation: string;
  category: string;
  evidence: string[];
}

export interface Verdict {
  input: string;
  kind: Kind;
  target: string;
  host: string | null;
  registrable: string | null;
  score: number;
  tier: Tier;
  signals: Signal[];
  allowlisted: boolean;
  platform: boolean;
  urls: Verdict[];
  listed: { tier: Tier; score: number } | null;
}

interface KeywordRule {
  term: string;
  pattern: string;
  needsRightBoundary: boolean;
}
interface BrandRule {
  name: string;
  label: string;
  aliases: string[];
  official: string[];
  officialLabels: string[];
}
interface PackRules {
  id: string;
  name: string;
  subject: string;
  keywords: KeywordRule[];
  keywordsCompact: string[];
  intents: string[];
  acquisition: string[];
  platformTerms: string[];
  unreleased: Record<string, string[]>;
  platformLabels: Record<string, string>;
  factNotes: Record<string, string>;
  brandTokens: Record<string, string>;
  brands: BrandRule[];
  officialDomains: string[];
  vocabulary: string[];
  multiword: string[];
  maxWord: number;
  outlets: string[];
  platforms: string[];
  releaseStorefronts: string[];
  factsAsOf: string | null;
  pcRelease: { status: string; claim: string; as_of: string; sources: string[] } | null;
}
export interface Rules {
  version: string;
  packs: PackRules[];
  baseOutlets: string[];
  basePlatforms: string[];
  abusedTlds: string[];
  shorteners: string[];
  sharedHosts: string[];
  reservedTlds: string[];
  selfAcquiring: string[];
  filler: string[];
  lookalikes: [string, string][];
  skeleton: Record<string, string>;
  psl: { rules: string[]; wildcards: string[]; exceptions: string[]; private: string[] };
  weights: Record<string, number>;
  tiers: { suspicious: number; likely: number; confirmed: number };
  text: {
    patterns: Record<string, string>;
    brandPattern: string | null;
    reassuranceBefore: string;
    reassuranceAfter: string;
  };
}

export interface Snapshot {
  lookup(domain: string): { tier: Tier; score: number } | null;
}

const TIER_RANK: Record<Tier, number> = { clear: 0, suspicious: 1, likely: 2, confirmed: 3 };
export const tierRank = (t: Tier): number => TIER_RANK[t];

// ------------------------------------------------------------------ defang
export function refang(value: string): string {
  let t = value.trim();
  t = t.replace(/\[\s*:\s*\/\s*\/\s*\]/g, "://");
  t = t.replace(/\[\s*:\/\/\s*\]/g, "://");
  t = t.replace(/\b(h)xx(ps?)(?=(?:\[:\]|:)\/\/|\[:\/\/\])/gi, "$1tt$2");
  t = t.replace(/\b(h)xx(ps?)\b/gi, "$1tt$2");
  t = t.replace(/\bfxp(?=:\/\/)/gi, "ftp");
  t = t.replace(/[\[\(\{]\s*(?:\.|dot)\s*[\]\)\}]/gi, ".");
  t = t.replace(/\\\./g, ".");
  t = t.replace(/[\[\(\{]\s*:\s*[\]\)\}]/g, ":");
  t = t.replace(/[\[\(\{]\s*\/\s*[\]\)\}]/g, "/");
  t = t.replace(/[\[\(\{]\s*(?:@|at)\s*[\]\)\}]/gi, "@");
  return t;
}

const defangHost = (h: string): string => h.replaceAll("[.]", ".").replaceAll(".", "[.]");

export function defang(value: string): string {
  const text = value.trim();
  if (!text) return text;
  const m = /^([a-zA-Z][a-zA-Z0-9+.-]*):\/\//.exec(text);
  if (m) {
    let scheme = m[1];
    const rest = text.slice(m[0].length);
    const low = scheme.toLowerCase();
    if (low === "http" || low === "https") {
      scheme = scheme[0] + (scheme[1] === scheme[1].toUpperCase() ? "XX" : "xx") + scheme.slice(3);
    } else if (low === "ftp") {
      scheme = scheme[0] + (scheme[1] === scheme[1].toUpperCase() ? "X" : "x") + scheme.slice(2);
    }
    let cut = rest.length;
    for (const sep of ["/", "?", "#"]) {
      const i = rest.indexOf(sep);
      if (i !== -1) cut = Math.min(cut, i);
    }
    let authority = rest.slice(0, cut);
    const tail = rest.slice(cut);
    const at = authority.lastIndexOf("@");
    if (at !== -1) authority = `${authority.slice(0, at)}[@]${defangHost(authority.slice(at + 1))}`;
    else authority = defangHost(authority);
    return `${scheme}://${authority}${tail}`;
  }
  const slash = text.indexOf("/");
  if (slash !== -1) return `${defangHost(text.slice(0, slash))}/${text.slice(slash + 1)}`;
  return defangHost(text);
}

// ------------------------------------------------------------ punycode
const BASE = 36, TMIN = 1, TMAX = 26, SKEW = 38, DAMP = 700, IBIAS = 72, IN = 128;

function adapt(delta: number, numPoints: number, first: boolean): number {
  let d = first ? Math.floor(delta / DAMP) : delta >> 1;
  d += Math.floor(d / numPoints);
  let k = 0;
  while (d > ((BASE - TMIN) * TMAX) >> 1) {
    d = Math.floor(d / (BASE - TMIN));
    k += BASE;
  }
  return k + Math.floor(((BASE - TMIN + 1) * d) / (d + SKEW));
}

function punyDecode(input: string): string | null {
  const out: number[] = [];
  let i = 0, n = IN, bias = IBIAS;
  const b = input.lastIndexOf("-");
  for (let j = 0; j < Math.max(b, 0); j++) {
    if (input.charCodeAt(j) >= 0x80) return null;
    out.push(input.charCodeAt(j));
  }
  for (let idx = b > 0 ? b + 1 : 0; idx < input.length; ) {
    const oldi = i;
    for (let w = 1, k = BASE; ; k += BASE) {
      if (idx >= input.length) return null;
      const c = input.charCodeAt(idx++);
      const digit = c - 48 < 10 ? c - 22 : c - 65 < 26 ? c - 65 : c - 97 < 26 ? c - 97 : BASE;
      if (digit >= BASE) return null;
      i += digit * w;
      const t = k <= bias ? TMIN : k >= bias + TMAX ? TMAX : k - bias;
      if (digit < t) break;
      w *= BASE - t;
    }
    bias = adapt(i - oldi, out.length + 1, oldi === 0);
    n += Math.floor(i / (out.length + 1));
    i %= out.length + 1;
    out.splice(i++, 0, n);
  }
  return String.fromCodePoint(...out);
}

export function toUnicodeHost(host: string): string {
  return host
    .split(".")
    .map((l) => (l.startsWith("xn--") ? (punyDecode(l.slice(4)) ?? l) : l))
    .join(".");
}

function toAsciiHost(host: string): string {
  const h = host.trim().replace(/\.+$/, "").toLowerCase();
  if (!h) return "";
  if (/^[\x00-\x7f]*$/.test(h)) return h;
  try {
    return new URL(`http://${h}/`).hostname;
  } catch {
    return "";
  }
}

// ---------------------------------------------------------------- types
interface Target {
  raw: string;
  kind: Kind;
  url: string | null;
  host: string;
  unicodeHost: string;
  registrable: string;
  label: string;
  subdomain: string;
  suffix: string;
  path: string;
  isIp: boolean;
  isPrivateSuffix: boolean;
}

class TargetError extends Error {}

const isIPv4 = (s: string): boolean =>
  /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.test(s) &&
  s.split(".").every((p) => Number(p) <= 255 && String(Number(p)) === p);
const isIPv6 = (s: string): boolean => {
  if (!s.includes(":") || !/^[0-9a-f:.]+$/i.test(s)) return false;
  try {
    new URL(`http://[${s}]/`);
    return true;
  } catch {
    return false;
  }
};
const isIp = (s: string): boolean => isIPv4(s) || isIPv6(s.replace(/^\[|\]$/g, ""));

interface Compiled {
  pack: PackRules;
  keywords: { term: string; re: RegExp; needsRightBoundary: boolean }[];
  intents: Set<string>;
  acquisition: Set<string>;
  platformTerms: Set<string>;
  unreleased: [string, Set<string>][];
  brandTokens: Map<string, string>;
  vocabulary: Set<string>;
  multiword: Set<string>;
  vocabList: string[];
  officialDomains: Set<string>;
  targets: Map<string, Map<string, string>>;
  segCache: Map<string, [string[], number]>;
}

const compact = (t: string): string => t.toLowerCase().replace(/[^a-z0-9]/g, "");
const tokenize = (t: string): string[] => t.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
const isAlpha = (ch: string): boolean => /\p{L}/u.test(ch);

/** Translate a Python regex (as exported) to a JS RegExp with the same meaning on ASCII text. */
function pyRe(pattern: string, flags: string): RegExp {
  return new RegExp(pattern.replace(/\[\\W_\]/g, "[^\\p{L}\\p{N}]"), flags.includes("u") ? flags : `${flags}u`);
}

export function createChecker(rules: Rules) {
  const W = rules.weights;
  const filler = new Set(rules.filler);
  const abused = new Set(rules.abusedTlds);
  const shortenersSet = new Set(rules.shorteners);
  const reserved = new Set(rules.reservedTlds);
  const selfAcq = new Set(rules.selfAcquiring);
  const pslRules = new Set(rules.psl.rules);
  const pslWild = new Set(rules.psl.wildcards);
  const pslExc = new Set(rules.psl.exceptions);
  const shared = [...rules.sharedHosts].sort((a, b) => b.length - a.length);

  // ------------------------------------------------------------ PSL / split
  const pslPrivate = new Set(rules.psl.private);
  /** Longest matching PSL rule (exceptions and wildcards honoured): [suffix, isPrivate]. */
  function pslMatch(host: string): [string, boolean] {
    const labels = host.split(".");
    for (let i = 0; i < labels.length; i++) {
      const cand = labels.slice(i).join(".");
      if (pslExc.has(cand)) return [labels.slice(i + 1).join("."), pslPrivate.has(`!${cand}`)];
      if (pslRules.has(cand)) return [cand, pslPrivate.has(cand)];
      const parent = labels.slice(i + 1).join(".");
      if (i + 1 < labels.length && pslWild.has(parent)) return [cand, pslPrivate.has(`*.${parent}`)];
    }
    return ["", false];
  }
  const pslSuffix = (host: string): string => pslMatch(host)[0];

  function splitHost(h: string): [string, string, string, boolean] {
    const labels = h.split(".");
    for (const extra of shared) {
      if (h.endsWith(`.${extra}`) && h !== extra) {
        const head = h.slice(0, -extra.length - 1).split(".");
        return [head.slice(0, -1).join("."), head[head.length - 1], extra, true];
      }
    }
    const [suffix, priv] = pslMatch(h);
    if (suffix) {
      const rest = h === suffix ? [] : h.slice(0, -suffix.length - 1).split(".");
      const label = rest.length ? rest[rest.length - 1] : "";
      const sub = rest.slice(0, -1).join(".");
      return [sub, label, suffix, priv];
    }
    if (labels.length < 2) return ["", h, "", false];
    return [labels.slice(0, -2).join("."), labels[labels.length - 2], labels[labels.length - 1], false];
  }

  function hasKnownSuffix(host: string): boolean {
    if (pslSuffix(host)) return true;
    return reserved.has(host.split(".").pop()!.toLowerCase());
  }

  // --------------------------------------------------------------- parsing
  function urlsplit(url: string) {
    const m = /^([a-zA-Z][a-zA-Z0-9+.-]*):\/\/(.*)$/s.exec(url);
    if (!m) throw new TargetError("bad url");
    const scheme = m[1].toLowerCase();
    let rest = m[2];
    const hashAt = rest.indexOf("#");
    if (hashAt !== -1) rest = rest.slice(0, hashAt);
    let cut = rest.length;
    for (const sep of ["/", "?"]) {
      const i = rest.indexOf(sep);
      if (i !== -1) cut = Math.min(cut, i);
    }
    const netloc = rest.slice(0, cut);
    let pathq = rest.slice(cut);
    let query = "";
    const q = pathq.indexOf("?");
    if (q !== -1) {
      query = pathq.slice(q + 1);
      pathq = pathq.slice(0, q);
    }
    const hostport = netloc.includes("@") ? netloc.slice(netloc.lastIndexOf("@") + 1) : netloc;
    let hostname = hostport;
    let port: string | null = null;
    if (hostport.startsWith("[")) {
      const end = hostport.indexOf("]");
      hostname = hostport.slice(1, end);
      const after = hostport.slice(end + 1);
      if (after.startsWith(":")) port = after.slice(1);
    } else if (hostport.includes(":")) {
      hostname = hostport.slice(0, hostport.lastIndexOf(":"));
      port = hostport.slice(hostport.lastIndexOf(":") + 1);
    }
    if (port !== null && port !== "" && (!/^\d+$/.test(port) || Number(port) > 65535)) {
      throw new TargetError("bad port");
    }
    return { scheme, hostname: hostname.toLowerCase(), port: port || null, path: pathq, query };
  }

  function parseTarget(raw: string): Target {
    if (raw.length > 20000) throw new TargetError("input too long");
    const text = refang(raw);
    if (!text) throw new TargetError("empty target");
    const blank: Target = {
      raw, kind: "text", url: null, host: "", unicodeHost: "", registrable: "", label: "",
      subdomain: "", suffix: "", path: "", isIp: false, isPrivateSuffix: false,
    };
    if (/\s/.test(text) || (!text.includes(".") && !text.includes("://") && !isIp(text))) return blank;
    let kind: Kind = "url";
    let urlText = text;
    if (!text.includes("://")) {
      if (/[\/?#]/.test(text)) urlText = `http://${text}`;
      else {
        kind = "domain";
        urlText = `http://${text}`;
      }
    }
    const parts = urlsplit(urlText);
    if (!["http", "https", "ftp"].includes(parts.scheme)) throw new TargetError("unsupported scheme");
    if (!parts.hostname) throw new TargetError("no hostname");
    const ip = isIp(parts.hostname);
    const asciiHost = ip ? parts.hostname.toLowerCase() : toAsciiHost(parts.hostname);
    if (!asciiHost || (!ip && !/^[a-z0-9.-]+$/.test(asciiHost))) throw new TargetError("invalid hostname");
    let path = parts.path;
    if (parts.query) path += `?${parts.query}`;
    let url: string | null = null;
    if (kind !== "domain") {
      const hostPart = ip && asciiHost.includes(":") ? `[${asciiHost}]` : asciiHost;
      const netloc = parts.port === null ? hostPart : `${hostPart}:${Number(parts.port)}`;
      url = `${parts.scheme}://${netloc}${path || "/"}`;
    }
    if (ip) {
      return { ...blank, kind, url, host: asciiHost, unicodeHost: asciiHost, registrable: asciiHost,
        label: asciiHost, path, isIp: true };
    }
    const [subdomain, label, suffix, priv] = splitHost(asciiHost);
    const registrable = label && suffix ? `${label}.${suffix}` : asciiHost;
    return {
      raw, kind, url, host: asciiHost, unicodeHost: toUnicodeHost(asciiHost), registrable, label,
      subdomain, suffix, path, isIp: false, isPrivateSuffix: priv,
    };
  }

  // ------------------------------------------------------- compiled packs
  const compiled: Compiled[] = rules.packs.map((pack) => {
    const targets = new Map<string, Map<string, string>>();
    for (const b of pack.brands) {
      const t = new Map<string, string>();
      t.set(b.name, b.label);
      for (const a of b.aliases) if (!t.has(a)) t.set(a, b.label);
      b.official.forEach((dom, i) => {
        const label = b.officialLabels[i];
        if (label.length >= 4 && !t.has(compact(label))) t.set(compact(label), `${b.label}, ${dom}`);
      });
      targets.set(b.name, t);
    }
    return {
      pack,
      keywords: pack.keywords.map((k) => ({
        term: k.term,
        re: pyRe(k.pattern, "gi"),
        needsRightBoundary: k.needsRightBoundary,
      })),
      intents: new Set(pack.intents),
      acquisition: new Set(pack.acquisition),
      platformTerms: new Set(pack.platformTerms),
      unreleased: Object.entries(pack.unreleased).map(([k, v]) => [k, new Set(v)] as [string, Set<string>]),
      brandTokens: new Map(Object.entries(pack.brandTokens)),
      vocabulary: new Set(pack.vocabulary),
      multiword: new Set(pack.multiword ?? []),
      vocabList: pack.vocabulary.filter((w) => w.length > 1),
      officialDomains: new Set(pack.officialDomains),
      targets,
      segCache: new Map(),
    };
  });

  // --------------------------------------------------------------- lexical
  function findKeywords(text: string, c: Compiled): [string, number, number][] {
    const lowered = text.toLowerCase();
    const spans: [string, number, number][] = [];
    for (const kp of c.keywords) {
      kp.re.lastIndex = 0;
      let m: RegExpExecArray | null;
      while ((m = kp.re.exec(lowered)) !== null) {
        if (m[0].length === 0) {
          kp.re.lastIndex++;
          continue;
        }
        const end = m.index + m[0].length;
        if (kp.needsRightBoundary && end < lowered.length && isAlpha(lowered[end])) {
          const rest = lowered.slice(end);
          if (!c.vocabList.some((w) => rest.startsWith(w))) continue;
        }
        spans.push([kp.term, m.index, end]);
      }
    }
    spans.sort((a, b) => a[1] - b[1] || b[2] - b[1] - (a[2] - a[1]));
    const kept: [string, number, number][] = [];
    for (const s of spans) {
      if (kept.length && s[1] < kept[kept.length - 1][2]) continue;
      kept.push(s);
    }
    return kept;
  }

  function segment(token: string, c: Compiled): [string[], number] {
    const cached = c.segCache.get(token);
    if (cached) return cached;
    const n = token.length;
    const max = c.pack.maxWord;
    const best: [number, number][] = Array.from({ length: n + 1 }, () => [n + 1, n + 1]);
    const back: [number, string | null][] = Array.from({ length: n + 1 }, () => [0, null]);
    best[0] = [0, 0];
    const less = (a: [number, number], b: [number, number]) => a[0] < b[0] || (a[0] === b[0] && a[1] < b[1]);
    for (let i = 1; i <= n; i++) {
      let cand: [number, number] = [best[i - 1][0] + 1, best[i - 1][1]];
      if (less(cand, best[i])) {
        best[i] = cand;
        back[i] = [i - 1, null];
      }
      for (let j = Math.max(0, i - max); j < i; j++) {
        const piece = token.slice(j, i);
        if (c.vocabulary.has(piece)) {
          cand = [best[j][0], best[j][1] + 1];
          if (less(cand, best[i])) {
            best[i] = cand;
            back[i] = [j, piece];
          }
        }
      }
    }
    const words: string[] = [];
    let i = n;
    while (i > 0) {
      const [j, found] = back[i];
      if (found !== null) words.push(found);
      i = j;
    }
    words.reverse();
    const out: [string[], number] = [words, n ? best[n][0] : 0];
    c.segCache.set(token, out);
    return out;
  }

  function recognisedWords(text: string, c: Compiled): string[] {
    const lowered = text.toLowerCase();
    const spans = findKeywords(lowered, c);
    let remainder = "";
    let cursor = 0;
    for (const [, start, end] of spans) {
      remainder += lowered.slice(cursor, start) + " ";
      cursor = end;
    }
    remainder += lowered.slice(cursor);
    const found: string[] = [];
    for (const token of remainder.split(/[^a-z0-9]+/)) {
      if (!token) continue;
      if (c.vocabulary.has(token)) {
        found.push(token);
        continue;
      }
      const [words, unknown] = segment(token, c);
      for (const w of words) if (w.length > 3 || unknown === 0) found.push(w);
    }
    return found;
  }

  interface Hits {
    keywords: string[];
    intents: string[];
    brands: string[];
    unreleased: [string, string[]][];
  }

  function analyse(text: string, c: Compiled): Hits {
    if (!text) return { keywords: [], intents: [], brands: [], unreleased: [] };
    const keywords = [...new Set(findKeywords(text, c).map((s) => s[0]))];
    const words = recognisedWords(text, c);
    const compactText = compact(text);
    const longEnough = (term: string): boolean => term.length >= 8 || c.multiword.has(term);
    const intents = words.filter((w) => c.intents.has(w));
    for (const i of c.pack.intents) if (longEnough(i) && compactText.includes(i) && !intents.includes(i)) intents.push(i);
    const brands = words.filter((w) => c.brandTokens.has(w));
    const unreleased: [string, string[]][] = [];
    for (const [platform, terms] of c.unreleased) {
      const hit = words.filter((w) => terms.has(w));
      for (const t of terms) if (longEnough(t) && compactText.includes(t) && !hit.includes(t)) hit.push(t);
      if (hit.length) unreleased.push([platform, [...new Set(hit)]]);
    }
    return { keywords, intents: [...new Set(intents)], brands: [...new Set(brands)], unreleased };
  }

  // ------------------------------------------------------------- skeleton
  const skelChar = (ch: string): string => {
    if (/^[\x00-\x7f]$/.test(ch)) return ch.toLowerCase();
    return rules.skeleton[ch] ?? ch;
  };
  const skeleton = (s: string): string => [...s].map(skelChar).join("");
  const asciiOnly = (s: string): string => [...s].filter((ch) => /^[\x00-\x7f]$/.test(ch)).join("");

  // ---------------------------------------------------------------- allow
  const baseOutlets = new Set(rules.baseOutlets);
  const basePlatforms = new Set(rules.basePlatforms);

  function allowState(t: Target): { outlet: boolean; platform: boolean; matched: string } {
    if (!t.registrable || t.isIp) return { outlet: false, platform: false, matched: "" };
    const outlets = new Set(baseOutlets);
    const platforms = new Set(basePlatforms);
    for (const c of compiled) {
      c.pack.outlets.forEach((d) => outlets.add(d));
      c.officialDomains.forEach((d) => outlets.add(d));
      c.pack.releaseStorefronts.forEach((d) => outlets.add(d));
      c.pack.platforms.forEach((d) => platforms.add(d));
    }
    if (outlets.has(t.registrable)) return { outlet: true, platform: false, matched: t.registrable };
    if (platforms.has(t.registrable)) return { outlet: false, platform: true, matched: t.registrable };
    return { outlet: false, platform: false, matched: "" };
  }

  // ------------------------------------------------------------ typosquat
  function deconfuse(token: string): string {
    let out = token.toLowerCase();
    for (const [src, dst] of rules.lookalikes) out = out.replaceAll(src, dst);
    return out;
  }
  const maxDistance = (target: string): number => (target.length >= 10 ? 2 : target.length >= 7 ? 1 : 0);

  function osa(a: string, b: string): number {
    const n = a.length, m = b.length;
    const d: number[][] = Array.from({ length: n + 1 }, (_, i) => Array.from({ length: m + 1 }, (_, j) => (i === 0 ? j : j === 0 ? i : 0)));
    for (let i = 1; i <= n; i++) {
      for (let j = 1; j <= m; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
      }
    }
    return d[n][m];
  }

  function typoMatch(candidate: string, target: string): { distance: number; method: string } | null {
    const cand = candidate.toLowerCase();
    if (cand === target || target.length < 4) return null;
    const deconf = deconfuse(cand);
    if (Math.abs(cand.length - target.length) > 2 && deconf.length !== target.length) return null;
    if (deconf === target) return { distance: osa(cand, target), method: "lookalike" };
    const limit = maxDistance(target);
    if (limit === 0) return null;
    if (cand.length < target.length - limit || cand.length > target.length + limit) return null;
    const dist = osa(deconf, target);
    if (dist <= limit) {
      if (deconf[0] !== target[0]) return null;
      return { distance: dist, method: "edit" };
    }
    return null;
  }

  // ------------------------------------------------------------ detectors
  interface Ctx {
    t: Target;
    allow: { outlet: boolean; platform: boolean; matched: string };
    memo: Map<string, Hits>;
  }

  function hostText(ctx: Ctx): string {
    const t = ctx.t;
    if (ctx.allow.outlet || ctx.allow.platform || t.isIp) return "";
    let owned = [t.subdomain, t.label].filter(Boolean).join(".");
    if (owned.includes("xn--")) owned = asciiOnly(skeleton(toUnicodeHost(owned)));
    return owned;
  }
  function pathText(ctx: Ctx): string {
    return pyUnquote(ctx.t.path || "");
  }
  function hostHits(ctx: Ctx, c: Compiled): Hits {
    const k = `h:${c.pack.id}`;
    if (!ctx.memo.has(k)) ctx.memo.set(k, analyse(hostText(ctx), c));
    return ctx.memo.get(k)!;
  }
  function pathHits(ctx: Ctx, c: Compiled): Hits {
    const k = `p:${c.pack.id}`;
    if (!ctx.memo.has(k)) ctx.memo.set(k, analyse(pathText(ctx), c));
    return ctx.memo.get(k)!;
  }

  const sig = (id: string, weight: number, category: string, explanation: string, evidence: string[] = []): Signal => ({
    id, weight, category, explanation, evidence,
  });

  function detectAllowlist(ctx: Ctx): Signal[] {
    if (ctx.allow.outlet) {
      return [sig("allowlisted", W.ALLOWLISTED, "trust", `${defang(ctx.allow.matched)} is allowlisted (established legitimate outlet): hard clear`)];
    }
    if (ctx.allow.platform) {
      return [sig("user_content_platform", 0, "trust", `${defang(ctx.allow.matched)} hosts user content: the domain itself is never blocklisted; only this URL is assessed (capped at SUSPICIOUS)`)];
    }
    return [];
  }

  const fmt = (xs: string[]): string => xs.map((x) => `"${x}"`).join(", ");

  function detectCombo(ctx: Ctx): Signal[] {
    let best: Signal | null = null;
    for (const c of compiled) {
      for (const [where, hits, weight] of [
        ["hostname", hostHits(ctx, c), W.KEYWORD_INTENT_COMBO_HOST],
        ["URL path", pathHits(ctx, c), W.KEYWORD_INTENT_COMBO_PATH],
      ] as [string, Hits, number][]) {
        // brand tokens ("steam", "epic") count for brand_impersonation, not again as intents
        const intents = hits.intents.filter((i) => !c.brandTokens.has(i));
        if (!(hits.keywords.length && intents.length)) continue;
        if (best && best.weight >= weight) continue;
        best = sig("keyword_intent_combo", weight, "lexical", `Keyword ${fmt(hits.keywords.slice(0, 2))} + intent ${fmt(intents.slice(0, 4))} in the ${where}`);
      }
    }
    return best ? [best] : [];
  }

  function unreleasedClaim(hits: Hits, c: Compiled): [string, string, string] | null {
    if (!hits.keywords.length || !hits.unreleased.length) return null;
    const acquisition = hits.intents.filter((i) => c.acquisition.has(i));
    for (const [platform, terms] of hits.unreleased) {
      const self = terms.filter((t) => selfAcq.has(t));
      if (acquisition.length || self.length) return [platform, terms[0], (acquisition.length ? acquisition : self)[0]];
    }
    return null;
  }

  function claimText(c: Compiled, platform: string, acq: string): string {
    const label = c.pack.platformLabels[platform] ?? platform.replace("_", " ");
    return `Promises "${acq}" of ${c.pack.subject} for ${label}: no official ${label} release exists${c.pack.factNotes[platform] ?? ""}`;
  }

  function detectClaims(ctx: Ctx): Signal[] {
    let best: Signal | null = null;
    for (const c of compiled) {
      for (const [hits, weight] of [
        [hostHits(ctx, c), W.CLAIMS_UNRELEASED_PLATFORM_HOST],
        [pathHits(ctx, c), W.CLAIMS_UNRELEASED_PLATFORM_PATH],
      ] as [Hits, number][]) {
        const claim = unreleasedClaim(hits, c);
        if (!claim || (best && best.weight >= weight)) continue;
        best = sig("claims_unreleased_platform", weight, "platform", claimText(c, claim[0], claim[2]));
      }
    }
    return best ? [best] : [];
  }

  function detectBrand(ctx: Ctx): Signal[] {
    const t = ctx.t;
    if (ctx.allow.outlet || ctx.allow.platform || t.isIp || !t.label) return [];
    const findings: { rank: number; brand: string; detail: string; kind: string }[] = [];
    for (const c of compiled) {
      if (c.officialDomains.has(t.registrable)) continue;
      let owned = [t.subdomain, t.label].filter(Boolean).join(".");
      let label = t.label;
      const idn = owned.includes("xn--");
      if (idn) {
        owned = asciiOnly(skeleton(toUnicodeHost(owned)));
        label = owned.split(".").pop()!;
      }
      const ownedCompact = compact(owned);
      const labelCompact = compact(label);
      const tokens = tokenize(owned).filter((x) => x.length >= 4);
      const segmented = new Set<string>();
      for (const tok of tokenize(owned)) {
        const [words, unknown] = segment(tok, c);
        if (unknown === 0) words.forEach((w) => segmented.add(w));
      }
      for (const [brand, targets] of c.targets) {
        if (targets.has(labelCompact)) {
          const desc = targets.get(labelCompact)!;
          findings.push({
            rank: idn ? 0 : 1, brand, kind: idn ? "confusable" : "exact",
            detail: idn ? `"${labelCompact}" spelled with look-alike Unicode (${desc})` : `brand label "${labelCompact}" (${desc}) on a non-official domain`,
          });
          continue;
        }
        let typo: (typeof findings)[number] | null = null;
        for (const [target, desc] of targets) {
          for (const cand of [...new Set([label, ...tokens])].sort()) {
            if (targets.has(cand)) continue;
            const m = typoMatch(cand, target);
            if (m && !typo) {
              const how = m.method === "lookalike" ? "look-alike characters" : "typo";
              typo = { rank: 0, brand, kind: "typosquat", detail: `"${cand}" imitates "${target}" (${desc}; ${how}, distance ${m.distance})` };
            }
          }
        }
        if (typo) {
          findings.push(typo);
          continue;
        }
        for (const [target, desc] of targets) {
          if (segmented.has(target) || (target.length >= 7 && ownedCompact.includes(target))) {
            findings.push({ rank: 2, brand, kind: "combosquat", detail: `"${target}" (${desc}) plus other words` });
            break;
          }
        }
      }
    }
    if (!findings.length) return [];
    findings.sort((a, b) => a.rank - b.rank || a.brand.localeCompare(b.brand));
    const top = findings[0];
    return [sig("brand_impersonation", W.BRAND_IMPERSONATION, "brand", `${top.kind[0].toUpperCase()}${top.kind.slice(1)}: ${top.detail}`, [defang(t.host)])];
  }

  function detectHomoglyph(ctx: Ctx): Signal[] {
    const t = ctx.t;
    if (ctx.allow.outlet || ctx.allow.platform || t.isIp) return [];
    const uni = t.unicodeHost;
    const owned = t.suffix && uni.endsWith(t.suffix) ? uni.slice(0, -t.suffix.length - 1) : uni;
    if (/^[\x00-\x7f]*$/.test(owned)) return [];
    const labelUni = owned.split(".").pop()!;
    const skel = compact(asciiOnly(skeleton(owned)));
    const labelSkel = compact(asciiOnly(skeleton(labelUni)));
    for (const c of compiled) {
      const cands = new Map<string, string>();
      for (const [brand, targets] of c.targets) for (const target of targets.keys()) if (!cands.has(target)) cands.set(target, brand);
      for (const k of c.keywords) if (!cands.has(compact(k.term))) cands.set(compact(k.term), `campaign keyword "${k.term}"`);
      for (const [target, what] of cands) {
        const hit = labelSkel === target || (target.length >= 4 && skel.includes(target));
        if (!hit && typoMatch(labelSkel, target) === null) continue;
        return [sig("homoglyph_idn", W.HOMOGLYPH_IDN, "brand", `Internationalised domain "${defang(uni)}" reads as "${skel}", imitating ${what}`, [defang(t.host), defang(uni)])];
      }
    }
    return [];
  }

  function detectTld(ctx: Ctx): Signal[] {
    const t = ctx.t;
    if (ctx.allow.outlet || ctx.allow.platform || t.isIp || !t.suffix || t.isPrivateSuffix) return [];
    const tld = t.suffix.split(".").pop()!;
    if (abused.has(tld)) return [sig("abused_tld", W.ABUSED_TLD, "infrastructure", `.${tld} appears on public most-abused-TLD rankings`, [`.${tld}`])];
    return [];
  }

  // ---------------------------------------------------------------- engine
  function tierForScore(score: number): Tier {
    if (score >= rules.tiers.confirmed) return "confirmed";
    if (score >= rules.tiers.likely) return "likely";
    if (score >= rules.tiers.suspicious) return "suspicious";
    return "clear";
  }
  const clamp = (n: number): number => Math.max(0, Math.min(100, n));

  function assess(t: Target, snapshot?: Snapshot | null): Verdict {
    const allow = allowState(t);
    const ctx: Ctx = { t, allow, memo: new Map() };
    const signals = [
      ...detectAllowlist(ctx), ...detectCombo(ctx), ...detectClaims(ctx), ...detectBrand(ctx),
      ...detectHomoglyph(ctx), ...detectTld(ctx),
    ];
    let listed: { tier: Tier; score: number } | null = null;
    if (snapshot && !allow.outlet) {
      listed = snapshot.lookup(t.host) ?? snapshot.lookup(t.registrable);
      if (listed) {
        signals.push(sig("feed_listed", 0, "reputation", `Listed in the LureRadar feed as ${listed.tier.toUpperCase()} (score ${listed.score})`));
      }
    }
    const score = allow.outlet ? 0 : clamp(signals.reduce((s, x) => s + x.weight, 0));
    let tier: Tier = allow.outlet ? "clear" : tierForScore(score);
    if (!allow.outlet && listed && TIER_RANK[listed.tier] > TIER_RANK[tier]) tier = listed.tier;
    if (allow.platform && TIER_RANK[tier] > TIER_RANK.suspicious) tier = "suspicious";
    signals.sort((a, b) => b.weight - a.weight || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const display = t.kind === "url" && t.url ? t.url : t.host;
    return {
      input: t.raw, kind: t.kind, target: defang(display || t.raw), host: t.host ? defang(t.host) : null,
      registrable: t.registrable ? defang(t.registrable) : null, score, tier, signals,
      allowlisted: allow.outlet, platform: allow.platform, urls: [], listed,
    };
  }

  // ----------------------------------------------------------------- text
  const TP = rules.text.patterns;
  const textRe = Object.fromEntries(Object.entries(TP).map(([k, v]) => [k, pyRe(v, "gi")])) as Record<string, RegExp>;
  const brandRe = rules.text.brandPattern ? pyRe(rules.text.brandPattern, "gi") : null;
  const reBefore = pyRe(rules.text.reassuranceBefore, "i");
  const reAfter = pyRe(rules.text.reassuranceAfter, "i");
  const URL_RE = /(?:(?:https?|ftp):\/\/[^\s<>"'`]+)|(?<![\p{L}\p{N}_@.-])(?:(?:[\p{L}\p{N}](?:[\p{L}\p{N}]|-){0,62}\.)+\p{L}(?:[\p{L}\p{N}]|-){1,62})(?::\d{2,5})?(?:\/[^\s<>"'`]*)?/giu;

  function findAll(re: RegExp, text: string, limit = 5): string[] {
    re.lastIndex = 0;
    const out: string[] = [];
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      if (m[0].length === 0) {
        re.lastIndex++;
        continue;
      }
      out.push(m[0].split(/\s+/).join(" ").slice(0, 80));
      if (out.length >= limit) break;
    }
    return out;
  }

  function findWarnings(text: string): string[] {
    const re = textRe.WARNING;
    re.lastIndex = 0;
    const out: string[] = [];
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      const before = text.slice(Math.max(0, m.index - 12), m.index);
      const after = text.slice(m.index + m[0].length, m.index + m[0].length + 8);
      if (reBefore.test(before) || reAfter.test(after)) continue;
      out.push(m[0]);
      if (out.length >= 5) break;
    }
    return out;
  }

  function findUrls(text: string): string[] {
    const found: string[] = [];
    URL_RE.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = URL_RE.exec(text)) !== null) {
      const token = m[0].replace(/[.,;:!?)\]}>'"]+$/, "");
      if (!token) continue;
      if (!token.includes("://")) {
        const host = token.split("/")[0].split(":")[0];
        if (!hasKnownSuffix(toAsciiHost(host) || host)) continue;
      }
      found.push(token);
    }
    return found;
  }

  function assessText(raw: string, snapshot?: Snapshot | null): Verdict {
    const clean = refang(raw.slice(0, 20000));
    const urls = [...new Set(findUrls(clean))];
    const signals: Signal[] = [];
    let campaign = false;
    let claim: Signal | null = null;
    for (const c of compiled) {
      const hits = analyse(clean, c);
      if (hits.keywords.length || hits.brands.length) campaign = true;
      const found = unreleasedClaim(hits, c);
      if (found && !claim) {
        claim = sig("text_unreleased_platform", W.CLAIMS_UNRELEASED_PLATFORM_TEXT, "platform", claimText(c, found[0], found[2]));
      }
    }
    if (claim) signals.push(claim);
    const checks: [string, number, string, string[], boolean][] = [
      ["text_free_key_offer", W.TEXT_FREE_KEY_OFFER, "Offers free/early/beta keys, codes or downloads", findAll(textRe.FREE_OFFER, clean), campaign],
      ["text_off_platform_contact", W.TEXT_OFF_PLATFORM_CONTACT, "Moves the conversation off-platform (Telegram, WhatsApp, Discord, DMs)", findAll(textRe.OFF_PLATFORM, clean), true],
      ["text_payment_red_flag", W.TEXT_PAYMENT_RED_FLAG, "Asks for gift cards, crypto or untraceable payment", findAll(textRe.PAYMENT, clean), true],
      ["text_urgency_scarcity", W.TEXT_URGENCY_SCARCITY, "Urgency or scarcity pressure (limited keys, expiring offer)", findAll(textRe.URGENCY, clean), true],
      ["text_disable_security", W.TEXT_DISABLE_SECURITY, "Asks you to disable antivirus/Defender or run as administrator", findAll(textRe.DISABLE_SECURITY, clean), true],
      ["text_account_threat", W.TEXT_ACCOUNT_THREAT, "Account-threat phishing language (suspended account, verify your login)", findAll(textRe.ACCOUNT_THREAT, clean), true],
      ["text_survey_gate", W.TEXT_SURVEY_GATE, "Survey, offer or 'human verification' gate before the download", findAll(textRe.SURVEY, clean), true],
      ["text_too_good_to_be_true", W.TEXT_TOO_GOOD_TO_BE_TRUE, "Too-good-to-be-true promise (100% working, no survey, unlimited money, cracked)", findAll(textRe.TOO_GOOD, clean), true],
    ];
    const exe = [...findAll(textRe.EXECUTABLE, clean), ...findAll(textRe.ARCHIVE_PASSWORD, clean)];
    checks.push(["text_executable_lure", W.TEXT_EXECUTABLE_LURE, "Points to an executable, installer or password-protected archive", exe, true]);
    const cheap = campaign ? findAll(textRe.CHEAP_PRICE, clean) : [];
    if (cheap.length && !checks.some((c) => c[0] === "text_too_good_to_be_true" && c[3].length)) {
      checks.push(["text_too_good_to_be_true", W.TEXT_TOO_GOOD_TO_BE_TRUE, "Price far below retail for a new release", cheap, true]);
    }
    if (brandRe) {
      checks.push(["text_impersonation_claim", W.TEXT_IMPERSONATION_CLAIM, "Claims to be staff, support or an 'official giveaway' of a brand", findAll(brandRe, clean), true]);
    }
    const seen = new Set<string>();
    for (const [id, weight, explanation, matches, enabled] of checks) {
      if (enabled && matches.length && !seen.has(id)) {
        seen.add(id);
        signals.push(sig(id, weight, "text", explanation, matches.slice(0, 3).map(defangTextSnippet)));
      }
    }
    const short: string[] = [];
    for (const u of urls) {
      try {
        if (shortenersSet.has(parseTarget(u).registrable)) short.push(defang(u));
      } catch {
        /* unparsable token */
      }
    }
    if (short.length) signals.push(sig("text_link_shortener", W.TEXT_LINK_SHORTENER, "text", "Uses a link shortener that hides the real destination", short.slice(0, 3)));
    const warnings = findWarnings(clean);
    const positive = signals.reduce((s, x) => s + (x.weight > 0 ? x.weight : 0), 0);
    if (warnings.length && positive > 0) {
      signals.push(sig("text_warning_context", W.TEXT_WARNING_CONTEXT, "text", "Reads as a warning or question about scams rather than an offer", warnings.slice(0, 3)));
    }
    const urlVerdicts: Verdict[] = [];
    for (const u of urls.slice(0, 10)) {
      let t: Target;
      try {
        t = parseTarget(u);
      } catch {
        continue;
      }
      if (t.kind === "text") continue;
      urlVerdicts.push(assess(t, snapshot));
    }
    const risky = urlVerdicts.filter((u) => u.score >= W.TEXT_RISKY_LINK_MIN_SCORE && !u.allowlisted);
    if (risky.length) {
      const worst = risky.reduce((a, b) => (b.score > a.score ? b : a));
      signals.push(sig("text_risky_link", W.TEXT_RISKY_LINK, "text", `Links to ${worst.host ?? worst.target} which shows lure signals (score ${worst.score})`, risky.slice(0, 3).map((u) => u.target)));
    }
    let score = clamp(signals.reduce((s, x) => s + x.weight, 0));
    let tier = tierForScore(score);
    let best: Verdict | null = null;
    for (const v of urlVerdicts) {
      if (!best || TIER_RANK[v.tier] > TIER_RANK[best.tier] || (TIER_RANK[v.tier] === TIER_RANK[best.tier] && v.score > best.score)) best = v;
    }
    if (best && (TIER_RANK[best.tier] > TIER_RANK[tier] || (TIER_RANK[best.tier] === TIER_RANK[tier] && best.score > score))) {
      score = best.score;
      tier = best.tier;
    }
    signals.sort((a, b) => b.weight - a.weight || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const snippet = raw.split(/\s+/).filter(Boolean).join(" ");
    return {
      input: raw, kind: "text", target: defangText(snippet.slice(0, 200) + (snippet.length > 200 ? "..." : "")),
      host: null, registrable: null, score, tier, signals, allowlisted: false, platform: false, urls: urlVerdicts, listed: null,
    };
  }

  function defangText(text: string): string {
    URL_RE.lastIndex = 0;
    return refang(text).replace(URL_RE, (token) => {
      const stripped = token.replace(/[.,;:!?)\]}>'"]+$/, "");
      const trailer = token.slice(stripped.length);
      if (!stripped.includes("://")) {
        const host = stripped.split("/")[0].split(":")[0];
        if (!hasKnownSuffix(toAsciiHost(host) || host)) return token;
      }
      return defang(stripped) + trailer;
    });
  }
  const defangTextSnippet = (s: string): string => defangText(s);

  function check(raw: string, snapshot?: Snapshot | null): Verdict {
    const t = parseTarget(raw);
    if (t.kind === "text") return assessText(raw, snapshot);
    return assess(t, snapshot);
  }

  return { check, parseTarget, defang, refang, defangText };
}

/** Python's urllib.parse.unquote (UTF-8, invalid sequences replaced). */
function pyUnquote(s: string): string {
  if (!s.includes("%")) return s;
  return s.replace(/(?:%[0-9a-fA-F]{2})+/g, (run) => {
    const bytes = new Uint8Array(run.length / 3);
    for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(run.slice(i * 3 + 1, i * 3 + 3), 16);
    return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
  });
}

export function snapshotFromFeed(feed: { indicators?: { domain: string; tier: Tier; score: number; status?: string }[] }): Snapshot {
  const map = new Map<string, { tier: Tier; score: number }>();
  for (const i of feed.indicators ?? []) if (!i.status || i.status === "active") map.set(i.domain.toLowerCase(), { tier: i.tier, score: i.score });
  return { lookup: (d: string) => (d ? (map.get(d.toLowerCase()) ?? null) : null) };
}
