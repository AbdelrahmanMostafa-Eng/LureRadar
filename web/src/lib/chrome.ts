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

let fadeTimer = 0;
function initTheme(): void {
  // Track the mode synchronously: the view transition applies it a frame
  // later, and fast double-clicks must still advance one step each.
  let mode: Theme = currentTheme();
  applyTheme(mode);
  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    const next = THEMES[(THEMES.indexOf(mode) + 1) % THEMES.length];
    mode = next;
    // A short colour crossfade. (A view transition would swallow clicks while
    // it plays, so quick repeated toggles would be lost.)
    const root = document.documentElement;
    if (!reduceMotion()) {
      root.classList.add("theme-anim");
      window.clearTimeout(fadeTimer);
      fadeTimer = window.setTimeout(() => root.classList.remove("theme-anim"), 450);
    }
    applyTheme(next);
  });
}

/** Give a .btn a letter-by-letter roll label. The letters are aria-hidden;
 *  a visually-hidden copy keeps the accessible name exactly the same. */
export function rollLabel(btn: HTMLElement, text?: string): void {
  const host = btn.querySelector<HTMLElement>(":scope > .btn-label") ?? btn;
  if (text === undefined) {
    if (btn.dataset.rolled) return;
    const node = [...host.childNodes].find((n) => n.nodeType === Node.TEXT_NODE && n.textContent?.trim());
    if (!node) return;
    text = node.textContent!.trim();
    node.replaceWith(document.createTextNode(""));
  }
  host.querySelectorAll(":scope > .lbl, :scope > .lbl-sr").forEach((n) => n.remove());
  const lbl = document.createElement("span");
  lbl.className = "lbl";
  lbl.setAttribute("aria-hidden", "true");
  [...text].forEach((ch, i) => {
    const span = document.createElement("span");
    span.textContent = ch;
    span.style.setProperty("--n", String(i));
    lbl.append(span);
  });
  const sr = document.createElement("span");
  sr.className = "lbl-sr visually-hidden";
  sr.textContent = text;
  host.prepend(lbl, sr);
  btn.dataset.rolled = text;
}

function initButtons(): void {
  document.querySelectorAll<HTMLElement>(".btn").forEach((b) => rollLabel(b));
  // Buttons created later (drawer actions, verdict cards) get the same label.
  new MutationObserver((records) => {
    for (const r of records) {
      r.addedNodes.forEach((n) => {
        if (!(n instanceof HTMLElement)) return;
        if (n.matches(".btn")) rollLabel(n);
        n.querySelectorAll?.<HTMLElement>(".btn").forEach((b) => rollLabel(b));
      });
    }
  }).observe(document.body, { childList: true, subtree: true });
}

function initCopy(): void {
  document.addEventListener("click", async (ev) => {
    const target = (ev.target as HTMLElement | null)?.closest<HTMLElement>("[data-copy]");
    if (!target) return;
    const text = target.dataset.copy ?? "";
    const label = target.dataset.rolled ?? target.textContent ?? "Copy";
    const set = (t: string) => (target.classList.contains("btn") ? rollLabel(target, t) : (target.textContent = t));
    try {
      await navigator.clipboard.writeText(text);
      set("Copied");
      target.dataset.copied = "";
    } catch {
      set("Select & copy");
    }
    setTimeout(() => {
      set(label);
      delete target.dataset.copied;
    }, 1600);
  });
}

/** Radar lock-on: brackets fly from the pointer and frame the control under it. */
function initLockOn(): void {
  if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
  const SEL = ".btn, .icon-btn, .nav a, .arrow-link, [role='tab'], .faq summary, .doclist a, .toc a, .doc-nav a, .brand, .site-footer a, .contacts button, .radar .c";
  const box = document.createElement("div");
  box.className = "lockon";
  box.setAttribute("aria-hidden", "true");
  const corners = [0, 1, 2, 3].map(() => box.appendChild(document.createElement("i")));
  document.body.append(box);
  const S = 9; // corner size
  let target: HTMLElement | null = null;
  let px = 0, py = 0;
  const place = (x: number, y: number, w: number, h: number, pad: number) => {
    const pts = [[x - pad, y - pad], [x + w + pad - S, y - pad], [x + w + pad - S, y + h + pad - S], [x - pad, y + h + pad - S]];
    corners.forEach((c, i) => (c.style.transform = `translate3d(${pts[i][0]}px, ${pts[i][1]}px, 0)`));
  };
  const collapse = () => place(px - 8, py - 8, 16, 16, 0);
  const frame = () => {
    if (!target) return;
    const r = target.getBoundingClientRect();
    if (target.matches(".radar .c")) place(r.left - 11, r.top - 11, 22, 22, 0);
    else place(r.left, r.top, r.width, r.height, 5);
  };
  document.addEventListener("pointermove", (e) => { px = e.clientX; py = e.clientY; if (!target) collapse(); }, { passive: true });
  document.addEventListener("pointerover", (e) => {
    const t = (e.target as HTMLElement).closest<HTMLElement>(SEL);
    if (!t || t === target) return;
    if (!target) collapse();
    target = t;
    requestAnimationFrame(() => { frame(); box.classList.add("on"); });
  });
  document.addEventListener("pointerout", (e) => {
    if (!target) return;
    const to = e.relatedTarget as Node | null;
    if (to && target.contains(to)) return;
    target = null;
    collapse();
    box.classList.remove("on");
  });
  window.addEventListener("scroll", () => requestAnimationFrame(frame), { passive: true });
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
  initButtons();
  initCopy();
  initLockOn();
  initFreshness();
  initHeader();
  initReveal();
  initTabs();
  initMenu();
}
