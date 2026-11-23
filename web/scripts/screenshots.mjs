// README screenshots (deviceScaleFactor 2) and radar animation frames.
//   npm run preview -- --port 4321 &   node scripts/screenshots.mjs
// Frames are captured by pausing every CSS animation and stepping its clock,
// so the GIF is smooth and deterministic. Assemble with:
//   uv run python scripts/gen_og.py --radar-gif <frames dir>
import { mkdirSync, mkdtempSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(web, "..", "assets", "screenshots");
const BASE = process.env.SHOT_URL ?? "http://127.0.0.1:4321/LureRadar/";
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 2, colorScheme: "dark", reducedMotion: "reduce" });
const page = await ctx.newPage();
const shots = [
  ["dashboard.png", ""],
  ["radar.png", "radar/"],
  ["pc-watch.png", "pc-watch/"],
];
for (const [name, path] of shots) {
  await page.goto(BASE + path, { waitUntil: "networkidle" });
  await page.screenshot({ path: join(out, name) });
}
await page.goto(BASE + "check/", { waitUntil: "networkidle" });
await page.waitForFunction(() => document.getElementById("status")?.textContent?.includes("loaded"));
await page.fill("#q", "hxxps://rockstar-gta6-pc-download[.]test/free-key");
await page.click("button[type=submit]");
await page.waitForSelector(".verdict");
await page.evaluate(() => {
  document.getElementById("check-form")?.scrollIntoView({ block: "start" });
  window.scrollBy(0, -84);
});
await page.screenshot({ path: join(out, "check.png") });
await ctx.close();

// radar animation frames (normal motion)
const frames = process.env.FRAMES_DIR ?? mkdtempSync(join(tmpdir(), "radar-frames-"));
mkdirSync(frames, { recursive: true });
const actx = await browser.newContext({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 1, colorScheme: "dark" });
const ap = await actx.newPage();
await ap.goto(BASE, { waitUntil: "networkidle" });
const fig = ap.locator("figure.radar");
await ap.evaluate(() => {
  const anims = document.getAnimations();
  // @ts-ignore stash start times
  window.__lr = anims.map((a) => { a.pause(); return [a, a.currentTime ?? 0]; });
});
const FPS = 12, SECONDS = 6;
for (let i = 0; i < FPS * SECONDS; i++) {
  await ap.evaluate((t) => {
    // @ts-ignore
    for (const [a, start] of window.__lr) a.currentTime = start + t;
  }, (i * 1000) / FPS);
  await fig.screenshot({ path: join(frames, `f${String(i).padStart(3, "0")}.png`), omitBackground: false });
}
await browser.close();
console.log(`screenshots -> ${out}\nframes -> ${frames}`);
