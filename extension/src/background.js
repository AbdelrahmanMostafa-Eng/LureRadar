// LureRadar extension background. Privacy: the only network request is the
// download of the public feed. Visited URLs are checked locally and never sent.
import { FEED_URL, FEED_URL_ALL } from "./config.js";
import { buildIndex, hostOf, lookup } from "./match.js";

const api = globalThis.browser ?? globalThis.chrome;
const REFRESH_MINUTES = 360;

async function settings() {
  const s = await api.storage.local.get({ enabled: true, includeSuspicious: false });
  return s;
}

export async function refreshFeed() {
  const { includeSuspicious } = await settings();
  const res = await fetch(includeSuspicious ? FEED_URL_ALL : FEED_URL, { cache: "no-cache", credentials: "omit" });
  if (!res.ok) throw new Error(`feed HTTP ${res.status}`);
  const doc = await res.json();
  const index = buildIndex(doc, includeSuspicious ? "suspicious" : "likely");
  await api.storage.local.set({
    index,
    count: Object.keys(index).length,
    generatedAt: doc.generated_at ?? null,
    fetchedAt: new Date().toISOString(),
    lastError: null,
  });
}

async function safeRefresh() {
  try {
    await refreshFeed();
  } catch (err) {
    await api.storage.local.set({ lastError: String(err) });
  }
}

api.runtime.onInstalled.addListener(() => {
  api.alarms.create("refresh", { periodInMinutes: REFRESH_MINUTES });
  safeRefresh();
});
api.runtime.onStartup?.addListener(safeRefresh);
api.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "refresh") safeRefresh();
});

api.webNavigation.onBeforeNavigate.addListener(async (details) => {
  if (details.frameId !== 0) return;
  const host = hostOf(details.url);
  if (!host) return;
  const { enabled, index = {} } = await api.storage.local.get({ enabled: true, index: {} });
  if (!enabled) return;
  const hit = lookup(index, host);
  if (!hit) return;
  const allowed = (await api.storage.session?.get({ allowed: [] }))?.allowed ?? [];
  if (allowed.includes(hit.domain)) return;
  const warning = api.runtime.getURL("src/warning.html") + "?u=" + encodeURIComponent(details.url);
  api.tabs.update(details.tabId, { url: warning });
});

api.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg?.type === "allowOnce" && typeof msg.domain === "string") {
    api.storage.session?.get({ allowed: [] }).then(({ allowed }) =>
      api.storage.session.set({ allowed: [...new Set([...allowed, msg.domain])] }).then(() => reply(true)),
    );
    return true;
  }
  if (msg?.type === "refresh") {
    safeRefresh().then(() => reply(true));
    return true;
  }
  return false;
});
