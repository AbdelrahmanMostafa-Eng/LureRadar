// Generates LureRadar's original brand SVGs into ../assets and ./public.
//   node scripts/gen-brand.mjs
// Text is converted to outlined paths (Inter, SIL OFL, from
// @expo-google-fonts/inter) so the SVGs render identically everywhere,
// including GitHub's README image proxy, without loading any font.
import { mkdirSync, readFileSync, writeFileSync, copyFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import opentype from "opentype.js";

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, "..");
const assets = join(web, "..", "assets");
const pub = join(web, "public");

const T = {
  bg: "#07090D", surface: "#0D1117", border: "#1B232C", text: "#E6EDF3", muted: "#8B98A5",
  radar: "#3CFFB0", amber: "#FFB020", danger: "#FF4D5E", info: "#4CC2FF",
  // light-theme counterparts (>= 4.5:1 on white for text, >= 3:1 for graphics)
  lightText: "#0D1117", lightRadar: "#00805A", lightAmber: "#A35F00", lightMuted: "#4A5562",
};

function font(path) {
  const buf = readFileSync(join(web, "node_modules", "@expo-google-fonts", path));
  return opentype.parse(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
}
const interBold = font("inter/700Bold/Inter_700Bold.ttf");
const interMedium = font("inter/500Medium/Inter_500Medium.ttf");
const monoMedium = font("jetbrains-mono/500Medium/JetBrainsMono_500Medium.ttf");

/** Outline `text` with manual layout (kerning, no shaping features). */
function outline(f, text, x, y, size, tracking = 0) {
  const scale = size / f.unitsPerEm;
  let cursor = x;
  let prev = null;
  let d = "";
  for (const ch of text) {
    const g = f.charToGlyph(ch);
    if (prev) cursor += f.getKerningValue(prev, g) * scale;
    d += g.getPath(cursor, y, size).toPathData(2);
    cursor += g.advanceWidth * scale + tracking;
    prev = g;
  }
  return { d, width: cursor - x - tracking };
}

// ------------------------------------------------------------------ the mark
// 64x64: radar rings, a sweep with its leading edge, a centre pip and one
// blip that has resolved into a fishing hook (the lure).
function mark({ ring = T.radar, hook = T.amber, id = "m" } = {}) {
  return `
  <defs>
    <linearGradient id="${id}-sweep" x1="32" y1="32" x2="54" y2="12" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="${ring}" stop-opacity="0"/>
      <stop offset="1" stop-color="${ring}" stop-opacity=".6"/>
    </linearGradient>
  </defs>
  <circle cx="32" cy="32" r="27" fill="none" stroke="${ring}" stroke-width="4"/>
  <circle cx="32" cy="32" r="15.5" fill="none" stroke="${ring}" stroke-width="2.5" opacity=".45"/>
  <path d="M32 32V5a27 27 0 0 1 23.4 13.5Z" fill="url(#${id}-sweep)"/>
  <path d="M32 32 55.4 18.5" stroke="${ring}" stroke-width="3" stroke-linecap="round"/>
  <circle cx="32" cy="32" r="3.2" fill="${ring}"/>
  <g fill="none" stroke="${hook}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M43 36.5V44a4.5 4.5 0 0 1-9 0v-3.2l2.8 2.6"/>
    <circle cx="43" cy="33.6" r="1.9" stroke-width="2.4"/>
  </g>`;
}

const adaptiveStyle = (cls) => `
  <style>
    .${cls}-ring { stroke: ${T.radar}; } .${cls}-fill { fill: ${T.radar}; } .${cls}-hook { stroke: ${T.amber}; }
    .${cls}-text { fill: ${T.text}; } .${cls}-accent { fill: ${T.radar}; }
    @media (prefers-color-scheme: light) {
      .${cls}-ring { stroke: ${T.lightRadar}; } .${cls}-fill { fill: ${T.lightRadar}; }
      .${cls}-hook { stroke: ${T.lightAmber}; } .${cls}-text { fill: ${T.lightText}; }
      .${cls}-accent { fill: ${T.lightRadar}; }
    }
  </style>`;

function adaptiveMark(cls) {
  // same geometry as mark(), colours driven by classes so the SVG follows the
  // viewer's colour scheme (works in <img> on GitHub and in browsers)
  return `
  <defs>
    <linearGradient id="${cls}-sweep" x1="32" y1="32" x2="54" y2="12" gradientUnits="userSpaceOnUse">
      <stop offset="0" class="${cls}-stop" stop-opacity="0" stop-color="currentColor"/>
      <stop offset="1" class="${cls}-stop" stop-opacity=".6" stop-color="currentColor"/>
    </linearGradient>
  </defs>
  <g class="${cls}-color">
    <circle class="${cls}-ring" cx="32" cy="32" r="27" fill="none" stroke-width="4"/>
    <circle class="${cls}-ring" cx="32" cy="32" r="15.5" fill="none" stroke-width="2.5" opacity=".45"/>
    <path d="M32 32V5a27 27 0 0 1 23.4 13.5Z" fill="url(#${cls}-sweep)"/>
    <path class="${cls}-ring" d="M32 32 55.4 18.5" stroke-width="3" stroke-linecap="round"/>
    <circle class="${cls}-fill" cx="32" cy="32" r="3.2"/>
    <g class="${cls}-hook" fill="none" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M43 36.5V44a4.5 4.5 0 0 1-9 0v-3.2l2.8 2.6"/>
      <circle cx="43" cy="33.6" r="1.9" stroke-width="2.4"/>
    </g>
  </g>`;
}

function adaptiveLogo() {
  const cls = "lr";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" role="img" aria-labelledby="t">
  <title id="t">LureRadar</title>${adaptiveStyle(cls)}
  <style>svg { color: ${T.radar}; } @media (prefers-color-scheme: light) { svg { color: ${T.lightRadar}; } }</style>
  ${adaptiveMark(cls)}
</svg>
`;
}

function staticLogo(ring, hook) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" role="img" aria-labelledby="t">
  <title id="t">LureRadar</title>${mark({ ring, hook })}
</svg>
`;
}

function favicon() {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <rect width="64" height="64" rx="14" fill="${T.bg}"/>
  <g transform="translate(3 3) scale(.906)">${mark({ id: "f" })}</g>
</svg>
`;
}

function wordmark() {
  const cls = "wm";
  const size = 44;
  const lure = outline(interBold, "Lure", 76, 46, size, -0.4);
  const radar = outline(interBold, "Radar", 76 + lure.width, 46, size, -0.4);
  const width = Math.ceil(76 + lure.width + radar.width + 6);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} 64" width="${width}" height="64" role="img" aria-labelledby="t">
  <title id="t">LureRadar</title>${adaptiveStyle(cls)}
  <style>svg { color: ${T.radar}; } @media (prefers-color-scheme: light) { svg { color: ${T.lightRadar}; } }</style>
  ${adaptiveMark(cls)}
  <path class="${cls}-text" d="${lure.d}"/>
  <path class="${cls}-accent" d="${radar.d}"/>
</svg>
`;
}

function banner() {
  const W = 1280, H = 320;
  const cx = 1060, cy = 160;
  const title1 = outline(interBold, "Lure", 168, 150, 76, -1.5);
  const title2 = outline(interBold, "Radar", 168 + title1.width, 150, 76, -1.5);
  const tag = outline(interMedium, "See the lure before you bite.", 172, 204, 30, 0);
  const chips = ["offline CLI", "explainable scores", "free blocklists", "PC Watch"];
  let chipX = 172;
  let chipSvg = "";
  for (const c of chips) {
    const o = outline(monoMedium, c, chipX + 14, 264, 15, 0);
    const w = o.width + 28;
    chipSvg += `<rect x="${chipX}" y="242" width="${w.toFixed(1)}" height="32" rx="16" fill="${T.surface}" stroke="${T.border}"/>`;
    chipSvg += `<path d="${o.d}" fill="${T.muted}"/>`;
    chipX += w + 10;
  }
  const rings = [60, 120, 180, 240]
    .map((r, i) => `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${i === 3 ? T.radar : T.border}" stroke-opacity="${i === 3 ? 0.35 : 1}" stroke-width="${i === 3 ? 2 : 1.5}"/>`)
    .join("");
  const hook = (x, y, s, color, op = 1) => `<g transform="translate(${x} ${y}) scale(${s})" fill="none" stroke="${color}" stroke-opacity="${op}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M0 -6V4a5 5 0 0 1-10 0v-3.5l3 2.8"/><circle cx="0" cy="-9" r="2" stroke-width="2.4"/></g>`;
  const blip = (x, y, r, color, op) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${color}" fill-opacity="${op}"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-labelledby="t d">
  <title id="t">LureRadar</title>
  <desc id="d">See the lure before you bite. Open threat radar for hyped-launch scams.</desc>
  <defs>
    <clipPath id="clip"><rect width="${W}" height="${H}" rx="18"/></clipPath>
    <radialGradient id="glow" cx="${cx}" cy="${cy}" r="300" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="${T.radar}" stop-opacity=".10"/>
      <stop offset="1" stop-color="${T.radar}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="sweep" x1="${cx}" y1="${cy}" x2="${cx + 170}" y2="${cy - 170}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="${T.radar}" stop-opacity="0"/>
      <stop offset="1" stop-color="${T.radar}" stop-opacity=".42"/>
    </linearGradient>
    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M32 0H0V32" fill="none" stroke="${T.border}" stroke-width="1" opacity=".55"/>
    </pattern>
    <linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="${T.bg}"/><stop offset=".55" stop-color="${T.bg}" stop-opacity=".2"/><stop offset="1" stop-color="${T.bg}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <g clip-path="url(#clip)">
    <rect width="${W}" height="${H}" fill="${T.bg}"/>
    <rect width="${W}" height="${H}" fill="url(#grid)"/>
    <rect width="${W}" height="${H}" fill="url(#fade)"/>
    <circle cx="${cx}" cy="${cy}" r="300" fill="url(#glow)"/>
    ${rings}
    <path d="M${cx - 240} ${cy}H${cx + 240}M${cx} ${cy - 240}V${cy + 240}" stroke="${T.border}" stroke-width="1.5"/>
    <path d="M${cx} ${cy}L${cx} ${cy - 240}A240 240 0 0 1 ${cx + 207.8} ${cy - 120}Z" fill="url(#sweep)"/>
    <path d="M${cx} ${cy}L${cx + 207.8} ${cy - 120}" stroke="${T.radar}" stroke-width="2.5" stroke-linecap="round"/>
    ${blip(cx + 70, cy - 150, 5, T.radar, 0.9)}${blip(cx - 130, cy + 60, 4, T.radar, 0.5)}${blip(cx + 150, cy + 90, 4, T.radar, 0.35)}
    ${hook(cx + 120, cy - 52, 1.6, T.amber)}${hook(cx - 70, cy - 100, 1.3, T.danger, 0.85)}${hook(cx + 40, cy + 130, 1.2, T.amber, 0.55)}
    <circle cx="${cx}" cy="${cy}" r="6" fill="${T.radar}"/>
    <g transform="translate(64 86) scale(1.5)">${mark({ id: "b" })}</g>
    <path d="${title1.d}" fill="${T.text}"/>
    <path d="${title2.d}" fill="${T.radar}"/>
    <path d="${tag.d}" fill="${T.muted}"/>
    ${chipSvg}
    <rect x=".75" y=".75" width="${W - 1.5}" height="${H - 1.5}" rx="17.5" fill="none" stroke="${T.border}" stroke-width="1.5"/>
  </g>
</svg>
`;
}

function write(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content);
  console.log("wrote", path.replace(join(web, ".."), "."));
}

write(join(assets, "logo.svg"), adaptiveLogo());
write(join(assets, "logo-dark.svg"), staticLogo(T.lightRadar, T.lightAmber));
write(join(assets, "logo-light.svg"), staticLogo(T.radar, T.amber));
write(join(assets, "wordmark.svg"), wordmark());
write(join(assets, "banner.svg"), banner());
write(join(assets, "favicon", "favicon.svg"), favicon());
mkdirSync(pub, { recursive: true });
copyFileSync(join(assets, "favicon", "favicon.svg"), join(pub, "favicon.svg"));
