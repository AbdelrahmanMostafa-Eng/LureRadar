// Small progressive enhancements shared by every page: theme toggle, copy
// buttons, freshness indicator. No network requests.
const THEMES = ["system", "dark", "light"] as const;
type Theme = (typeof THEMES)[number];

function currentTheme(): Theme {
  const t = document.documentElement.dataset.theme;
  return t === "dark" || t === "light" ? t : "system";
}

function applyTheme(t: Theme): void {
  if (t === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = t;
  try {
    if (t === "system") localStorage.removeItem("lr-theme");
    else localStorage.setItem("lr-theme", t);
  } catch {
    /* storage unavailable */
  }
  const btn = document.getElementById("theme-toggle");
  if (btn) {
    btn.textContent = `Theme: ${t === "system" ? "Auto" : t === "dark" ? "Dark" : "Light"}`;
  }
}

export function initChrome(): void {
  applyTheme(currentTheme());
  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    const next = THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length];
    applyTheme(next);
  });

  document.addEventListener("click", async (ev) => {
    const target = (ev.target as HTMLElement | null)?.closest<HTMLElement>("[data-copy]");
    if (!target) return;
    const text = target.dataset.copy ?? "";
    try {
      await navigator.clipboard.writeText(text);
      const old = target.textContent;
      target.textContent = "Copied";
      setTimeout(() => (target.textContent = old), 1400);
    } catch {
      target.textContent = "Select & copy";
    }
  });

  const time = document.getElementById("fresh-time") as HTMLTimeElement | null;
  const ageEl = document.getElementById("fresh-age");
  const dot = document.getElementById("fresh-dot");
  if (time?.dateTime && ageEl) {
    const t = Date.parse(time.dateTime);
    if (!Number.isNaN(t)) {
      const hours = Math.max(0, (Date.now() - t) / 3_600_000);
      ageEl.textContent = hours < 1 ? "(less than an hour ago)" : hours < 48 ? `(${Math.round(hours)} h ago)` : `(${Math.round(hours / 24)} days ago)`;
      if (hours > 36) dot?.classList.add("stale");
    }
  }
}
