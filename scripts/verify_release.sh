#!/usr/bin/env bash
# Verify a downloaded LureRadar release artifact before installing it.
#
#   scripts/verify_release.sh lureradar-0.1.0-py3-none-any.whl
#
# Checks (each needs its tool; missing tools are reported, never skipped silently):
#  1. GitHub build-provenance attestation  (gh attestation verify)
#  2. Sigstore signature bundle            (python -m sigstore verify github)
#  3. SHA-256 against SHA256SUMS            (sha256sum)
set -euo pipefail
REPO="AbdelrahmanMostafa-Eng/LureRadar"
artifact="${1:?usage: verify_release.sh <artifact> [SHA256SUMS] [bundle]}"
sums="${2:-SHA256SUMS}"
bundle="${3:-${artifact}.sigstore.json}"
status=0

if command -v gh >/dev/null 2>&1; then
  echo "== build provenance (GitHub attestation)"
  gh attestation verify "$artifact" --repo "$REPO" || status=1
else
  echo "!! gh not installed: cannot check the build-provenance attestation"; status=1
fi

if python3 -c "import sigstore" 2>/dev/null; then
  echo "== Sigstore signature"
  python3 -m sigstore verify github "$artifact" --bundle "$bundle" \
    --repository "$REPO" --trigger release || status=1
else
  echo "!! sigstore not installed (pip install sigstore): cannot check the signature"; status=1
fi

if [ -f "$sums" ]; then
  echo "== SHA-256"
  grep " $(basename "$artifact")\$" "$sums" | sha256sum -c - || status=1
else
  echo "!! $sums not found next to the artifact"; status=1
fi

[ "$status" -eq 0 ] && echo "release artifact verified" || echo "VERIFICATION INCOMPLETE OR FAILED"
exit "$status"
