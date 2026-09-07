# SERVER ACCESS — read this before touching anything deployed

**The whole estate moved off Hetzner onto one netcup box on 3 September 2026.
Every Hetzner server is gone. Any old IP, host or deploy path in this repo's
docs is stale.**

## The server

| | |
|---|---|
| Host | `159.195.251.161` (netcup RS 8000 · 16 cores · 64 GB · 2 TB · Debian 13) |
| IPv6 | `2a0a:4cc0:60:2330:460:1bff:fe04:4f25` |
| Agents SSH | `ssh -i ~/.ssh/agents_netcup deploy@159.195.251.161` |
| Sophia SSH | `ssh -i ~/.ssh/sophia_netcup deploy@159.195.251.161` |

Those two keys are the ONLY ones. The old per-box keys (`sakurastudios`,
`agent-house-access-theourgia`, `hetzner-migration`) are retired — the boxes
they opened no longer exist.

## How the box is laid out

- **One host Caddy owns :80/:443** for every domain: `/etc/caddy/Caddyfile`
  with one file per site in `/etc/caddy/Caddyfile.d/*.caddy`. It terminates TLS
  (Let's Encrypt via Cloudflare DNS-01) and reverse-proxies to each stack on a
  **loopback port**. Its Cloudflare token lives in `/etc/caddy/caddy.env`.
- **Every stack binds 127.0.0.1 only.** Port assignments are in `/srv/PORTS.md`
  — check there before choosing one, never pick ad hoc.
- ⚠ After editing `/etc/caddy/caddy.env` you must **`systemctl restart caddy`**,
  not reload — a reload does not re-read systemd's EnvironmentFile.
- ⚠ A stack Caddy behind the host Caddy needs BOTH `auto_https off` **and**
  `http://` on every site address, or it still binds :443 and fights the host.

## Backups

Nightly, offsite to Cloudflare R2, and **alarmed**: a failed or stale backup
writes a banner you will see on your next SSH login, plus a syslog error.
Status files are in `/var/lib/netcup-backups/`, logs in
`/var/log/netcup-backups/`. Never add a second backup cron for a stack that
already has one — the old boxes double-ran theirs for months.

## This project on the server

| | |
|---|---|
| Stack | shruti-astro |
| Path | `/srv/shruti-astro/prod` |
| Loopback port | 8201 |
| Runs as | `theourgia` |
| Deploy | `cd /srv/shruti-astro/prod && docker compose up -d` |
| Serves | (internal; joins the shruti-interop network) |

## Full record

- `/home/sophia/MIGRATION-PLAN.md` — the complete migration, phase by phase,
  including every fault found and fixed.
- `/home/sophia/MIGRATION-hetzner-to-netcup.md` — the access map.
- `/home/sophia/ROLLBACK-*.md` — per-service DNS rollback records (historical;
  the Hetzner boxes are deleted, so these are reference only).
- `/srv/_hetzner-attic/` on the server — everything from the old boxes that was
  not part of a running service, kept so nothing was lost on deletion.
