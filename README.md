# shruti-astro

Astrological computation service for **shrutivtuber.com** — Hellenistic and
Vedic side by side.

**Licence: AGPL-3.0-only. This repository is public, and must stay public.**

## Why this is a separate repository *and* a separate program

Swiss Ephemeris is dual-licensed AGPL-3.0 or commercial. The commercial licence
is bought for Theourgia and astropractise; it is deliberately **not** bought for
the public tools on shrutivtuber.com, which therefore run under the AGPL arm.

AGPL-3.0 **§13** requires that anyone interacting with the software *over a
network* be offered the Corresponding Source of the whole combined work. If the
website's backend linked `pyswisseph` in its own process, the entire website
backend would become AGPL and its complete source would have to be offered to
every visitor of every page.

A separate repo does not achieve that on its own — licence boundaries follow the
**program** boundary, not the git remote. So this is a separate program: its own
process, its own container, reached only over an HTTP JSON API. The website
calls it at arm's length and stays outside the copyleft.

Three rules follow, and none of them are optional:

1. **This repo is public.** A private repo serving an AGPL network service is a
   licence violation the moment a tool goes live.
2. **Every page that consumes this service links its source at the running
   commit.** §13 asks for the source of the version actually running, not
   whatever is on `main` — hence `GET /version`.
3. **No code is shared with Theourgia.** Not a package, not a vendored module,
   not a copied file. Theourgia's engine runs under the commercial licence;
   copying in either direction contaminates one side.

See `docs/adr/0001-astrology-licensing.md` in the shrutivtubersite repo.

## Scope

Hellenistic and Vedic are first-class together, not one bolted onto the other:

| | |
|---|---|
| **Shared** | Swiss Ephemeris positions, houses, planetary hours, timezone and DST handling |
| **Hellenistic** | Whole-sign places, the seven Hermetic lots, essential dignities, bounds and decans, sect |
| **Vedic** | Sidereal with selectable ayanāṁśa, pañcāṅga (tithi · nakṣatra · yoga · karaṇa), daśās |

## Endpoints

| | |
|---|---|
| `GET /health` | liveness |
| `GET /version` | build SHA — what §13 source links must point at |
| `GET /planetary-hours` | current hour and its ruler, for a location |
| `GET /panchanga` | tithi, nakṣatra, yoga, karaṇa for a date and place |
| `GET /chart` | positions, houses, aspects — tropical and sidereal |
| `GET /rise-conventions` | the sunrise toggle — both traditions, described |
| `GET /ayanamsas` | the six ayanāṁśas |

## Sunrise is a toggle, not a setting

Sophia practises both traditions, so the daemon serves both definitions rather
than merging them:

| Convention | Definition | Used by |
|---|---|---|
| `visible_disc` *(default)* | upper limb of the apparent disc, **with** refraction | Hellenistic planetary hours, Western almanacs |
| `hindu` | centre of the disc, **no** refraction | Indian pañcāṅgas, the Vedic day boundary |

Measured difference in Athens: **~4.6 minutes**. That is enough to move a
tithi-at-sunrise across a boundary, which is why picking one globally would
quietly corrupt the other.

`GET /panchanga?at_sunrise=true&lat=&lon=` is the mode that reproduces a printed
Indian almanac: almanacs name the day by the tithi prevailing *at sunrise* under
the Hindu convention, so asking at noon can legitimately disagree by a day.

## Running

```bash
docker compose up --build      # serves on 127.0.0.1:8201
```
