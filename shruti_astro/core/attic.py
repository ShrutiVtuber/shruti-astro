# SPDX-License-Identifier: AGPL-3.0-only
"""
The Attic calendar of Athens.

Ported from Theourgia (AGPL-3.0-only, same copyright holder) and extended. Its
ephemeris calls already used the Moshier arm, so nothing about the Swiss
Ephemeris licence changes in the move.

Three things make this calendar unlike the others here:

  - **The month opens at the noumenia**, the first sighting of the new crescent,
    and runs *full* (30 days) or *hollow* (29). Which it is emerges from where
    the next new moon falls, not from a table.

    A sighting happens *somewhere*, and this file long claimed the sentence
    above while computing the day after the conjunction in UTC — which is
    nobody's calendar. Both readings are now available and neither is imposed.
    `reckoning="conjunction"` opens the month the day after the conjunction in
    local time: deterministic, defined at every latitude, and what most modern
    Hellenic practice uses. `reckoning="visibility"` opens it the evening the
    crescent can actually be seen from the observer's own position, which is
    what Athens did. They part company in six months of twelve, and Athens and
    Sydney part company in seven.

    Above roughly 55° the crescent cannot be caught reliably — Swiss Ephemeris
    will report a first visibility three weeks after the conjunction — so
    visibility reckoning there is checked and, when it yields months that are
    not 29 or 30 days, given back as conjunction with a note saying why.
  - **The last third of the month is counted backwards.** Days 21 onward are
    named by how many remain — δεκάτη φθίνοντος is the tenth *from the end* —
    and the final day is ἕνη καὶ νέα, "old and new", belonging to both months.
  - **Twelve lunar months fall about eleven days short of the solar year**, so a
    thirteenth is inserted seven times in nineteen. Athens put it after
    Poseideon and called it Poseideon II.

**Before 432 BCE the Metonic cycle was not in use**, and Athens' actual
intercalations were decided by magistrates, argued about at the time, and are
not recoverable. The calendar refuses those years rather than inventing them,
and it never fabricates an archon year.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import swisseph as swe

from shruti_astro.core.ephemeris import _ensure_init, _flags, _from_julday, _julday

MONTH_NAMES = (
    "Hekatombaion", "Metageitnion", "Boedromion", "Pyanepsion",
    "Maimakterion", "Poseideon", "Gamelion", "Anthesterion",
    "Elaphebolion", "Mounichion", "Thargelion", "Skirophorion",
)

MONTH_GREEK = (
    "Ἑκατομβαιών", "Μεταγειτνιών", "Βοηδρομιών", "Πυανεψιών",
    "Μαιμακτηριών", "Ποσειδεών", "Γαμηλιών", "Ἀνθεστηριών",
    "Ἐλαφηβολιών", "Μουνιχιών", "Θαργηλιών", "Σκιροφοριών",
)

INTERCALARY_AFTER = 6
INTERCALARY_NAME = "Poseideon II"
INTERCALARY_GREEK = "Ποσειδεὼν βʹ"

# The Metonic cycle was published at Athens in 432 BCE. Earlier intercalations
# were magistrates' decisions and are not recoverable.
METONIC_EPOCH_YEAR = -431          # 432 BCE in astronomical numbering

_ORDINALS = (
    "πρώτη", "δευτέρα", "τρίτη", "τετάρτη", "πέμπτη",
    "ἕκτη", "ἑβδόμη", "ὀγδόη", "ἐνάτη", "δεκάτη",
)

DECADS = (
    ("ἱσταμένου", "histamenou", "of the month beginning"),
    ("μεσοῦντος", "mesountos", "of the middle"),
    ("φθίνοντος", "phthinontos", "of the waning — counted backwards"),
)


# Athens. The Attic calendar is the civic calendar of one city, so when no
# observer is given, that city is the honest default. Until now this code had
# no observer at all and silently answered in UTC, which is nobody's calendar.
ATHENS = (37.9838, 23.7275)

# How the month is opened.
#   "conjunction" — the day after the conjunction. Deterministic, defined
#       everywhere, and what most modern Hellenic practice actually uses.
#   "visibility"  — the evening the crescent can first be seen from where you
#       are. What Athens did, and what the docstring above promises.
# They disagree in half the months of a year, so this cannot be settled here.
RECKONINGS = ("conjunction", "visibility")

# A month runs 29 or 30 days. When the visibility model reports a longer lag
# than this it has lost the crescent, not found a late one: at 61°N in August
# it returns a first sighting 21 days after the conjunction, which would build
# a forty-day Metageitnion. Past this we fall back and say we did.
MAX_CRESCENT_LAG_DAYS = 2.5


def _local_date(jd: float, lon: float) -> date_cls:
    """Civil date at `lon` by mean solar time — not the political timezone."""
    return _from_julday(jd + lon / 360.0).date()


def _first_crescent(nm_jd: float, lat: float, lon: float) -> float | None:
    """JD the new crescent first becomes visible here, or None if never."""
    _ensure_init()
    try:
        r = swe.heliacal_ut(
            nm_jd - 1.0,
            [lon, lat, 50.0],
            [1013.25, 15.0, 50.0, 0.25],
            [25.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "moon",
            swe.EVENING_FIRST,
            swe.HELFLAG_HIGH_PRECISION | swe.FLG_MOSEPH,
        )
    except Exception:
        return None
    return float(r[0]) if r and r[0] else None


def _noumenia(nm_jd: float, lat: float, lon: float,
              reckoning: str) -> tuple[date_cls, str | None]:
    """Opening day of the month whose conjunction is `nm_jd`, and any caveat."""
    fallback = _local_date(nm_jd, lon) + timedelta(days=1)
    if reckoning == "conjunction":
        return fallback, None

    seen = _first_crescent(nm_jd, lat, lon)
    if seen is None:
        return fallback, "the crescent was never caught here; opened by conjunction instead"
    if seen - nm_jd > MAX_CRESCENT_LAG_DAYS:
        return fallback, (
            f"first visible only {seen - nm_jd:.1f} days after the conjunction at this "
            "latitude, which is too late to open a month; opened by conjunction instead"
        )
    return _local_date(seen, lon), None


class BeforeTheCycle(Exception):
    """Earlier than 432 BCE: the intercalations are not recoverable."""


@dataclass
class AtticDay:
    gregorian: date_cls
    month: str
    month_greek: str
    month_index: int
    is_intercalary: bool
    day: int
    month_length: int
    is_full: bool
    day_name_greek: str
    day_name_translit: str
    decad: str
    days_remaining: int
    moon_age_days: float
    next_noumenia: date_cls
    year_is_intercalary: bool
    months_in_year: int
    latitude: float
    longitude: float
    location_defaulted: bool
    reckoning: str
    noumenia_note: str | None


def _new_moon_after(jd: float) -> float:
    """Bisect the next conjunction after `jd`."""
    _ensure_init()

    def d(j: float) -> float:
        sun = swe.calc_ut(j, swe.SUN, _flags())[0][0]
        moon = swe.calc_ut(j, swe.MOON, _flags())[0][0]
        return ((moon - sun + 180.0) % 360.0) - 180.0

    step = 0.5
    j = jd + 0.5
    prev = d(j)
    for _ in range(90):
        j += step
        cur = d(j)
        if prev < 0 <= cur:
            lo, hi = j - step, j
            for _ in range(60):
                mid = (lo + hi) / 2
                if d(lo) < 0 <= d(mid):
                    hi = mid
                else:
                    lo = mid
            return (lo + hi) / 2
        prev = cur
    raise ValueError("no conjunction found")


def _summer_solstice(year: int) -> float:
    """JD of the solstice — the Attic year begins with the first noumenia after it."""
    _ensure_init()
    lo = _julday(datetime(year, 6, 1, tzinfo=timezone.utc))
    hi = _julday(datetime(year, 7, 15, tzinfo=timezone.utc))
    for _ in range(80):
        mid = (lo + hi) / 2
        if swe.calc_ut(mid, swe.SUN, _flags())[0][0] % 360.0 < 90.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _lengths_are_lunar(months, moons, lat: float, lon: float) -> bool:
    """Every month must run 29 or 30 days, the closing one included."""
    after = _new_moon_after(moons[-1])
    edges = [m[2] for m in months] + [_noumenia(after, lat, lon, "conjunction")[0]]
    return all((edges[i + 1] - edges[i]).days in (29, 30) for i in range(len(months)))


@lru_cache(maxsize=256)
def _attic_year(
    start_year: int, lat: float = ATHENS[0], lon: float = ATHENS[1],
    reckoning: str = "conjunction",
) -> tuple[tuple[str, str, date_cls, bool, str | None], ...]:
    """(name, greek, opening day, is_intercalary, note) for each month.

    The *count* of months, and so the intercalation, comes from the conjunctions
    between one solstice and the next. Only where each month opens depends on
    the observer — so a year is twelve or thirteen months under either reckoning.
    """
    if reckoning not in RECKONINGS:
        raise ValueError(f"reckoning must be one of {RECKONINGS}, not {reckoning!r}")
    if start_year < METONIC_EPOCH_YEAR:
        raise BeforeTheCycle(
            f"{abs(start_year) + 1} BCE is before the Metonic cycle was adopted at "
            "Athens in 432 BCE; the actual intercalations are not recoverable"
        )

    first = _new_moon_after(_summer_solstice(start_year))
    next_first = _new_moon_after(_summer_solstice(start_year + 1))

    moons = [first]
    while moons[-1] < next_first - 1.0:
        moons.append(_new_moon_after(moons[-1]))
    if moons[-1] >= next_first - 1.0:
        moons = moons[:-1]

    count = len(moons)
    if count == 13:
        names = (list(MONTH_NAMES[:INTERCALARY_AFTER]) + [INTERCALARY_NAME]
                 + list(MONTH_NAMES[INTERCALARY_AFTER:]))
        greeks = (list(MONTH_GREEK[:INTERCALARY_AFTER]) + [INTERCALARY_GREEK]
                  + list(MONTH_GREEK[INTERCALARY_AFTER:]))
    else:
        names, greeks = list(MONTH_NAMES), list(MONTH_GREEK)

    out = []
    for n, g, nm in zip(names, greeks, moons):
        first, note = _noumenia(nm, lat, lon, reckoning)
        out.append((n, g, first, n == INTERCALARY_NAME, note))

    if reckoning == "visibility" and not _lengths_are_lunar(out, moons, lat, lon):
        # A month that fell back to conjunction now sits beside one that did
        # not, and the gap between them is no longer 29 or 30 days. Athens
        # would simply proclaim the month when cloud hid the crescent, so a
        # mixed year is fine as long as it still runs in lunar months — but 28
        # and 31 day months are not a calendar. Hand back the whole year by
        # conjunction rather than an incoherent one.
        note = (
            "the crescent cannot be caught reliably at this latitude, and "
            "visibility reckoning produced months that were not 29 or 30 days; "
            "the whole year is given by conjunction instead"
        )
        out = [(n, g, _noumenia(nm, lat, lon, "conjunction")[0],
                n == INTERCALARY_NAME, note)
               for n, g, nm in zip(names, greeks, moons)]
    return tuple(out)


def _day_name(day: int, month_length: int) -> tuple[str, str, str]:
    """(greek, transliteration, decad) — the backwards third included."""
    if day <= 10:
        return _ORDINALS[day - 1] + " ἱσταμένου", f"{day} histamenou", DECADS[0][0]
    if day <= 20:
        if day == 20:
            return "εἰκάς", "eikas", DECADS[1][0]
        return f"{day} ἐπὶ δέκα", f"{day} epi deka", DECADS[1][0]

    remaining = month_length - day + 1
    if not 1 <= remaining <= 10:
        raise ValueError(
            f"day {day} of a {month_length}-day month has no Attic name; "
            "the month is not lunar"
        )
    if remaining == 1:
        # Belongs to both months at once.
        return "ἕνη καὶ νέα", "henē kai nea", DECADS[2][0]
    return (_ORDINALS[remaining - 1] + " φθίνοντος",
            f"{remaining} phthinontos", DECADS[2][0])


def attic_day(
    d: date_cls, lat: float | None = None, lon: float | None = None,
    reckoning: str = "conjunction",
) -> AtticDay:
    """Resolve one civil date onto the Attic reckoning, as seen from somewhere.

    Give no observer and you get Athens, flagged as defaulted — the crescent
    opens the month at a place, and half the months of a year open on a
    different day in Sydney than they do in Attica.
    """
    defaulted = lat is None or lon is None
    if defaulted:
        lat, lon = ATHENS

    nxt = None
    for start in (d.year, d.year - 1):
        months = _attic_year(start, lat, lon, reckoning)
        if months[0][2] <= d:
            try:
                nxt = _attic_year(start + 1, lat, lon, reckoning)
            except BeforeTheCycle:
                nxt = None
            if nxt is None or d < nxt[0][2]:
                break
    else:
        raise ValueError("could not place the date in an Attic year")

    bounds = [m[2] for m in months] + ([nxt[0][2]] if nxt else [None])
    for i, (name, greek, first, intercal, note) in enumerate(months):
        nxt_first = bounds[i + 1]
        if nxt_first is None or (first <= d < nxt_first):
            length = (nxt_first - first).days if nxt_first else 30
            day = (d - first).days + 1
            g, t, decad = _day_name(day, length)
            jd = _julday(datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc))
            sun = swe.calc_ut(jd, swe.SUN, _flags())[0][0]
            moon = swe.calc_ut(jd, swe.MOON, _flags())[0][0]
            return AtticDay(
                gregorian=d, month=name, month_greek=greek, month_index=i + 1,
                is_intercalary=intercal, day=day, month_length=length,
                is_full=length == 30, day_name_greek=g, day_name_translit=t,
                decad=decad, days_remaining=length - day + 1,
                moon_age_days=round(((moon - sun) % 360.0) / 360.0 * 29.530588, 3),
                next_noumenia=nxt_first if nxt_first else first,
                year_is_intercalary=len(months) == 13, months_in_year=len(months),
                latitude=lat, longitude=lon, location_defaulted=defaulted,
                reckoning=reckoning, noumenia_note=note,
            )
    raise ValueError("could not place the date in an Attic month")


def attic_year(
    start_year: int, lat: float | None = None, lon: float | None = None,
    reckoning: str = "conjunction",
) -> dict:
    """
    The Attic year as a table of months, each with its Gregorian span.

    The counterpart of `hindu_year`, and it exists for the same reason: a
    calendar tool that can only say what today is cannot show anyone when
    anything happens. The festivals are attached by the caller, from the
    corpus — this function knows about months, not observances.

    **The year begins at the first new moon after the summer solstice**, so it
    straddles two Gregorian years and the table says so rather than pretending
    to run January to December. `start_year` is the Gregorian year that summer
    falls in.

    A thirteenth month is not an anomaly to be smoothed: an intercalary year
    genuinely has one, it is named Poseideon II, and it is flagged so a reader
    can see why the year is longer rather than assuming a bug.
    """
    defaulted = lat is None or lon is None
    if defaulted:
        lat, lon = ATHENS

    months = _attic_year(start_year, lat, lon, reckoning)
    try:
        following = _attic_year(start_year + 1, lat, lon, reckoning)
        year_end = following[0][2]
    except BeforeTheCycle:
        following, year_end = None, None

    bounds = [m[2] for m in months] + [year_end]
    out = []
    for i, (name, greek, first, intercalary, note) in enumerate(months):
        nxt = bounds[i + 1]
        # The last month of a year with no following year computed: 30 days is
        # the honest guess and it is only ever the final row.
        length = (nxt - first).days if nxt else 30
        last = first + timedelta(days=length - 1)
        out.append({
            "name": name,
            "greek": greek,
            "index": i + 1,
            "intercalary": intercalary,
            "start": first.isoformat(),
            "end": last.isoformat(),
            "days": length,
            "full": length == 30,
            "note": note,
        })

    return {
        "startYear": start_year,
        "reckoning": reckoning,
        "observer": {
            "lat": round(lat, 4), "lon": round(lon, 4), "defaulted": defaulted,
        },
        "monthCount": len(out),
        "intercalary": any(m["intercalary"] for m in out),
        "spans": f"{out[0]['start']} to {out[-1]['end']}",
        "months": out,
    }
