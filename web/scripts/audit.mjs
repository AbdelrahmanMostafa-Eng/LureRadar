// Accessibility, privacy and performance audit for the built site.
//   npm run build && npm run preview -- --port 4321 &   then:   npm run audit
// - axe-core (WCAG 2.0/2.1/2.2 A+AA) on every page, dark AND light scheme;
// - fails if any request leaves the site's own origin (no third-party requests);
// - Lighthouse (all four categories) on Home, Radar, Check and PC Watch.
// Results are written to web/audit-results.json.
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright"); // pre-installed globally in CI images; `npx playwright` otherwise
const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const BASE = process.env.AUDIT_URL ?? "http://127.0.0.1:4321/LureRadar/";
const CHROME = process.env.CHROME_PATH ?? chromium.executablePath();
const LH_VERSION = "13.6.0";
const axeSource = readFileSync(join(web, "node_modules/axe-core/axe.min.js"), "utf8");
const PAGES = ["", "radar/", "check/", "feeds/", "pc-watch/", "methodology/", "packs/", "report/", "about/", "ethics/", "privacy/", "bot/", "docs/", "docs/quickstart/", "docs/signals/", "404.html"];
const LH_PAGES = ["", "radar/", "check/", "pc-watch/"];

const origin = new URL(BASE).origin;
const results = { base: BASE, generated_at: new Date().toISOString(), axe: {}, third_party: {}, lighthouse: {} };
let failed = false;

const browser = await chromium.launch();
for (const scheme of ["dark", "light"]) {
  const ctx = await browser.newContext({ colorScheme: scheme, viewport: { width: 1280, height: 900 } });
  for (const path of PAGES) {
    const page = await ctx.newPage();
    const external = [];
    page.on("request", (r) => { if (!r.url().startsWith(origin) && !r.url().startsWith("data:")) external.push(r.url()); });
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    if (path === "check/") {
      await page.fill("#q", "hxxps://rockstar-gta6-pc-download[.]test/free-key");
      await page.click("button[type=submit]");
      await page.waitForSelector(".verdict");
    }
    // Let entrance animations finish (finite ones only; the radar sweep loops
    // forever) so contrast is measured on the settled page, not mid-fade.
    await page.evaluate(() => Promise.all(document.getAnimations()
      .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
      .map((a) => a.finished.catch(() => null))));
    await page.addScriptTag({ content: axeSource });
    const res = await page.evaluate(async () =>
      // @ts-ignore injected
      await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] } }),
    );
    const v = res.violations.map((x) => ({ id: x.id, impact: x.impact, nodes: x.nodes.length, sample: x.nodes[0]?.target }));
    results.axe[`${scheme}:${path || "/"}`] = v;
    if (v.length) { failed = true; console.log(`axe ${scheme} ${path || "/"}:`, JSON.stringify(v)); }
    if (external.length) { failed = true; results.third_party[`${scheme}:${path || "/"}`] = external; console.log("third-party requests on", path, external); }
    await page.close();
  }
  await ctx.close();
}
await browser.close();

for (const path of LH_PAGES) {
  const out = join(mkdtempSync(join(tmpdir(), "lh-")), "report.json");
  try {
    execFileSync("npx", ["--yes", `lighthouse@${LH_VERSION}`, BASE + path, "--quiet", "--output=json", `--output-path=${out}`,
      "--only-categories=performance,accessibility,best-practices,seo", "--chrome-flags=--headless=new --no-sandbox --disable-gpu"],
      { env: { ...process.env, CHROME_PATH: CHROME }, stdio: ["ignore", "ignore", "inherit"], timeout: 240_000 });
    const lhr = JSON.parse(readFileSync(out, "utf8"));
    const scores = Object.fromEntries(Object.entries(lhr.categories).map(([k, c]) => [k, Math.round(c.score * 100)]));
    results.lighthouse[path || "/"] = scores;
    const low = Object.entries(scores).filter(([, s]) => s < 95);
    if (low.length) {
      failed = true;
      const audits = Object.values(lhr.audits).filter((a) => a.score !== null && a.score < 0.9 && a.scoreDisplayMode !== "informative").map((a) => a.id);
      console.log(`lighthouse ${path || "/"} below 95:`, low, "failing audits:", audits.slice(0, 12));
    }
    console.log(`lighthouse ${path || "/"}`, scores);
  } catch (err) {
    failed = true;
    results.lighthouse[path || "/"] = { error: String(err.message || err).slice(0, 200) };
    console.log("lighthouse failed for", path, String(err.message || err).slice(0, 200));
  }
}

writeFileSync(join(web, "audit-results.json"), JSON.stringify(results, null, 2) + "\n");
const axeTotal = Object.values(results.axe).reduce((n, v) => n + v.length, 0);
console.log(`axe: ${axeTotal} violations across ${Object.keys(results.axe).length} page/scheme runs; third-party requests: ${Object.keys(results.third_party).length}`);
process.exit(failed ? 1 : 0);
