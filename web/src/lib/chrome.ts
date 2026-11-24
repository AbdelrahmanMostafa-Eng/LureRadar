// Progressive enhancements shared by every page: theme toggle, copy buttons,
// freshness indicator, header elevation, scroll reveals, count-up numbers,
// tabs and the mobile menu. No network requests, no dependencies.
// Everything degrades to a fully readable static page without JavaScript.
const THEMES = ["system", "dark", "light"] as const;
type Theme = (typeof THEMES)[number];
const LABEL: Record<Theme, string> = { system: "Auto", dark: "Dark", light: "Light" };
const reduceMotion = (): boolean => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

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
    btn.dataset.mode = t;
    const label = `Colour theme: ${LABEL[t]} (click to change)`;
    btn.setAttribute("aria-label", label);
    btn.title = label;
  }
}

function initTheme(): void {
  applyTheme(currentTheme());
  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    const next = THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length];
    const swap = () => applyTheme(next);
    const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown };
    if (doc.startViewTransition && !reduceMotion()) doc.startViewTransition(swap);
    else swap();
  });
}

function initCopy(): void {
  document.addEventListener("click", async (ev) => {
    const target = (ev.target as HTMLElement | null)?.closest<HTMLElement>("[data-copy]");
    if (!target) return;
    const text = target.dataset.copy ?? "";
    const old = target.textContent;
    try {
      await navigator.clipboard.writeText(text);
      target.textContent = "Copied";
      target.dataset.copied = "";
    } catch {
      target.textContent = "Select & copy";
    }
    setTimeout(() => {
      target.textContent = old;
      delete target.dataset.copied;
    }, 1600);
  });
}

function initFreshness(): void {
  const time = document.getElementById("fresh-time") as HTMLTimeElement | null;
  const ageEl = document.getElementById("fresh-age");
  const dot = document.getElementById("fresh-dot");
  if (!time?.dateTime || !ageEl) return;
  const t = Date.parse(time.dateTime);
  if (Number.isNaN(t)) return;
  const hours = Math.max(0, (Date.now() - t) / 3_600_000);
  ageEl.textContent = hours < 1 ? "less than an hour ago" : hours < 48 ? `${Math.round(hours)} h ago` : `${Math.round(hours / 24)} days ago`;
  if (hours > 36) dot?.classList.add("stale");
}

function initHeader(): void {
  const header = document.querySelector<HTMLElement>(".site-header");
  if (!header) return;
  // The page has no visible scrollbar; this hairline shows reading progress.
  const bar = header.querySelector<HTMLElement>(".scroll-progress > span");
  const update = () => {
    if (window.scrollY > 8) header.dataset.elevated = "";
    else delete header.dataset.elevated;
    if (bar) {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.transform = `scaleX(${max > 0 ? Math.min(1, window.scrollY / max) : 0})`;
    }
  };
  update();
  let ticking = false;
  window.addEventListener("scroll", () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      update();
      ticking = false;
    });
  }, { passive: true });
  window.addEventListener("resize", update, { passive: true });
}

function countUp(el: HTMLElement): void {
  const target = Number(el.dataset.count);
  if (!Number.isFinite(target) || target <= 0 || reduceMotion()) return;
  const dur = 1400;
  const start = performance.now();
  const ease = (x: number) => (x === 1 ? 1 : 1 - 2 ** (-10 * x));
  const frame = (now: number) => {
    const p = Math.min(1, (now - start) / dur);
    el.textContent = String(Math.round(target * ease(p)));
    if (p < 1) requestAnimationFrame(frame);
  };
  el.textContent = "0";
  requestAnimationFrame(frame);
}

function initReveal(): void {
  const items = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal]"));
  const counters = Array.from(document.querySelectorAll<HTMLElement>("[data-count]"));
  if (!("IntersectionObserver" in window)) {
    items.forEach((el) => el.classList.add("is-in"));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const el = e.target as HTMLElement;
      if (el.hasAttribute("data-count")) countUp(el);
      else el.classList.add("is-in");
      io.unobserve(el);
    }
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
  items.forEach((el) => io.observe(el));
  counters.forEach((el) => io.observe(el));
}

function initTabs(): void {
  document.querySelectorAll<HTMLElement>("[data-tabs]").forEach((root) => {
    const tabs = Array.from(root.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
    const ink = root.querySelector<HTMLElement>(".tab-ink");
    const select = (tab: HTMLButtonElement, focus = false) => {
      for (const t of tabs) {
        const on = t === tab;
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
        const panel = document.getElementById(t.getAttribute("aria-controls") ?? "");
        if (panel) panel.hidden = !on;
      }
      if (ink) {
        ink.style.width = `${tab.offsetWidth}px`;
        ink.style.transform = `translateX(${tab.offsetLeft}px)`;
      }
      if (focus) tab.focus();
    };
    tabs.forEach((t, i) => {
      t.addEventListener("click", () => select(t));
      t.addEventListener("keydown", (ev) => {
        const k = ev.key;
        let j = -1;
        if (k === "ArrowRight") j = (i + 1) % tabs.length;
        else if (k === "ArrowLeft") j = (i - 1 + tabs.length) % tabs.length;
        else if (k === "Home") j = 0;
        else if (k === "End") j = tabs.length - 1;
        if (j >= 0) {
          ev.preventDefault();
          select(tabs[j], true);
        }
      });
    });
    const first = tabs.find((t) => t.getAttribute("aria-selected") === "true") ?? tabs[0];
    if (first) select(first);
    window.addEventListener("resize", () => {
      const cur = tabs.find((t) => t.getAttribute("aria-selected") === "true");
      if (cur) select(cur);
    });
  });
}

function initMenu(): void {
  const menu = document.querySelector<HTMLDetailsElement>("details.menu");
  if (!menu) return;
  const summary = menu.querySelector("summary");
  const header = document.querySelector<HTMLElement>(".site-header");
  const sync = () => {
    if (menu.open && header) document.documentElement.style.setProperty("--menu-top", `${Math.max(0, header.getBoundingClientRect().bottom)}px`);
    document.documentElement.classList.toggle("menu-open", menu.open);
    summary?.setAttribute("aria-label", menu.open ? "Close menu" : "Open menu");
  };
  menu.addEventListener("toggle", sync);
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && menu.open) {
      menu.open = false;
      summary?.focus();
    }
  });
  window.matchMedia("(min-width: 961px)").addEventListener("change", (m) => {
    if (m.matches && menu.open) menu.open = false;
  });
}

export function initChrome(): void {
  initTheme();
  initCopy();
  initFreshness();
  initHeader();
  initReveal();
  initTabs();
  initMenu();
}
