import { defang, hostOf, lookup } from "./match.js";

const api = globalThis.browser ?? globalThis.chrome;
const url = new URLSearchParams(location.search).get("u") ?? "";
const host = hostOf(url);
document.getElementById("target").textContent = defang(url);

const { index = {} } = await api.storage.local.get({ index: {} });
const hit = lookup(index, host);
if (hit) {
  document.getElementById("tier").textContent = `${hit.tier.toUpperCase()} · score ${hit.score}/100`;
  const ul = document.getElementById("why");
  for (const s of hit.signals) {
    const li = document.createElement("li");
    li.textContent = s;
    ul.append(li);
  }
  if (hit.dispute) document.getElementById("dispute").href = hit.dispute;
}
document.getElementById("back").addEventListener("click", () => history.length > 2 ? history.go(-2) : window.close());
document.getElementById("proceed").addEventListener("click", async () => {
  if (hit) await api.runtime.sendMessage({ type: "allowOnce", domain: hit.domain });
  if (/^https?:\/\//i.test(url)) location.replace(url);
});
