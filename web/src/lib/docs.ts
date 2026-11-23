// Build-time Markdown rendering of the repository's docs/*.md (trusted,
// first-party content). Relative links are rewritten to site pages or to the
// repository on GitHub. Missing files are tolerated.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { Marked } from "marked";
import { REPO_URL, href } from "./site";

export const DOCS_DIR = join(process.cwd(), "..", "docs");

export const slugOf = (file: string): string => file.replace(/\.md$/i, "").toLowerCase().replaceAll("_", "-");

export function listDocs(): { slug: string; file: string; title: string }[] {
  if (!existsSync(DOCS_DIR)) return [];
  return readdirSync(DOCS_DIR)
    .filter((f) => f.endsWith(".md"))
    .sort()
    .map((file) => {
      const text = readFileSync(join(DOCS_DIR, file), "utf8");
      const title = text.split("\n").find((l) => l.startsWith("# "))?.slice(2).trim() ?? file;
      return { slug: slugOf(file), file, title };
    });
}

function rewrite(link: string): string {
  if (/^[a-z][a-z0-9+.-]*:/i.test(link) || link.startsWith("#") || link.startsWith("//")) return link;
  const [path, anchor] = link.split("#");
  const suffix = anchor ? `#${anchor}` : "";
  const clean = path.replace(/^\.\//, "");
  if (/^[^/]+\.md$/i.test(clean)) return href(`docs/${slugOf(clean)}/`) + suffix;
  if (clean.startsWith("../")) {
    const repoPath = clean.replace(/^(\.\.\/)+/, "");
    return `${REPO_URL}/blob/main/${repoPath}${suffix}`;
  }
  return `${REPO_URL}/blob/main/docs/${clean}${suffix}`;
}

export function renderDoc(file: string): { html: string; title: string } | null {
  const path = join(DOCS_DIR, file);
  if (!existsSync(path)) return null;
  const text = readFileSync(path, "utf8");
  const title = text.split("\n").find((l) => l.startsWith("# "))?.slice(2).trim() ?? file;
  const marked = new Marked({ gfm: true });
  marked.use({
    walkTokens(token) {
      if (token.type === "link" || token.type === "image") token.href = rewrite(token.href);
    },
    renderer: {
      heading({ tokens, depth }) {
        const text = this.parser.parseInline(tokens);
        const id = text.replace(/<[^>]+>/g, "").toLowerCase().replace(/[^\w\- ]/g, "").trim().replaceAll(" ", "-");
        return `<h${depth} id="${id}">${text}</h${depth}>\n`;
      },
    },
  });
  // drop the first H1 (rendered by the page) to avoid duplicate h1 elements
  const body = text.replace(/^# .*\n/m, "");
  const html = (marked.parse(body, { async: false }) as string)
    // scrollable code blocks must be keyboard-focusable (WCAG 2.1.1)
    .replaceAll("<pre>", '<pre tabindex="0">')
    .replace(/<table>/g, '<div class="table-wrap" tabindex="0" role="region" aria-label="Scrollable table"><table>')
    .replace(/<\/table>/g, "</table></div>");
  return { html, title };
}

/** Reading order for the docs index and sidebar; unknown docs sort after these, by title. */
export const DOC_ORDER = ["quickstart", "how-it-works", "signals", "feeds", "pc-watch", "packs", "schema", "sources", "benchmarks", "threat-model", "privacy", "ethics-and-abuse", "deploy", "decisions"];
