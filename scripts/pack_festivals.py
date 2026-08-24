#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""
Build the festival corpora as MBF packs.

Reproducible on purpose: `created_at` is pinned per pack rather than taken from
the clock, and mbf.Pack already sorts keys and fixes ZIP timestamps. Two builds
of the same data must be byte-identical or the digests stop meaning anything —
so this script rebuilds every pack and reports whether any changed, which is
also how we notice a corpus edit that nobody meant to ship.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shruti_astro.core.festival_registry import CORPORA, load  # noqa: E402
from shruti_astro.packs.mbf import Pack, Payload  # noqa: E402

DIST = ROOT / "packs" / "dist"

SPEC = {
    "attic": {
        "slug": "shruti-attic-festivals",
        "name": "The Attic Festival Calendar",
        # 0.2.0: the 0.1.0 pack was stale. The corpus had gained competing
        # dates, alternate names and the attested/conventional split of the
        # deities, none of which were in the packed payload.
        "version": "0.2.0",
        # The standard reference works for the corpus as a whole. They are
        # cited by no single entry, so deriving citations from entries alone
        # would silently drop them.
        "bibliography": [
            {"author": "H. W. Parke", "work": "Festivals of the Athenians", "locus": None},
            {"author": "L. Deubner", "work": "Attische Feste", "locus": None},
            {"author": "J. D. Mikalson",
             "work": "The Sacred and Civil Calendar of the Athenian Year", "locus": None},
            {"author": "E. Simon", "work": "Festivals of Attica", "locus": None},
        ],
        "created_at": "2026-08-24T00:00:00+00:00",
        "description": (
            "The festival calendar of Athens, anchored to the noumenia rather "
            "than to civil dates. Days are graded attested, conventional or "
            "disputed, and festivals the sources cannot date carry their "
            "reconstructions and who proposed them instead of a guess."
        ),
    },
    "hindu": {
        "slug": "shruti-hindu-festivals",
        "name": "The Hindu Festival Calendar",
        "version": "0.1.0",
        "created_at": "2026-08-24T00:00:00+00:00",
        "bibliography": [
            {"author": "P. V. Kane", "work": "History of Dharmaśāstra", "locus": "Vol. V"},
            {"author": "R. Sewell and S. B. Dikshit",
             "work": "The Indian Calendar", "locus": None},
            {"author": "M. M. Underhill", "work": "The Hindu Religious Year", "locus": None},
            {"author": "Kāśīnātha Upādhyāya", "work": "Dharmasindhu", "locus": None},
            {"author": "Kamalākara Bhaṭṭa", "work": "Nirṇayasindhu", "locus": None},
        ],
        "description": (
            "Hindu festivals anchored to tithi, nakṣatra and solar ingress "
            "rather than to civil dates, so they resolve for any year and any "
            "place. Where traditions genuinely disagree — smārta against "
            "vaiṣṇava on ekādaśī, north against Deccan on Vaṭa Sāvitrī — the "
            "entry carries both and labels them instead of ruling. Entries "
            "carry a `restriction` field: initiatory and detail-withheld "
            "material is named but not expounded."
        ),
    },
}


def _citations(spec: dict, corpus) -> list[dict]:
    """Corpus-level bibliography first, then every entry citation, deduplicated.

    The same work is cited by many entries — Kane alone appears sixty-six
    times — and a manifest listing it sixty-six times tells a reader nothing.
    """
    seen: set[tuple] = set()
    out: list[dict] = []
    derived = ({"author": s.get("author"), "work": s.get("work"),
                "locus": s.get("locus")}
               for e in corpus.entries for s in e.get("sources", []))
    for c in [*spec.get("bibliography", []), *derived]:
        key = (c.get("author"), c.get("work"), c.get("locus"))
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def build(tradition: str) -> tuple[Path, str, bool]:
    spec = SPEC[tradition]
    corpus = load(tradition)
    if not corpus.verified:
        raise SystemExit(f"refusing to pack {tradition}: corpus is not verified")

    payload = Payload(kind="festival-calendar",
                      path="payloads/festival-calendar.json",
                      items=corpus.entries)
    pack = Pack(
        slug=spec["slug"], name=spec["name"], version=spec["version"],
        description=spec["description"], author_name="Soror Eu. A.",
        spdx="CC-BY-SA-4.0", created_at=spec["created_at"],
        # The packs carry no closed material. Where a tradition's detail is
        # restricted the entry names the observance and withholds the detail,
        # flagged in `restriction` so a consumer can filter on it.
        closed_tradition=False,
        closed_tradition_note=(
            "No closed material is carried. Entries whose detail is restricted "
            "are marked `restriction: initiatory` or `detail-withheld` and are "
            "limited to what is publicly kept."
        ),
        source_citations=_citations(spec, corpus),
        payloads=[payload],
    )
    out = DIST / f"{spec['slug']}-v{spec['version']}.mbf"
    before = hashlib.sha256(out.read_bytes()).hexdigest() if out.exists() else None
    pack.write(out)
    after = hashlib.sha256(out.read_bytes()).hexdigest()
    return out, after, before is not None and before != after


if __name__ == "__main__":
    changed = []
    for tradition in sorted(CORPORA):
        path, digest, differs = build(tradition)
        n = len(load(tradition).entries)
        flag = "  CHANGED" if differs else ""
        print(f"  {path.name:<42} {n:>3} entries  {digest[:16]}{flag}")
        if differs:
            changed.append(path.name)
    if changed:
        print(f"\n  {len(changed)} pack(s) differ from the previous build: "
              f"{', '.join(changed)}")
