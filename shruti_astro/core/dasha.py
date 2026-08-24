# SPDX-License-Identifier: AGPL-3.0-only
"""
Vimśottarī daśā — the 120-year planetary period system.

The most consulted predictive technique in jyotiṣa, and the one whose absence
makes a Vedic chart tool unusable rather than merely incomplete.

The whole ladder hangs off one number: how far the Moon had travelled through
its nakṣatra at birth. That fraction sets the balance of the first mahādaśā, and
every sub-period below inherits from it — so an error in the Moon's longitude
does not produce a slightly wrong daśā, it produces a wrong *sequence*.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from shruti_astro.core.divisions import division_fraction, division_index
from shruti_astro.core.vedic import NAKSHATRA_LORDS

# The nine lords in their fixed order, with their years. Sums to 120.
VIMSHOTTARI = [
    ("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7),
    ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17),
]
TOTAL_YEARS = 120
assert sum(y for _, y in VIMSHOTTARI) == TOTAL_YEARS

LORD_ORDER = [name for name, _ in VIMSHOTTARI]
LORD_YEARS = dict(VIMSHOTTARI)

# The length of a daśā year is genuinely contested, and the choice moves a
# mahādaśā boundary by months over a lifetime. Per the governing ruling: where
# the tradition holds two opinions, the practitioner chooses.
YEAR_LENGTHS = {
    "julian": 365.25,          # most common in software
    "sidereal": 365.256363,    # the true sidereal year
    "savana": 360.0,           # the 360-day civil year some schools use
}


@dataclass
class Period:
    lord: str
    level: int                 # 1 mahādaśā, 2 antardaśā, 3 pratyantardaśā
    start: datetime
    end: datetime
    children: list["Period"]

    def to_dict(self) -> dict:
        return {
            "lord": self.lord,
            "level": self.level,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "children": [c.to_dict() for c in self.children],
        }


def _order_from(lord: str) -> list[str]:
    i = LORD_ORDER.index(lord)
    return LORD_ORDER[i:] + LORD_ORDER[:i]


def balance_at_birth(moon_sidereal_longitude: float) -> tuple[str, float]:
    """
    (starting lord, fraction of that lord's period still remaining).

    The Moon's position *within* its nakṣatra is the entire input. A Moon at the
    very start of Aśvinī begins a full 7-year Ketu daśā; one at the very end
    begins with almost none of it left and moves to Venus within days.
    """
    lon = moon_sidereal_longitude % 360.0
    idx = division_index(lon, 27)
    return NAKSHATRA_LORDS[idx], 1.0 - division_fraction(lon, 27)


def _subdivide(
    lord: str, start: datetime, span_days: float, level: int, max_level: int
) -> list[Period]:
    """
    Sub-periods run in the same fixed order, beginning with the parent's own
    lord, each taking its own share of the parent's span. The proportions are
    identical at every level — that self-similarity is the system.
    """
    if level > max_level:
        return []

    out: list[Period] = []
    cursor = start
    for sub in _order_from(lord):
        sub_days = span_days * (LORD_YEARS[sub] / TOTAL_YEARS)
        end = cursor + timedelta(days=sub_days)
        out.append(
            Period(
                lord=sub, level=level, start=cursor, end=end,
                children=_subdivide(sub, cursor, sub_days, level + 1, max_level),
            )
        )
        cursor = end
    return out


def vimshottari(
    birth: datetime,
    moon_sidereal_longitude: float,
    cycles: int = 1,
    max_level: int = 2,
    year_length: str = "julian",
) -> list[Period]:
    """
    The mahādaśā sequence from birth, with sub-periods to `max_level`.

    The first mahādaśā is truncated to its balance at birth — it began before
    the native did. Its antardaśās are computed over that *shortened* span, not
    the full one, which is the subtlety implementations most often miss: a
    truncated mahādaśā does not simply start partway through its sub-periods,
    it compresses all of them proportionally.
    """
    if year_length not in YEAR_LENGTHS:
        raise ValueError(f"unknown year length; choose from {sorted(YEAR_LENGTHS)}")
    days_per_year = YEAR_LENGTHS[year_length]

    start_lord, remaining = balance_at_birth(moon_sidereal_longitude)

    periods: list[Period] = []
    cursor = birth
    sequence = _order_from(start_lord) * max(1, cycles)

    for i, lord in enumerate(sequence):
        years = LORD_YEARS[lord] * (remaining if i == 0 else 1.0)
        span_days = years * days_per_year
        end = cursor + timedelta(days=span_days)
        periods.append(
            Period(
                lord=lord, level=1, start=cursor, end=end,
                children=_subdivide(lord, cursor, span_days, 2, max_level),
            )
        )
        cursor = end

    return periods


def active_chain(periods: list[Period], moment: datetime) -> list[dict]:
    """The nested periods in force at one instant — mahā, antara, pratyantara."""
    chain: list[dict] = []
    level = periods
    while level:
        found = next((p for p in level if p.start <= moment < p.end), None)
        if found is None:
            break
        chain.append({
            "lord": found.lord, "level": found.level,
            "start": found.start.isoformat(), "end": found.end.isoformat(),
        })
        level = found.children
    return chain
