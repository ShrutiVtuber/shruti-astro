# Deploying shruti-astro

## Where it runs

`agent-house`, alongside the site. Port map:

| | |
|---|---|
| 8090 | daskalos |
| 8190 | theourgia |
| 8200 | shrutivtuber.com — the site |
| **8201** | **shruti-astro — this daemon** |
| 8210 | astropractise |

```bash
ssh -i ~/.ssh/agent-house-access-theourgia theourgia@178.105.106.225
cd /srv/shruti-astro/prod
```

Pulls over a **read-only deploy key** (`~/.ssh/shruti-astro-deploy`, host alias
`github-shruti-astro`). The server cannot push.

## Deploy

```bash
cd /srv/shruti-astro/prod
git pull --ff-only
SHRUTI_ASTRO_SHA=$(git rev-parse --short HEAD) docker compose up -d --build
```

**Always pass `SHRUTI_ASTRO_SHA`.** It is baked into the image and returned by
`GET /version` — see below.

## The AGPL obligation is operational, not paperwork

This daemon links Swiss Ephemeris under the **AGPL arm**, so §13 requires that
anyone interacting with it over a network be offered the Corresponding Source
**for the version actually running**.

Three things must stay true, and all three are checkable:

```bash
# 1. /version reports the running commit
curl -s http://127.0.0.1:8201/version

# 2. every response carries the offer
curl -sI http://127.0.0.1:8201/health | grep -i x-source

# 3. the URL it names actually resolves, anonymously
curl -o /dev/null -w '%{http_code}\n' \
  "$(curl -s http://127.0.0.1:8201/version | python3 -c 'import sys,json;print(json.load(sys.stdin)["sourceUrl"])')"
```

That third check is the one that quietly breaks. **Deploying a commit that was
never pushed makes `/version` point at a tree nobody can fetch** — the daemon
then claims to offer source it does not offer, which is the violation, and it
leaves no error anywhere. Push before you deploy, and verify the 200.

**The repository must stay public.** Making it private is an immediate violation
the moment anyone uses a tool.

Verified at the last deploy rather than assumed: the source URL returned 200,
the repo is public with `AGPL-3.0` declared, `LICENSE` is the full Affero text,
and the running commit was reachable in an anonymous clone.

## Health

```bash
docker compose ps
docker stats --no-stream shruti-astro-astro-1     # 512m / 0.75 cpu ceiling
curl -s "http://127.0.0.1:8201/today?lat=37.9838&lon=23.7275"
```

Steady state is around 100 MB — most of it the Python runtime, since the Moshier
ephemeris needs no data files.

## Not yet routed publicly

Nothing proxies to 8201 from outside. When the tool pages exist, either route
`/api/astro/*` there from the site's internal Caddy, or give it its own
hostname. Whichever it is, the §13 source link must be visible **on the tool
pages themselves**, not only in a response header the visitor never sees.
