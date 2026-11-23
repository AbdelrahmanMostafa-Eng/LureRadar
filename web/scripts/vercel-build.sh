#!/usr/bin/env bash
# Build command for the `web` service on Vercel (vercel.json -> services.web).
# Runs in web/ after Vercel's `npm install`. See docs/DEPLOY.md.
set -euo pipefail
cd "$(dirname "$0")/.."            # web/
ROOT="$(cd .. && pwd)"             # repository root (Python package, packs, scripts)

# 1. Base URL of THIS deployment. The site's links, canonical URLs and OG images
#    derive from LURERADAR_BASE_URL (src/lureradar/config.py, web/astro.config.mjs).
#    On Vercel the site is served at "/", not GitHub Pages' "/LureRadar/".
#    Set LURERADAR_BASE_URL in the project's environment variables to pin a
#    custom domain; otherwise use Vercel's system variables.
if [ -z "${LURERADAR_BASE_URL:-}" ]; then
  if [ "${VERCEL_ENV:-}" = "production" ] && [ -n "${VERCEL_PROJECT_PRODUCTION_URL:-}" ]; then
    host="$VERCEL_PROJECT_PRODUCTION_URL"
  else
    host="${VERCEL_BRANCH_URL:-${VERCEL_URL:-}}"
  fi
  if [ -n "$host" ]; then
    export LURERADAR_BASE_URL="https://${host}/"
  fi
fi
echo "LureRadar base URL: ${LURERADAR_BASE_URL:-<DEFAULT_BASE_URL from src/lureradar/config.py>}"

# 2. uv for the Python data generator (never `curl | sh`).
if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip --version >/dev/null 2>&1 || python3 -m ensurepip --user >/dev/null
  python3 -m pip install --quiet --user uv
  export PATH="$HOME/.local/bin:$PATH"
fi

# 3. Published feeds from the rolling GitHub releases written by feed-refresh.yml
#    and pc-watch.yml. Until they exist, the site shows labelled demo data.
feeds="$ROOT/build/public/feeds"
rm -rf "$feeds" && mkdir -p "$feeds"
if [ -n "${VERCEL_GIT_REPO_OWNER:-}" ] && [ -n "${VERCEL_GIT_REPO_SLUG:-}" ]; then
  releases="https://github.com/${VERCEL_GIT_REPO_OWNER}/${VERCEL_GIT_REPO_SLUG}/releases/download"
  fetch() {  # fetch <release-tag> <file>; missing files are fine
    curl -fsSL --max-time 30 -o "$feeds/$2" "$releases/$1/$2" 2>/dev/null || rm -f "$feeds/$2"
  }
  for f in latest.json all.json stats.json hosts.txt domains.txt adguard.txt rpz.zone \
           stix.json indicators.csv SHA256SUMS shields-detections-24h.json \
           shields-active.json shields-updated.json shields-fpr.json; do
    fetch feeds-latest "$f"
    fetch feeds-latest "$f.minisig"
  done
  for f in pc-watch.json pc-watch.atom shields-pc-watch.json; do
    fetch pcwatch-latest "$f"
  done
fi
feeds_arg=()
if [ -f "$feeds/latest.json" ]; then
  feeds_arg=(--feeds "$feeds")
  echo "using published feeds"
else
  echo "no published feeds yet: building with labelled demo data"
fi
(cd "$ROOT" && uv run --locked --no-dev --extra render python scripts/build_site_data.py "${feeds_arg[@]}")

# 4. Static build (output: web/dist). The parity test fails the deploy if the
#    browser checker drifted from the Python engine.
npm run build
npm test
