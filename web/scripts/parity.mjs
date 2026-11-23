// Parity test: the browser checker must return the same score and tier as
// the Python engine for every case exported by scripts/build_site_data.py.
//   npm test   (runs: node --experimental-strip-types scripts/parity.mjs)
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createChecker } from "../src/lib/checker.ts";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const rules = JSON.parse(readFileSync(join(web, "public/data/rules.json"), "utf8"));
const cases = JSON.parse(readFileSync(join(web, "src/data/generated/parity.json"), "utf8"));
const checker = createChecker(rules);

let failures = 0;
const sameSet = (a, b) => a.length === b.length && a.every((x) => b.includes(x));
for (const c of cases) {
  let got;
  try {
    got = checker.check(c.input);
  } catch (err) {
    if (c.error) continue;
    failures++;
    console.log(`FAIL (threw) ${JSON.stringify(c.input)}: ${err.message}`);
    continue;
  }
  if (c.error) {
    failures++;
    console.log(`FAIL (python rejected, TS accepted) ${JSON.stringify(c.input)}`);
    continue;
  }
  const ids = [...new Set(got.signals.map((s) => s.id))].sort();
  if (got.score !== c.score || got.tier !== c.tier || !sameSet(ids, c.signals) || got.kind !== c.kind) {
    failures++;
    console.log(
      `FAIL ${JSON.stringify(c.input).slice(0, 90)}\n  python: ${c.kind} ${c.tier} ${c.score} [${c.signals}]\n  ts:     ${got.kind} ${got.tier} ${got.score} [${ids}]`,
    );
  }
}
const total = cases.length;
console.log(`parity: ${total - failures}/${total} cases match the Python engine (score, tier, signal ids)`);
process.exit(failures ? 1 : 0);
