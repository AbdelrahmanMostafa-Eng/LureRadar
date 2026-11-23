#!/usr/bin/env bash
# Build the wheel, install it into a brand-new virtualenv (no repo on the path),
# and prove the README quickstart works offline. Also exercises `uvx`.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf dist
uv build >/dev/null
wheel="$(ls dist/lureradar-*.whl)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
python3 -m venv "$tmp/venv"
"$tmp/venv/bin/python" -m pip install --quiet "$wheel"
cd "$tmp"  # make sure nothing is imported from the repository checkout
set +e
"$tmp/venv/bin/lureradar" check "https://rockstar-gta6-pc-download[.]test/free-key" > out.txt
code=$?
set -e
grep -q "LIKELY LURE" out.txt
grep -q "hxxps://rockstar-gta6-pc-download\[.\]test/free-key" out.txt
[ "$code" -eq 20 ] || { echo "unexpected exit code $code"; exit 1; }
"$tmp/venv/bin/lureradar" pack list >/dev/null
"$tmp/venv/bin/lureradar" pcwatch history >/dev/null
"$tmp/venv/bin/python" -c "from lureradar.scoring.engine import quick_check; assert quick_check('www.ign.com').tier.value == 'clear'"
echo "wheel install OK: $(basename "$wheel") (exit $code, bundled packs found)"
if command -v uvx >/dev/null 2>&1; then
  set +e
  uvx --quiet --from "$OLDPWD/$wheel" lureradar check "hxxps://gta6-pc-download[.]test" >/dev/null
  ucode=$?
  set -e
  [ "$ucode" -eq 10 ] || [ "$ucode" -eq 20 ] || { echo "uvx run failed ($ucode)"; exit 1; }
  echo "uvx run OK (exit $ucode)"
fi
