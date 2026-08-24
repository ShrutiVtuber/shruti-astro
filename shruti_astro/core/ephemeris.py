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


def _ayanamsa_for(jd: float, flags: int) -> float:
    """
    The ayanāṁśa **actually used** by the sidereal positions, not a nearby one.

    `get_ayanamsa_ut` ignores the calculation flags and comes out ~14 arcseconds
    adrift from what `calc_ut(..., FLG_SIDEREAL)` applies. Reporting that number
    means a user who subtracts it from the tropical longitude does not get the
    sidereal longitude we printed — and this project trades on being the one
    whose arithmetic checks out. `get_ayanamsa_ex_ut` takes the same flags and
    reconciles exactly.
    """
    return swe.get_ayanamsa_ex_ut(jd, flags)[1]


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
        ayan = _ayanamsa_for(jd, _flags(sidereal=True))

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


# ── full chart positions ────────────────────────────────────────────────────

# The seven traditional planets, then the lunar nodes. Vedic charts are not
# usable without Rāhu/Ketu; Hellenistic ones simply ignore them.
TRADITIONAL = [
    ("Sun", swe.SUN), ("Moon", swe.MOON), ("Mercury", swe.MERCURY),
    ("Venus", swe.VENUS), ("Mars", swe.MARS), ("Jupiter", swe.JUPITER),
    ("Saturn", swe.SATURN),
]
MODERN = [("Uranus", swe.URANUS), ("Neptune", swe.NEPTUNE), ("Pluto", swe.PLUTO)]

HOUSE_SYSTEMS = {
    "whole_sign": b"W",
    "equal": b"A",
    "placidus": b"P",
    "porphyry": b"O",
    "regiomontanus": b"R",
    "koch": b"K",
}


@dataclass
class Body:
    name: str
    longitude: float          # in the requested zodiac
    latitude: float
    speed: float              # °/day; negative means retrograde
    retrograde: bool


@dataclass
class ChartPositions:
    bodies: list[Body]
    ascendant: float
    midheaven: float
    cusps: list[float]
    ayanamsa: float | None
    sidereal: bool


def chart_positions(
    moment: datetime,
    lat: float,
    lon: float,
    sidereal: bool = False,
    ayanamsa: str = "lahiri",
    house_system: str = "whole_sign",
    include_modern: bool = False,
    true_node: bool = False,
) -> ChartPositions:
    """
    One computation, serving both traditions.

    `sidereal` selects the zodiac: tropical for Hellenistic, sidereal for Vedic.
    Everything downstream — dignities, lots, nakṣatras, navāṁśa — reads from the
    same numbers, so the two readings can never disagree about where a planet is,
    only about which frame to name it in.
    """
    _ensure_init()
    if house_system not in HOUSE_SYSTEMS:
        raise ValueError(f"unknown house system: {house_system}")
    if sidereal and ayanamsa not in AYANAMSAS:
        raise ValueError(f"unknown ayanamsa: {ayanamsa}")

    jd = _julday(moment)
    flags = _flags(sidereal=sidereal)

    wanted = list(TRADITIONAL) + (MODERN if include_modern else [])
    # Vedic convention is the mean node; the true node is offered because some
    # schools use it and the difference is real (up to ~1.5°).
    wanted.append(("Rahu", swe.TRUE_NODE if true_node else swe.MEAN_NODE))

    with _lock:
        if sidereal:
            swe.set_sid_mode(AYANAMSAS[ayanamsa], 0, 0)

        bodies: list[Body] = []
        for name, ident in wanted:
            (lg, lt, _dist, speed, *_), _ = swe.calc_ut(jd, ident, flags)
            bodies.append(
                Body(name=name, longitude=lg % 360, latitude=lt,
                     speed=speed, retrograde=speed < 0)
            )

        cusps, ascmc = swe.houses_ex(
            jd, lat, lon, HOUSE_SYSTEMS[house_system],
            swe.FLG_SIDEREAL if sidereal else 0,
        )
        ayan = _ayanamsa_for(jd, flags) if sidereal else None

    # Ketu is definitionally opposite Rāhu; deriving it keeps them consistent.
    rahu = next(b for b in bodies if b.name == "Rahu")
    bodies.append(
        Body(name="Ketu", longitude=(rahu.longitude + 180.0) % 360.0,
             latitude=-rahu.latitude, speed=rahu.speed, retrograde=rahu.retrograde)
    )

    return ChartPositions(
        bodies=bodies,
        ascendant=ascmc[0] % 360,
        midheaven=ascmc[1] % 360,
        cusps=[c % 360 for c in cusps],
        ayanamsa=ayan,
        sidereal=sidereal,
    )
