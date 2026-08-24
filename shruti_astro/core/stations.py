# SPDX-License-Identifier: AGPL-3.0-only
"""
Solar and lunar stations — the four daily transitions of each body.

The structural skeleton of a daily rite. For the Sun these are sunrise, noon,
sunset and midnight; in Thelemic practice they carry the Liber Resh adorations,
in the Hellenic set Hekate Phosphoros at dawn, Apollo at noon, Hekate Enodia at
dusk and Persephone at night. This module computes the *times*; which name
belongs to which station is a preset the caller chooses or ignores.

**Noon and midnight are not clock times.** They are the Sun's upper and lower
meridian transits, which drift up to a quarter of an hour either side of 12:00
local across the year — that is the equation of time, and a rite kept by the
clock is kept at the wrong moment. The same applies to the Moon's culmination.

**The Moon does not rise every day.** It rises roughly fifty minutes later each
day, so it skips a civil day regularly at any latitude, and at high latitude can
go a week without one. A missing moonrise is a fact about the sky, not missing
data, and is reported as such rather than left blank.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone

import swisseph as swe

from shruti_astro.core.ephemeris import _ensure_init, _flags, _from_julday, _julday

# A month is the cap. A year of station times is a different product and a much
# heavier computation; the limit is stated rather than silently truncating.
MAX_DAYS = 31

SOLAR_STATIONS = ("sunrise", "noon", "sunset", "midnight")
LUNAR_STATIONS = ("moonrise", "culmination", "moonset", "nadir")

PRESETS: dict[str, dict[str, str]] = {
    "hellenic": {
        "sunrise": "Hekate Phosphoros",
        "noon": "Apollo",
        "sunset": "Hekate Enodia Kleidouchos",
        "midnight": "Persephone",
    },
    "thelemic": {
        "sunrise": "Ra",
        "noon": "Ahathoor",
        "sunset": "Tum",
        "midnight": "Khephra",
    },
    "none": {},
}

_SOLAR_FLAGS = {
    "sunrise": swe.CALC_RISE,
    "noon": swe.CALC_MTRANSIT,        # upper meridian transit
    "sunset": swe.CALC_SET,
    "midnight": swe.CALC_ITRANSIT,    # lower meridian transit
}
_LUNAR_FLAGS = {
    "moonrise": swe.CALC_RISE,
    "culmination": swe.CALC_MTRANSIT,
    "moonset": swe.CALC_SET,
    "nadir": swe.CALC_ITRANSIT,
}


@dataclass
class Station:
    name: str
    at: datetime | None
    absent_reason: str = ""
    dedication: str = ""

    @property
    def occurred(self) -> bool:
        return self.at is not None


# The eight conventional phase names, by the Moon's elongation from the Sun.
# Anyone tracking lunar stations wants the phase beside the times — the design
# gives it its own column, because a moonrise means something different at the
# full than at the dark.
PHASE_NAMES = (
    "new", "waxing crescent", "first quarter", "waxing gibbous",
    "full", "waning gibbous", "last quarter", "waning crescent",
)
SYNODIC_MONTH = 29.530588


def moon_phase(moment: datetime) -> tuple[str, float, float]:
    """(phase name, age in days since the conjunction, illuminated fraction)."""
    from shruti_astro.core.ephemeris import longitudes

    L = longitudes(moment)
    elongation = (L.moon_tropical - L.sun_tropical) % 360.0
    # Eight equal 45° arcs, centred so "full" spans the actual full moon
    # rather than beginning at it.
    index = int(((elongation + 22.5) % 360.0) // 45.0)
    age = elongation / 360.0 * SYNODIC_MONTH
    illumination = (1.0 - math.cos(math.radians(elongation))) / 2.0
    return PHASE_NAMES[index], age, illumination


@dataclass
class StationDay:
    date: date_cls
    body: str
    stations: list[Station]
    # Moon only: the phase column the lunar tracker is designed around.
    phase: str = ""
    moon_age_days: float | None = None
    illumination: float | None = None


def _transit(jd_start: float, body: int, rsmi: int, lat: float, lon: float) -> datetime | None:
    _ensure_init()
    res, tret = swe.rise_trans(jd_start, body, rsmi, (lon, lat, 0.0), 0.0, 0.0, _flags())
    if res < 0 or not tret or not tret[0]:
        return None
    return _from_julday(tret[0])


def _day_window(day: date_cls) -> tuple[float, datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return _julday(start), start, start + timedelta(days=1)


def stations_for_day(
    day: date_cls, lat: float, lon: float, body: str = "sun",
    preset: str = "none",
) -> StationDay:
    """
    The four stations of one body on one civil day, in UTC.

    A station that does not occur on this day carries `absent_reason` rather
    than being omitted — the caller needs to distinguish "did not happen" from
    "we did not look".
    """
    if body not in ("sun", "moon"):
        raise ValueError("body must be 'sun' or 'moon'")
    if preset not in PRESETS:
        raise ValueError(f"unknown preset; choose from {sorted(PRESETS)}")

    ident = swe.SUN if body == "sun" else swe.MOON
    flags = _SOLAR_FLAGS if body == "sun" else _LUNAR_FLAGS
    names = SOLAR_STATIONS if body == "sun" else LUNAR_STATIONS
    dedications = PRESETS[preset] if body == "sun" else {}

    jd0, start, end = _day_window(day)

    out: list[Station] = []
    for name in names:
        moment = _transit(jd0, ident, flags[name], lat, lon)
        # rise_trans finds the NEXT occurrence, which may fall past midnight.
        # A station belonging to tomorrow is not this day's station.
        if moment is not None and not (start <= moment < end):
            moment = None

        reason = ""
        if moment is None:
            if body == "moon" and name in ("moonrise", "moonset"):
                reason = (
                    f"no {name} on this date — the Moon rises about fifty minutes "
                    "later each day and skips a civil day regularly"
                )
            else:
                reason = (
                    f"no {name} on this date — the body does not cross that point "
                    "at this latitude on this day"
                )

        out.append(Station(name=name, at=moment, absent_reason=reason,
                           dedication=dedications.get(name, "")))

    phase = ""
    age: float | None = None
    lit: float | None = None
    if body == "moon":
        # Judged at local noon, so the column describes the day as a whole
        # rather than whichever instant happened to be first in the list.
        noon = _from_julday(jd0 + 0.5 - lon / 360.0)
        phase, age, lit = moon_phase(noon)

    return StationDay(date=day, body=body, stations=out,
                      phase=phase, moon_age_days=age, illumination=lit)


def stations_for_range(
    start: date_cls, days: int, lat: float, lon: float,
    body: str = "sun", preset: str = "none",
) -> list[StationDay]:
    """Consecutive days, capped at MAX_DAYS."""
    if days < 1:
        raise ValueError("days must be at least 1")
    if days > MAX_DAYS:
        raise ValueError(
            f"a maximum of {MAX_DAYS} days may be requested at once; "
            f"{days} were asked for"
        )
    return [
        stations_for_day(start + timedelta(days=i), lat, lon, body, preset)
        for i in range(days)
    ]


def next_station(
    moment: datetime, lat: float, lon: float, body: str = "sun", preset: str = "none"
) -> tuple[Station, StationDay] | None:
    """
    The next station after `moment`, looking up to three days ahead.

    Three days rather than one because at high latitude a lunar station can be
    that far away, and answering "none today" when one falls tomorrow morning is
    unhelpful to someone deciding whether to set an alarm.
    """
    day = moment.astimezone(timezone.utc).date()
    for offset in range(4):
        sd = stations_for_day(day + timedelta(days=offset), lat, lon, body, preset)
        upcoming = [s for s in sd.stations if s.at and s.at > moment]
        if upcoming:
            return min(upcoming, key=lambda s: s.at), sd
    return None
