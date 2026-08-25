# SPDX-License-Identifier: AGPL-3.0-only
"""
The Thelemic date.

Three parts, and the first two are the point: the date is written as the
positions of the luminaries, not as a number. ``☉ in 1° ♍ : ☾ in 22° ♑ :
Anno Vxii e.v.``

Written in glyphs rather than sign names, which is how the line is set in
practice — and the luminaries were already glyphs, so spelling out the signs
beside them was inconsistent anyway. The names remain in the structured
fields for anything that needs to read them.

**The year turns at the March equinox**, not at midnight on 1 January, because
the era is dated from the equinox of 1904 — so a date in February belongs to
the year that began the previous March.

**Years are counted in twenty-two year cycles**, one per trump of the Tarot.
The convention is an uppercase Roman numeral for completed cycles followed by
a lowercase one for the year within the current cycle, so 1904 itself is year
0 and 2026 is Vxii — five complete cycles and twelve years. Year zero in a
cycle is written with the cycle numeral alone.

Nothing here is interpretation. It is a calendar conversion, and where the
inputs are the same the output is the same.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from shruti_astro.core import hellenistic as he
from shruti_astro.core.ephemeris import longitudes

# 20 March 1904: the equinox from which the era is reckoned.
EPOCH_YEAR = 1904
CYCLE_YEARS = 22

_ROMAN = (
    (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
    (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
)


def roman(n: int, upper: bool = False) -> str:
    """Roman numeral. Zero has no numeral and returns an empty string."""
    if n <= 0:
        return ""
    out = []
    for value, glyph in _ROMAN:
        while n >= value:
            out.append(glyph)
            n -= value
    s = "".join(out)
    return s.upper() if upper else s


def march_equinox(year: int) -> datetime:
    """
    The instant the Sun reaches 0° TROPICAL Aries.

    Tropical, not sidereal: the era is dated from the equinox itself, which is
    the definition of tropical zero. Reading it sidereally would drift the new
    year by the ayanāṁśa — about 24 days at present — and put the turn in
    April.
    """
    lo = datetime(year, 3, 17, tzinfo=timezone.utc)
    hi = datetime(year, 3, 24, tzinfo=timezone.utc)

    def past(m: datetime) -> bool:
        # Longitude wraps 360 → 0 at the equinox, so test the half-circle.
        return longitudes(m).sun_tropical < 180.0

    for _ in range(60):
        mid = lo + (hi - lo) / 2
        if past(mid):
            hi = mid
        else:
            lo = mid
    return lo + (hi - lo) / 2


@dataclass
class ThelemicDate:
    sun_sign: str
    sun_degree: float
    moon_sign: str
    moon_degree: float
    year: int          # years since the 1904 equinox
    cycle: int         # completed 22-year cycles
    year_in_cycle: int
    anno: str          # "Vxii"
    formatted: str     # the whole line


def thelemic_date(moment: datetime) -> ThelemicDate:
    """The Thelemic date for an instant."""
    L = longitudes(moment)

    # Which era-year are we in? The year turns at the March equinox, so
    # compare against this Gregorian year's equinox and step back if the
    # moment falls before it.
    era_year = moment.year - EPOCH_YEAR
    if moment < march_equinox(moment.year):
        era_year -= 1

    cycle, year_in_cycle = divmod(era_year, CYCLE_YEARS)
    # Zero has no Roman numeral, so the first year of a cycle is the cycle
    # numeral alone and the very first year of the era is written "0" rather
    # than as an empty string with a stray space in the middle of the line.
    anno = roman(cycle, upper=True) + roman(year_in_cycle) or "0"

    sun_i = he.sign_of(L.sun_tropical)
    moon_i = he.sign_of(L.moon_tropical)
    sun_sign = he.SIGNS[sun_i]
    moon_sign = he.SIGNS[moon_i]
    sun_deg = he.degree_in_sign(L.sun_tropical)
    moon_deg = he.degree_in_sign(L.moon_tropical)

    formatted = (
        f"☉ in {sun_deg:.0f}° {he.SIGN_GLYPHS[sun_i]} "
        f": ☾ in {moon_deg:.0f}° {he.SIGN_GLYPHS[moon_i]} "
        f": Anno {anno} e.v."
    )
    return ThelemicDate(
        sun_sign=sun_sign, sun_degree=round(sun_deg, 4),
        moon_sign=moon_sign, moon_degree=round(moon_deg, 4),
        year=era_year, cycle=cycle, year_in_cycle=year_in_cycle,
        anno=anno, formatted=formatted,
    )
