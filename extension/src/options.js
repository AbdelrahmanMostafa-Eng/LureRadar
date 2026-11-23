const api = globalThis.browser ?? globalThis.chrome;
const enabled = document.getElementById("enabled");
const suspicious = document.getElementById("suspicious");
const status = document.getElementById("status");

async function render() {
  const s = await api.storage.local.get({ enabled: true, includeSuspicious: false, count: 0, generatedAt: null, lastError: null });
  enabled.checked = s.enabled;
  suspicious.checked = s.includeSuspicious;
  status.textContent = s.lastError
    ? `Last update failed: ${s.lastError}`
    : `${s.count} listed domains · feed generated ${s.generatedAt ?? "not yet downloaded"}`;
}

enabled.addEventListener("change", () => api.storage.local.set({ enabled: enabled.checked }));
suspicious.addEventListener("change", async () => {
  await api.storage.local.set({ includeSuspicious: suspicious.checked });
  await api.runtime.sendMessage({ type: "refresh" });
  render();
});
document.getElementById("refresh").addEventListener("click", async () => {
  status.textContent = "Updating…";
  await api.runtime.sendMessage({ type: "refresh" });
  render();
});
render();
