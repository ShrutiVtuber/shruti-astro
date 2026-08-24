# SPDX-License-Identifier: AGPL-3.0-only
"""
Loading festival corpora and resolving a year of them.

**Verification status travels with the data.** The Attic corpus went through an
adversarial audit; the Hindu one has not yet. A consumer is entitled to know
which it is looking at, so every response says so rather than presenting both
with equal authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from shruti_astro.core.festivals import Resolved, resolve

DATA = Path(__file__).resolve().parent.parent / "data"

# Fields the anchor carries for provenance rather than computation. The resolver
# ignores unknown keys, but stripping them keeps the anchor legible in output.
_PROVENANCE_KEYS = (
    "dayCertainty", "dayBeginsAtSunset", "dayBasis", "dayCandidates",
    "dayReconstructions", "spanReconstructions", "elaboratedYear",
    "sourceCount", "dayRuleReason", "monthSpellingNormalised",
    "dayRuleUnmodelled", "hollowMonthRuleContested", "decad", "recurrence",
    "note", "monthNote",
)


@dataclass
class Corpus:
    tradition: str
    entries: list[dict]
    verified: bool
    verification_note: str


CORPORA = {
    "attic": {
        "file": "attic-festivals.json",
        "verified": True,
        "note": "Audited adversarially across four lenses. Days graded "
                "attested / conventional / disputed; several festivals are "
                "recorded as undatable rather than given a guessed day.",
    },
    "hindu": {
        "file": "hindu-festivals.json",
        "verified": False,
        "note": "PROVISIONAL — sourced and cited, day rules verified against "
                "published 2026 almanac dates, but this corpus has not yet "
                "passed the adversarial audit its Attic counterpart did. "
                "Treat dates as good but unconfirmed.",
    },
}


@lru_cache(maxsize=4)
def load(tradition: str) -> Corpus:
    if tradition not in CORPORA:
        raise ValueError(f"unknown tradition; choose from {sorted(CORPORA)}")
    spec = CORPORA[tradition]
    entries = json.loads((DATA / spec["file"]).read_text())
    return Corpus(tradition=tradition, entries=entries,
                  verified=spec["verified"], verification_note=spec["note"])


def _clean(anchor: dict | None) -> dict | None:
    if not anchor:
        return anchor
    return {k: v for k, v in anchor.items() if k not in _PROVENANCE_KEYS}


def year(tradition: str, gregorian_year: int, **kw) -> dict:
    """
    Every occurrence in the year, with the undatable ones reported as such.

    Undated entries are returned alongside the dated ones rather than filtered
    out. A festival that cannot be dated is a fact about the record, and
    dropping it silently would leave a consumer believing the corpus is smaller
    and more certain than it is.
    """
    corpus = load(tradition)
    dated: list[dict] = []
    undated: list[dict] = []

    for entry in corpus.entries:
        anchor = _clean(entry.get("anchor"))
        try:
            result = resolve(anchor, gregorian_year, **kw)
        except Exception as exc:                   # noqa: BLE001
            undated.append({
                "key": entry.get("key"), "name": entry.get("name"),
                "reason": f"could not resolve: {exc}",
            })
            continue

        occurrences: list[Resolved] = result if isinstance(result, list) else [result]
        placed = False
        for r in occurrences:
            if r.date is None:
                continue
            placed = True
            dated.append({
                "key": entry.get("key"), "name": entry.get("name"),
                "date": r.date.isoformat(),
                "summary": entry.get("summary", ""),
                "confidence": entry.get("confidence"),
                "tags": entry.get("tags", []),
                "note": r.note,
                "doubled": r.doubled,
                "lasts": entry.get("lasts"),
                "sources": entry.get("sources", []),
            })
        if not placed:
            reason = (occurrences[0].skipped_reason if occurrences
                      else "no occurrence this year")
            undated.append({
                "key": entry.get("key"), "name": entry.get("name"),
                "reason": reason,
                "confidence": entry.get("confidence"),
            })

    dated.sort(key=lambda x: x["date"])
    return {
        "tradition": tradition,
        "year": gregorian_year,
        "verified": corpus.verified,
        "verificationNote": corpus.verification_note,
        "counts": {"entries": len(corpus.entries),
                   "dated": len(dated), "undated": len(undated)},
        "festivals": dated,
        # Present, not filtered: a festival that cannot be dated is a fact about
        # the record, not an absence.
        "undated": undated,
    }
