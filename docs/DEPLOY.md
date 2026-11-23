# Deploying the site

LureRadar's public product is a **static site** (dashboard, checker, docs,
feeds) plus files produced by GitHub Actions. There is no application server:
the browser checker runs client-side and the Python package is a CLI/library
used at build time and in scheduled workflows.

## GitHub Pages (canonical)

`pages.yml` builds `web/` with real feeds from the rolling `feeds-latest` and
`pcwatch-latest` releases and deploys it. The base URL is
`DEFAULT_BASE_URL` in `src/lureradar/config.py` (a sub-path deployment,
`/LureRadar/`). Enable it under Settings → Pages → Source: *GitHub Actions*.

## Vercel

`vercel.json` defines one Vercel service, `web` (Astro, root `web/`),
exposed publicly on `/` by a catch-all rewrite:

```json
{
  "services": {
    "web": { "root": "web/", "framework": "astro", "buildCommand": "bash scripts/vercel-build.sh" }
  },
  "rewrites": [{ "source": "/(.*)", "destination": { "service": "web" } }]
}
```

`web/scripts/vercel-build.sh`:

1. sets `LURERADAR_BASE_URL` to the deployment's own URL from Vercel's system
   variables (`VERCEL_PROJECT_PRODUCTION_URL` in production,
   `VERCEL_BRANCH_URL` or `VERCEL_URL` in previews), so links, canonical URLs,
   sitemap and OG images are served from `/`, not `/LureRadar/`. Set
   `LURERADAR_BASE_URL` in the Vercel project to pin a custom domain;
2. installs `uv` with pip if the build image lacks it;
3. downloads the published feeds from the repository's rolling releases
   (`VERCEL_GIT_REPO_OWNER` / `VERCEL_GIT_REPO_SLUG`), or falls back to
   clearly labelled demo data when none exist yet;
4. runs `scripts/build_site_data.py`, `npm run build` and the checker parity
   test (a drifted checker fails the deploy).

There are no service bindings: the site has no server-side functions and no
service calls another at runtime; the browser fetches `data/rules.json` and
`feeds/*` from the same origin.

Local check of the Vercel build (simulated system variables):

```bash
cd web && VERCEL_ENV=production VERCEL_PROJECT_PRODUCTION_URL=example.vercel.app bash scripts/vercel-build.sh
```

With the Vercel CLI linked to a project, `vercel dev` runs the service locally.
