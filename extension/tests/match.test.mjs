import assert from "node:assert/strict";
import { test } from "node:test";
import { buildIndex, candidates, defang, hostOf, lookup } from "../src/match.js";

const doc = {
  indicators: [
    { domain: "gta6-pc-download.test", tier: "likely", score: 75, status: "active",
      signals: [{ weight: 30, explanation: "fake PC" }, { weight: 0, explanation: "info" }], dispute_url: "https://example.org/d" },
    { domain: "maybe.test", tier: "suspicious", score: 45, status: "active", signals: [] },
    { domain: "old.test", tier: "likely", score: 80, status: "stale", signals: [] },
  ],
};

test("hostOf only accepts http(s)", () => {
  assert.equal(hostOf("https://WWW.Gta6-PC-Download.test./x"), "www.gta6-pc-download.test");
  assert.equal(hostOf("chrome://settings"), "");
  assert.equal(hostOf("not a url"), "");
});

test("candidates walk parent domains but never a bare TLD", () => {
  assert.deepEqual(candidates("a.b.example.test"), ["a.b.example.test", "b.example.test", "example.test"]);
});

test("index respects tier and status", () => {
  const likely = buildIndex(doc);
  assert.deepEqual(Object.keys(likely), ["gta6-pc-download.test"]);
  assert.deepEqual(likely["gta6-pc-download.test"].signals, ["fake PC"]);
  assert.ok(buildIndex(doc, "suspicious")["maybe.test"]);
});

test("lookup matches subdomains of listed domains only", () => {
  const index = buildIndex(doc);
  assert.equal(lookup(index, "cdn.gta6-pc-download.test").tier, "likely");
  assert.equal(lookup(index, "gta6-pc-download.test.evil.test"), null);
  assert.equal(lookup(index, ""), null);
});

test("defang for display", () => {
  assert.equal(defang("https://a.b.test/x.y"), "hxxps://a[.]b[.]test/x.y");
  assert.equal(defang("a.test"), "a[.]test");
});
