# Unbound (and BIND) with the RPZ zone

`feeds/rpz.zone` is a Response Policy Zone: each indicator and its subdomains
answer NXDOMAIN.

## Unbound (1.10+)

```text
server:
    module-config: "respip validator iterator"

rpz:
    name: rpz.lureradar.invalid.
    url: https://lureradar.vercel.app/feeds/rpz.zone
    zonefile: /var/lib/unbound/lureradar.rpz
    rpz-log: yes
    rpz-log-name: lureradar
```

Unbound downloads the zone over HTTPS and re-checks it on the SOA refresh
interval (1 hour). Verify the signature out of band if you mirror the file
(see [docs/FEEDS.md](../docs/FEEDS.md#verify-what-you-download)).

## BIND 9

Fetch the file with a cron job (BIND cannot transfer RPZ over HTTPS), then:

```text
options {
    response-policy { zone "rpz.lureradar.invalid"; };
};
zone "rpz.lureradar.invalid" {
    type primary;
    file "/var/lib/bind/lureradar.rpz";
};
```
