# AdGuard Home and AdGuard apps

**AdGuard Home:** Filters → DNS blocklists → *Add blocklist* → *Add a custom list*:

```text
https://abdelrahmanmostafa-eng.github.io/LureRadar/feeds/adguard.txt
```

**AdGuard browser extension / apps:** Settings → Filters → Custom → *Add
custom filter* → paste the same URL.

The list uses Adblock syntax (`||domain^`), which blocks the domain and all its
subdomains. It declares `! Expires: 1 day`, so AdGuard refreshes it daily.
