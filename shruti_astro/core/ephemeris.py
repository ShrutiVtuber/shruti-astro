# SPDX-License-Identifier: AGPL-3.0-only
"""
Swiss Ephemeris access.

Two deliberate choices:

**Moshier by default.** `SEFLG_MOSEPH` is the built-in semi-analytic theory and
needs no data files at all — no 100 MB of `.se1` to ship, license and back up.
Its accuracy is a few arcseconds for the Moon, and since a tithi is 12° wide and
the Moon moves ~13°/day, an arcsecond is about 6.6 seconds of time. That is far
inside any boundary a pañcāṅga cares about. Point `SHRUTI_EPHE_PATH` at real
Swiss files if sub-arcsecond precision is ever wanted.

**Absolute instants everywhere.** Every computation happens in UTC and is
formatted only at the edge. Local time is presentation; a DST boundary must
never be able to move a tithi.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import swisseph as swe

_lock = threading.Lock()
_initialised = False

# Selectable ayanāṁśa. Lahiri is the Indian civil standard; the others are here
# because practitioners genuinely disagree and the disagreement is legitimate.
AYANAMSAS = {
    "lahiri": swe.SIDM_LAHIRI,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
    "raman": swe.SIDM_RAMAN,
    "fagan_bradley": swe.SIDM_FAGAN_BRADLEY,
    "true_citra": swe.SIDM_TRUE_CITRA,
    "true_revati": swe.SIDM_TRUE_REVATI,
}


# Sunrise is not one definition. The traditions disagree, the disagreement is
# real, and picking one globally silently corrupts the other.
#
#   visible_disc — upper limb of the apparent disc, WITH refraction. The
#                  standard almanac sunrise, and the Greco-Egyptian basis for
#                  planetary hours.
#   hindu        — centre of the disc, NO refraction. What Indian pañcāṅgas
#                  print, and what the Vedic day boundary uses.
#
# They differ by a few minutes — enough to move a tithi-at-sunrise across a
# boundary, which is exactly the disagreement that makes two almanacs name
# different days.
RISE_CONVENTIONS = {
    "visible_disc": 0,
    "hindu": swe.BIT_HINDU_RISING,
}


class SunNeverRose(Exception):
    """No rise or no set at this latitude and date — a real polar condition."""


def _ensure_init() -> None:
    global _initialised
    if _initialised:
        return
    with _lock:
        if _initialised:
            return
        path = os.environ.get("SHRUTI_EPHE_PATH")
        if path:
            swe.set_ephe_path(path)
        _initialised = True


def _flags(sidereal: bool = False) -> int:
    base = swe.FLG_SWIEPH if os.environ.get("SHRUTI_EPHE_PATH") else swe.FLG_MOSEPH
    return base | (swe.FLG_SIDEREAL if sidereal else 0)


def _julday(moment: datetime) -> float:
    m = moment.astimezone(timezone.utc)
    return swe.julday(
        m.year, m.month, m.day,
        m.hour + m.minute / 60 + m.second / 3600 + m.microsecond / 3_600_000_000,
        swe.GREG_CAL,
    )


def _from_julday(jd: float) -> datetime:
    y, mo, d, ut = swe.revjul(jd, swe.GREG_CAL)
    return datetime(y, mo, d, tzinfo=timezone.utc) + timedelta(hours=ut)


@dataclass
class Longitudes:
    sun_tropical: float
    moon_tropical: float
    sun_sidereal: float
    moon_sidereal: float
    ayanamsa: float
    ayanamsa_name: str


def longitudes(moment: datetime, ayanamsa: str = "lahiri") -> Longitudes:
    """Tropical and sidereal longitudes of Sun and Moon at one instant."""
    _ensure_init()
    if ayanamsa not in AYANAMSAS:
        raise ValueError(f"unknown ayanamsa: {ayanamsa}")

    jd = _julday(moment)
    with _lock:
        swe.set_sid_mode(AYANAMSAS[ayanamsa], 0, 0)
        sun_t = swe.calc_ut(jd, swe.SUN, _flags())[0][0]
        moon_t = swe.calc_ut(jd, swe.MOON, _flags())[0][0]
        sun_s = swe.calc_ut(jd, swe.SUN, _flags(sidereal=True))[0][0]
        moon_s = swe.calc_ut(jd, swe.MOON, _flags(sidereal=True))[0][0]
        ayan = swe.get_ayanamsa_ut(jd)

    return Longitudes(
        sun_tropical=sun_t % 360, moon_tropical=moon_t % 360,
        sun_sidereal=sun_s % 360, moon_sidereal=moon_s % 360,
        ayanamsa=ayan, ayanamsa_name=ayanamsa,
    )


def _rise_or_set(
    jd_start: float, lat: float, lon: float, rsmi: int, convention: str = "visible_disc"
) -> datetime | None:
    """
    One rise or set after jd_start, or None if it does not occur.

    Signature is (tjd, body, rsmi, geopos, atpress, attemp, flags) — rsmi comes
    before geopos. Getting that order wrong fails loudly, which is the good case;
    what it must never do is silently return a plausible-but-wrong time.

    res == -2 is Swiss Ephemeris telling us the body is circumpolar. That is the
    polar case, reported by the library rather than inferred by us.

    `convention` selects the disc/refraction rule — see RISE_CONVENTIONS.
    """
    _ensure_init()
    if convention not in RISE_CONVENTIONS:
        raise ValueError(f"unknown rise convention: {convention}")
    res, tret = swe.rise_trans(
        jd_start, swe.SUN, rsmi | RISE_CONVENTIONS[convention],
        (lon, lat, 0.0), 0.0, 0.0, _flags(),
    )
    if res < 0 or not tret or not tret[0]:
        return None
    return _from_julday(tret[0])


def sun_events(
    day: datetime, lat: float, lon: float, convention: str = "visible_disc"
) -> tuple[datetime, datetime, datetime]:
    """
    (sunrise, sunset, next sunrise) bracketing `day` at this location.

    Raises SunNeverRose at polar latitudes where one of them does not occur —
    the caller is expected to say so rather than fabricate a day.
    """
    start = day.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    jd0 = _julday(start)

    sunrise = _rise_or_set(jd0, lat, lon, swe.CALC_RISE, convention)
    if sunrise is None:
        raise SunNeverRose("the Sun did not rise at this location on this date")

    sunset = _rise_or_set(_julday(sunrise), lat, lon, swe.CALC_SET, convention)
    if sunset is None:
        raise SunNeverRose("the Sun did not set at this location on this date")

    next_sunrise = _rise_or_set(_julday(sunset), lat, lon, swe.CALC_RISE, convention)
    if next_sunrise is None:
        raise SunNeverRose("the Sun did not rise again after this sunset")

    return sunrise, sunset, next_sunrise
