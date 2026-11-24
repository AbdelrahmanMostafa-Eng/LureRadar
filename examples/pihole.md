# Pi-hole

1. Open the Pi-hole admin page → **Adlists** (Pi-hole v5) or **Lists** (v6).
2. Add this address and give it a comment such as `LureRadar launch lures`:

   ```text
   https://lureradar.vercel.app/feeds/hosts.txt
   ```

3. Update gravity: **Tools → Update Gravity**, or:

   ```bash
   pihole -g
   ```

Pi-hole also accepts the plain list `feeds/domains.txt`. Both contain only
LIKELY and CONFIRMED indicators. The feed refreshes daily (best-effort); Pi-hole
re-downloads lists on its weekly gravity run unless you schedule more often.

Something blocked that should not be? Use the dispute link in
[docs/FEEDS.md](../docs/FEEDS.md#disputes-and-removal).
