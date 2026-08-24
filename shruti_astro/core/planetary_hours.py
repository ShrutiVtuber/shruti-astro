# SPDX-License-Identifier: AGPL-3.0-only
"""
Planetary hours.

The day from sunrise to sunset is divided into twelve *unequal* hours, and the
night from sunset to next sunrise into twelve more. Rulership runs in Chaldean
order, and the first hour of the day belongs to the planet ruling that weekday.

The correctness lives entirely in the edge cases, which is why they are handled
explicitly here rather than left to fail quietly:

  - At high latitude the Sun may not rise or set at all. There are no planetary
    hours on such a day, and saying so is the honest answer. Returning twelve
    equal hours of an imaginary day is not.
  - DST transitions make "the length of an hour" ambiguous in local time, so all
    arithmetic is done on absolute instants and only formatted at the edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Chaldean order — slowest apparent motion to fastest.
CHALDEAN = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

# Weekday rulers. Python's weekday(): Monday=0 .. Sunday=6.
DAY_RULER = {0: "Moon", 1: "Mars", 2: "Mercury", 3: "Jupiter", 4: "Venus", 5: "Saturn", 6: "Sun"}


class NoPlanetaryHours(Exception):
    """The Sun neither rose nor set — the day has no hours to divide."""


@dataclass
class PlanetaryHour:
    index: int              # 1..24, counted from sunrise
    ruler: str
    starts_at: datetime     # UTC
    ends_at: datetime       # UTC
    is_night: bool


def build_hours(
    sunrise: datetime | None,
    sunset: datetime | None,
    next_sunrise: datetime | None,
    weekday: int,
) -> list[PlanetaryHour]:
    """All twenty-four hours for one sunrise-to-sunrise cycle."""
    if sunrise is None or sunset is None or next_sunrise is None:
        raise NoPlanetaryHours(
            "the Sun did not both rise and set at this location on this date"
        )

    day_len = (sunset - sunrise) / 12
    night_len = (next_sunrise - sunset) / 12

    start_ruler = DAY_RULER[weekday]
    offset = CHALDEAN.index(start_ruler)

    hours: list[PlanetaryHour] = []
    for i in range(24):
        is_night = i >= 12
        if is_night:
            begin = sunset + night_len * (i - 12)
            end = begin + night_len
        else:
            begin = sunrise + day_len * i
            end = begin + day_len
        hours.append(
            PlanetaryHour(
                index=i + 1,
                ruler=CHALDEAN[(offset + i) % 7],
                starts_at=begin.astimezone(timezone.utc),
                ends_at=end.astimezone(timezone.utc),
                is_night=is_night,
            )
        )
    return hours


def current_hour(hours: list[PlanetaryHour], now: datetime | None = None) -> PlanetaryHour | None:
    now = now or datetime.now(timezone.utc)
    for h in hours:
        if h.starts_at <= now < h.ends_at:
            return h
    return None
