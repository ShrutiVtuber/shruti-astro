# Packs

Festival corpora built as **Magickal Bundle Format** so Theourgia's calendar and
Vedic modules can install them directly, rather than as a private table only this
project can read.

| pack | entries | verified |
|---|---|---|
| `shruti-attic-festivals-v0.1.0.mbf` | 45 | **yes** — audited across four lenses |
| Hindu | 71 | **not yet** — audit in flight; not packed |

## Why the Hindu corpus is not here

It is sourced, cited, and its day rules resolve to published 2026 almanac dates.
But it never went through the adversarial audit its Attic counterpart did — the
assembly agent dropped that half and the entries were recovered from a journal.
**Packing it would present unverified data with the same authority as verified
data**, which the format has no way to qualify once installed.

`GET /festivals` serves it meanwhile with `verified: false` and a note saying so.

## Rebuilding

```bash
docker run --rm --user root -v "$PWD:/src:ro" -v "$PWD/packs/dist:/out" \
  shruti-astro:dev sh -c "python /chk/pack.py && chown 1000:1000 /out/*.mbf"
```

Builds are byte-identical for the same input — sorted keys, fixed separators, a
pinned zip timestamp — so a rebuild that changes the digest means the data
changed, which is the point of recording it.

## The dayRule caveat, for whoever consumes these

MBF has no `dayRule` concept yet. The Attic pack does not need one; **a Hindu
pack will**, because Dīpāvalī is kept at pradoṣa and Mahā Śivarātri at niśītha,
and applying the sunrise rule to those puts each a day late. See the note left in
the theourgia phone repo.
