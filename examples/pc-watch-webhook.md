# PC Watch notifications to Discord or Slack

LureRadar has no accounts and sends no email. To get PC Watch updates in a
chat channel, poll the public JSON and post when the status changes. Run it
from your own scheduler or a forked GitHub Action.

```bash
#!/usr/bin/env bash
# pcwatch-notify.sh - post to a Discord/Slack webhook when the PC Watch status changes.
set -euo pipefail
FEED="https://abdelrahmanmostafa-eng.github.io/LureRadar/feeds/pc-watch.json"
STATE_FILE="${STATE_FILE:-$HOME/.cache/pcwatch-last-status}"
WEBHOOK_URL="${WEBHOOK_URL:?set WEBHOOK_URL to your Discord or Slack incoming webhook}"

json="$(curl -fsS "$FEED")"
status="$(printf '%s' "$json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
answer="$(printf '%s' "$json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["answer"])')"
last="$(cat "$STATE_FILE" 2>/dev/null || true)"

if [ "$status" != "$last" ]; then
  # Discord expects {"content": ...}; Slack expects {"text": ...}
  payload="$(python3 -c 'import json,sys; print(json.dumps({"content": sys.argv[1], "text": sys.argv[1], "allowed_mentions": {"parse": []}}))' "PC Watch: $answer")"
  curl -fsS -H 'Content-Type: application/json' -d "$payload" "$WEBHOOK_URL"
  mkdir -p "$(dirname "$STATE_FILE")"
  printf '%s' "$status" > "$STATE_FILE"
fi
```

Python users can build the same payload with
`lureradar.pcwatch.notify.webhook_payload(state, "discord" | "slack")`.

## As a GitHub Action in your fork

```yaml
name: PC Watch notify
on:
  schedule: [{ cron: "41 */6 * * *" }]
  workflow_dispatch:
permissions: { contents: read }
jobs:
  notify:
    runs-on: ubuntu-latest
    steps:
      - name: Restore last status
        uses: actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0
        with: { path: .pcwatch-last, key: "pcwatch-${{ github.run_id }}", restore-keys: pcwatch- }
      - name: Notify on change
        env:
          WEBHOOK_URL: ${{ secrets.PCWATCH_WEBHOOK_URL }}
          STATE_FILE: .pcwatch-last
        run: bash ./pcwatch-notify.sh
```

Keep the webhook URL in a repository secret. Respect the feed's cache: polling
more than every 30 minutes gains nothing, since PC Watch itself runs every 4 hours.
