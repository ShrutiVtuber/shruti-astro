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


DEFAULT_PLACE = {
    # name, (lat, lon), and why this place and not another.
    "hindu": ("Ujjain", (23.1765, 75.7885),
              "the classical prime meridian of Indian astronomy"),
    "attic": ("Athens", (37.9838, 23.7275), "the city whose calendar this is"),
}


def year(
    tradition: str,
    gregorian_year: int,
    lat: float | None = None,
    lon: float | None = None,
    school: str | None = None,
    **kw,
) -> dict:
    """
    Every occurrence in the year, for a place.

    **The place is not decoration.** A tithi is current at an instant, and which
    civil day owns it depends on when the Sun rises where you are. Measured for
    2026, five of seven major festivals fall on different days in Sydney than in
    Ujjain. Serving one location's answer to everyone is the single easiest way
    for a calendar to be quietly wrong for most of its users.

    Where no location is given, Ujjain is used — the classical prime meridian of
    Indian astronomy — and the response says so, so a consumer knows it is
    reading a default rather than an answer about them.

    `school` selects among variants where traditions genuinely disagree. Without
    it, an entry that has variants returns **all** of them rather than a
    default: picking one silently would make a doctrinal ruling on the
    practitioner's behalf.

    Undated entries are returned alongside the dated ones. A festival that
    cannot be dated is a fact about the record, and dropping it would leave a
    consumer believing the corpus is smaller and more certain than it is.
    """
    from shruti_astro.core.attic import ATHENS, RECKONINGS
    from shruti_astro.core.festivals import UJJAIN

    # The default belongs to the tradition, not to the registry. Serving
    # Ujjain's sunrise to someone asking for the calendar of Athens was simply
    # the wrong city.
    where, home, why = DEFAULT_PLACE.get(
        tradition,
        ("Ujjain", UJJAIN, "the classical prime meridian of Indian astronomy"))
    defaulted = lat is None or lon is None
    if defaulted:
        lat, lon = home
    kw.update(lat=lat, lon=lon)

    # For Athens the school is the reckoning: whether the month opens the day
    # after the conjunction, or on the evening the crescent can actually be
    # seen from where you are. They disagree in half the months of a year.
    reckoning = kw.pop("reckoning", None)
    if tradition == "attic":
        reckoning = reckoning or "conjunction"
        if reckoning not in RECKONINGS:
            raise ValueError(f"reckoning must be one of {RECKONINGS}, not {reckoning!r}")
        kw["reckoning"] = reckoning
    else:
        reckoning = None

    corpus = load(tradition)
    dated: list[dict] = []
    undated: list[dict] = []

    for entry in corpus.entries:
        base = _clean(entry.get("anchor"))

        # Variants are alternatives a practitioner chooses between, not
        # refinements of one answer. Each is resolved and labelled.
        variants = entry.get("variants") or []
        if variants and school:
            chosen = [v for v in variants if v.get("school") == school]
            candidates = [(school, _clean(v.get("anchor") or base)) for v in chosen] \
                or [(None, base)]
        elif variants:
            candidates = [(v.get("school"), _clean(v.get("anchor") or base))
                          for v in variants]
        else:
            candidates = [(None, base)]

        for label, anchor in candidates:
            _place(entry, anchor, label, gregorian_year, kw, dated, undated)

    dated.sort(key=lambda x: x["date"])
    return {
        "tradition": tradition,
        "year": gregorian_year,
        "location": {"lat": lat, "lon": lon, "defaulted": defaulted,
                     "note": (f"no location was given, so this is computed for "
                              f"{where}, {why} — festival dates differ by "
                              f"location and this may not be the answer where "
                              f"you are")
                             if defaulted else None},
        "school": school,
        "reckoning": reckoning,
        "verified": corpus.verified,
        "verificationNote": corpus.verification_note,
        "counts": {"entries": len(corpus.entries),
                   "dated": len(dated), "undated": len(undated)},
        "festivals": dated,
        "undated": undated,
    }


def _place(entry, anchor, label, gregorian_year, kw, dated, undated) -> None:
    """Resolve one anchor and file the result under dated or undated."""
    try:
        result = resolve(anchor, gregorian_year, **kw)
    except Exception as exc:                       # noqa: BLE001
        undated.append({
            "key": entry.get("key"), "name": entry.get("name"),
            "school": label, "reason": f"could not resolve: {exc}",
        })
        return

    occurrences: list[Resolved] = result if isinstance(result, list) else [result]
    placed = False
    for r in occurrences:
        if r.date is None:
            continue
        placed = True
        dated.append({
            "key": entry.get("key"), "name": entry.get("name"),
            "school": label,
            "date": r.date.isoformat(),
            "summary": entry.get("summary", ""),
            "confidence": entry.get("confidence"),
            "restriction": entry.get("restriction", "none"),
            "tags": entry.get("tags", []),
            "note": r.note,
            "doubled": r.doubled,
            "lasts": entry.get("lasts"),
            "sources": entry.get("sources", []),
        })
    if not placed:
        undated.append({
            "key": entry.get("key"), "name": entry.get("name"), "school": label,
            "reason": (occurrences[0].skipped_reason if occurrences
                       else "no occurrence this year"),
            "confidence": entry.get("confidence"),
        })
