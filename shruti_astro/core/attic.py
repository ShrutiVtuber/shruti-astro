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


@lru_cache(maxsize=32)
def _attic_year(start_year: int) -> tuple[tuple[str, str, date_cls, bool], ...]:
    """(name, greek, first civil day, is_intercalary) for each month of the year."""
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
    for i, (n, g, nm) in enumerate(zip(names, greeks, moons)):
        # The noumenia is the day after conjunction — first crescent.
        noumenia = (_from_julday(nm) + timedelta(days=1)).date()
        out.append((n, g, noumenia, n == INTERCALARY_NAME))
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
    if remaining == 1:
        # Belongs to both months at once.
        return "ἕνη καὶ νέα", "henē kai nea", DECADS[2][0]
    return (_ORDINALS[remaining - 1] + " φθίνοντος",
            f"{remaining} phthinontos", DECADS[2][0])


def attic_day(d: date_cls) -> AtticDay:
    """Resolve one civil date onto the Attic reckoning."""
    for start in (d.year, d.year - 1):
        try:
            months = _attic_year(start)
        except BeforeTheCycle:
            raise
        if months[0][2] <= d:
            try:
                nxt = _attic_year(start + 1)
            except BeforeTheCycle:
                nxt = None
            if nxt is None or d < nxt[0][2]:
                break
    else:
        raise ValueError("could not place the date in an Attic year")

    bounds = [m[2] for m in months] + ([nxt[0][2]] if nxt else [None])
    for i, (name, greek, first, intercal) in enumerate(months):
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
            )
    raise ValueError("could not place the date in an Attic month")
