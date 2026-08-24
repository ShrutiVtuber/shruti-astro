# SPDX-License-Identifier: AGPL-3.0-only
"""
Resolving festival anchors to actual days.

A festival in a portable pack is stored as an **anchor**, not a date — "Kārtika
Kṛṣṇa 15" rather than "12 November 2026" — because the date is a function of the
year and the anchor is not. This module turns one into the other.

The rule that decides which civil day owns an observance is not obvious and is
where most implementations go wrong: **a tithi belongs to the sunrise it is
current at.** Tithis are not 24 hours long, so one can begin and end between two
sunrises and own no day at all (*kṣaya*), or span two sunrises and be counted
twice (*vṛddhi*). Both are reported rather than smoothed away.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone

from shruti_astro.core.hindu_calendar import MONTHS, hindu_date
from shruti_astro.core.panchanga import tithi as tithi_of
from shruti_astro.core.ephemeris import SunNeverRose, longitudes, sun_events

# Ujjain — the classical prime meridian of Indian astronomy, and the default
# when a pack does not name a place. Stated rather than assumed.
UJJAIN = (23.1765, 75.7885)

# **Which moment of the day owns an observance is not one rule.**
#
# Most festivals go to the tithi current at sunrise. But Dīpāvalī is kept on the
# amāvāsyā prevailing at *pradoṣa*, the evening twilight; Mahā Śivarātri and
# Janmāṣṭamī on the tithi at *niśītha*, true midnight; Vijayadaśamī and śrāddha
# rites at *aparāhṇa*, the afternoon. Applying the sunrise rule to all of them
# puts Dīpāvalī and Śivarātri each a day late, which is exactly what a wrong
# almanac does.
#
# Fractions are of the daylight span (sunrise → sunset) unless noted.
DAY_RULES = {
    "sunrise": None,                    # the tithi at sunrise — the default
    "madhyahna": 0.5,                   # midday
    "aparahna": 0.75,                   # afternoon, the fourth of five parts
    "pradosha": 1.0,                    # sunset, running into the evening
    "nishitha": "midnight",             # true midnight, between the sunrises
}


# A recurring anchor names no month: it happens every lunation. Ekādaśī twice a
# month, Pradoṣa twice, Saṅkaṣṭī Caturthī once. These matter more for daily
# practice than the annual festivals do, and there are more of them in a year
# than of everything else combined.
RECURRING = "*"

# A few observances exist ONLY in an intercalary month. Padminī and Paramā
# Ekādaśī are the pair: an adhika māsa has its own two Ekādaśīs, and they occur
# in no ordinary year at all. This is the exact opposite of the rule that
# festivals wait for the nija month — these belong to the repeat itself.
ADHIKA_ONLY = "adhika"


@dataclass
class Resolved:
    key: str
    name: str
    date: date_cls | None
    anchor: dict
    note: str = ""
    skipped: bool = False
    skipped_reason: str = ""
    doubled: bool = False


def _reckoning_moment(day: date_cls, lat: float, lon: float, rule: str) -> datetime | None:
    """The instant of `day` at which the observance's tithi is judged."""
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)
    try:
        sunrise, sunset, next_sunrise = sun_events(noon, lat, lon, "hindu")
    except SunNeverRose:
        return None

    spec = DAY_RULES.get(rule)
    if spec is None:
        return sunrise
    if spec == "midnight":
        return sunrise + (next_sunrise - sunrise) / 2
    return sunrise + (sunset - sunrise) * spec


def _tithi_at(day: date_cls, lat: float, lon: float,
              rule: str = "sunrise") -> tuple[int, str] | None:
    """(tithi index 1..30, pakṣa) at the moment this observance is judged by."""
    moment = _reckoning_moment(day, lat, lon, rule)
    if moment is None:
        return None
    L = longitudes(moment)
    t = tithi_of(L.sun_tropical, L.moon_tropical)
    return t.index, ("Śukla" if t.index <= 15 else "Kṛṣṇa")


def resolve_lunar(
    anchor: dict, gregorian_year: int, lat: float = UJJAIN[0], lon: float = UJJAIN[1]
) -> Resolved:
    """
    A Hindu lunar anchor → the civil day that owns it.

    `anchor` carries month, paksha, tithi, and optionally reckoning. Scans the
    year for the day whose *sunrise* falls in the named month, pakṣa and tithi.
    """
    month = anchor["month"]
    want_tithi = int(anchor["tithi"])
    reckoning = anchor.get("reckoning", "amanta")
    rule = anchor.get("dayRule", "sunrise")

    if month not in MONTHS:
        raise ValueError(f"unknown lunar month: {month}")
    if rule not in DAY_RULES:
        raise ValueError(f"unknown day rule: {rule}; choose from {sorted(DAY_RULES)}")

    # Normalise the pakṣa to ASCII before testing it. Comparing an incoming
    # "shukla" against the transliterated "Śukla" silently sends every bright
    # fortnight anchor to the wrong tithi — it did, until this was fixed.
    paksha = anchor["paksha"].strip().lower()
    if paksha.startswith(("s", "ś", "\u015b")):
        bright = True
    elif paksha.startswith("k"):
        bright = False
    else:
        raise ValueError(f"paksha must be shukla or krishna, got {anchor['paksha']!r}")

    # Absolute tithi index: Śukla 1..15, Kṛṣṇa 16..30.
    target = want_tithi if bright else want_tithi + 15

    hits: list[date_cls] = []
    d = date_cls(gregorian_year, 1, 1)
    end = date_cls(gregorian_year, 12, 31)
    while d <= end:
        got = _tithi_at(d, lat, lon, rule)
        if got is not None and got[0] == target:
            # The month must be judged at the SAME moment as the tithi. Reading
            # the tithi at pradoṣa and the month at noon can straddle a new moon
            # and put a festival a whole lunation out — it did.
            moment = _reckoning_moment(d, lat, lon, rule)
            hd = hindu_date(moment, reckoning)
            # Observances never fall in an intercalary month — they wait for
            # the nija month that follows.
            if hd.month == month and not hd.is_adhika:
                hits.append(d)
        d += timedelta(days=1)

    if not hits:
        return Resolved(
            key=anchor.get("key", ""), name=anchor.get("name", ""), date=None,
            anchor=anchor, skipped=True,
            skipped_reason=(
                f"no day in {gregorian_year} carried {anchor['paksha']} {want_tithi} "
                f"of {month} at {rule} — the tithi began and ended between two "
                f"reckoning moments (kṣaya)"
            ),
        )

    return Resolved(
        key=anchor.get("key", ""), name=anchor.get("name", ""),
        date=hits[0], anchor=anchor,
        doubled=len(hits) > 1,
        note=(f"judged at {rule}"
              + ("; the tithi spanned two reckoning moments and is counted "
                 "twice (vṛddhi)" if len(hits) > 1 else "")),
    )


def resolve_crescent(anchor: dict, gregorian_year: int) -> Resolved:
    """
    An Attic anchor → the civil day.

    Months open at the noumenia, so this walks the Attic year rather than
    counting from a fixed point.
    """
    from shruti_astro.core.attic import attic_day

    month = anchor["month"]
    want_day = int(anchor["day"])

    d = date_cls(gregorian_year, 1, 1)
    end = date_cls(gregorian_year, 12, 31)
    while d <= end:
        a = attic_day(d)
        if a.month == month and a.day == want_day:
            return Resolved(key=anchor.get("key", ""), name=anchor.get("name", ""),
                            date=d, anchor=anchor)
        d += timedelta(days=1)

    return Resolved(
        key=anchor.get("key", ""), name=anchor.get("name", ""), date=None,
        anchor=anchor, skipped=True,
        skipped_reason=(
            f"{month} {want_day} did not occur in {gregorian_year} — either the "
            f"month was hollow and has no day {want_day}, or it fell outside the "
            f"Gregorian year"
        ),
    )


def resolve_recurring(
    anchor: dict, gregorian_year: int, lat: float = UJJAIN[0], lon: float = UJJAIN[1]
) -> list[Resolved]:
    """
    Every occurrence in the year of an observance that recurs each lunation.

    `month` is "*". Unlike an annual anchor this returns a **list** — Ekādaśī
    falls about twenty-four times a year, and collapsing that to one date would
    be a different and wrong answer rather than a partial one.

    Adhika months are included: a recurring observance is not a festival waiting
    for the nija month, it simply happens again.
    """
    paksha_raw = anchor["paksha"].strip().lower()
    if paksha_raw.startswith(("s", "ś", "\u015b")):
        bright = True
    elif paksha_raw.startswith("k"):
        bright = False
    else:
        raise ValueError(f"paksha must be shukla or krishna, got {anchor['paksha']!r}")

    want_tithi = int(anchor["tithi"])
    rule = anchor.get("dayRule", "sunrise")
    if rule not in DAY_RULES:
        raise ValueError(f"unknown day rule: {rule}; choose from {sorted(DAY_RULES)}")

    target = want_tithi if bright else want_tithi + 15

    adhika_only = anchor.get("month") == ADHIKA_ONLY

    out: list[Resolved] = []
    d = date_cls(gregorian_year, 1, 1)
    end = date_cls(gregorian_year, 12, 31)
    while d <= end:
        got = _tithi_at(d, lat, lon, rule)
        if got is not None and got[0] == target:
            moment = _reckoning_moment(d, lat, lon, rule)
            hd = hindu_date(moment, anchor.get("reckoning", "amanta"))
            if not adhika_only or hd.is_adhika:
                out.append(Resolved(
                    key=anchor.get("key", ""), name=anchor.get("name", ""),
                    date=d, anchor=anchor,
                    note=(f"{'Adhika ' if hd.is_adhika else ''}{hd.month} "
                          f"{hd.paksha}, judged at {rule}"),
                ))
        d += timedelta(days=1)

    # Two consecutive occurrences mean the tithi spanned two reckoning moments
    # — vṛddhi. Both are marked rather than one being dropped, because the
    # choice between them is a real doctrinal one: on a doubled Ekādaśī the
    # Smārta and Vaiṣṇava traditions fast on different days. Picking one here
    # would be making that ruling on the practitioner's behalf.
    for earlier, later in zip(out, out[1:]):
        if (later.date - earlier.date).days == 1:
            earlier.doubled = later.doubled = True
            for r in (earlier, later):
                r.note += ("; vṛddhi — the tithi spans two days and the "
                           "traditions differ on which is kept")
    return out


def resolve(anchor: dict, gregorian_year: int, **kw):
    """
    An annual anchor yields one Resolved; a recurring one yields a list.

    The return type genuinely differs because the questions differ — "when is
    Dīpāvalī this year" has one answer and "when is Ekādaśī" has about
    twenty-four. Returning a one-element list for the first would make every
    caller unwrap it; returning only the first of the second would be wrong.
    """
    kind = anchor.get("kind")
    if kind == "lunar":
        if anchor.get("month") in (RECURRING, ADHIKA_ONLY):
            # Both walk the year rather than seeking one month: "*" takes every
            # lunation, "adhika" takes only the intercalary ones — which in most
            # years is none, and that empty list is the correct answer.
            return resolve_recurring(anchor, gregorian_year, **kw)
        return resolve_lunar(anchor, gregorian_year, **kw)
    if kind == "crescent":
        return resolve_crescent(anchor, gregorian_year)
    if kind == "fixed":
        return Resolved(
            key=anchor.get("key", ""), name=anchor.get("name", ""),
            date=date_cls(gregorian_year, int(anchor["month"]), int(anchor["day"])),
            anchor=anchor,
        )
    raise ValueError(f"unsupported anchor kind: {kind!r}")
