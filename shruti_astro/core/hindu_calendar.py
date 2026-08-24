# SPDX-License-Identifier: AGPL-3.0-only
"""
The Hindu lunisolar calendar.

The gap Theourgia's `core/calendars/` does not fill. Everything here rests on
two instants the ephemeris can find exactly — the new moon that opens a lunar
month, and the saṅkrānti at which the Sun changes rāśi — so the calendar is
computed rather than tabulated.

**Two reckonings, both correct.** A lunar month may be taken to end at the new
moon (*amānta*, southern practice) or at the full moon (*pūrṇimānta*, northern).
The same day can therefore sit in differently-named months depending on where
the practitioner stands, and the difference is a fortnight, not a rounding.
Neither is the default-correct one, so the caller chooses — the same ruling the
sunrise conventions follow.

**Intercalation is detected, not assumed.** When a lunar month contains no
saṅkrānti at all, it is *adhika* (repeated); when one contains two, the
following month is *kṣaya* (dropped). Calendars that skip this drift by a whole
month within a couple of years.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import swisseph as swe

from shruti_astro.core.ephemeris import AYANAMSAS, _ensure_init, _flags, _julday, _from_julday

# The twelve lunar months, in order from Chaitra.
MONTHS = [
    "Chaitra", "Vaiśākha", "Jyeṣṭha", "Āṣāḍha", "Śrāvaṇa", "Bhādrapada",
    "Āśvina", "Kārtika", "Mārgaśīrṣa", "Pauṣa", "Māgha", "Phālguna",
]

RECKONINGS = ("amanta", "purnimanta")

# Era offsets from the Gregorian year. Vikrama and Śaka are the two in civil
# use; Kali Yuga is included because ritual almanacs still name it.
ERA_OFFSETS = {"vikrama": 57, "shaka": -78, "kali": 3101}


class Reckoning(str):
    pass


@dataclass
class HinduDate:
    month: str
    month_index: int
    is_adhika: bool
    is_kshaya: bool
    paksha: str
    tithi_index: int
    tithi_name: str
    reckoning: str
    years: dict[str, int]
    month_start: datetime
    month_end: datetime


def _elongation(jd: float) -> float:
    """Moon − Sun, in degrees, 0..360. Zero at new moon, 180 at full."""
    f = _flags()
    sun = swe.calc_ut(jd, swe.SUN, f)[0][0]
    moon = swe.calc_ut(jd, swe.MOON, f)[0][0]
    return (moon - sun) % 360.0


def _find_phase(jd_from: float, target: float, forward: bool = False) -> float:
    """
    The instant nearest `jd_from` at which elongation equals `target`.

    Bisection on the wrapped difference. Coarse-steps first to bracket the
    crossing, because the function is sawtoothed and a naive bisection over a
    whole synodic month lands on the wrong root.
    """
    step = 0.25 if forward else -0.25

    def delta(jd: float) -> float:
        return ((_elongation(jd) - target + 180.0) % 360.0) - 180.0

    jd = jd_from
    prev = delta(jd)
    for _ in range(200):                       # ~50 days either way
        jd += step
        cur = delta(jd)
        if prev == 0.0:
            return jd - step
        if (prev < 0) != (cur < 0) and abs(cur - prev) < 180.0:
            lo, hi = (jd - step, jd) if forward else (jd, jd - step)
            for _ in range(60):                # to well under a second
                mid = (lo + hi) / 2
                if (delta(lo) < 0) != (delta(mid) < 0):
                    hi = mid
                else:
                    lo = mid
            return (lo + hi) / 2
        prev = cur
    raise ValueError("could not bracket the requested lunar phase")


def _sun_rashi(jd: float, ayanamsa: str) -> int:
    _ensure_init()
    swe.set_sid_mode(AYANAMSAS[ayanamsa], 0, 0)
    lon = swe.calc_ut(jd, swe.SUN, _flags(sidereal=True))[0][0] % 360.0
    return int(lon * 12 / 360)


def hindu_date(
    moment: datetime,
    reckoning: str = "amanta",
    ayanamsa: str = "lahiri",
) -> HinduDate:
    """The lunar month, pakṣa and tithi in force at `moment`."""
    if reckoning not in RECKONINGS:
        raise ValueError(f"reckoning must be one of {RECKONINGS}")
    if ayanamsa not in AYANAMSAS:
        raise ValueError(f"unknown ayanamsa: {ayanamsa}")

    _ensure_init()
    jd = _julday(moment)

    # The amānta month always runs new moon → new moon; pūrṇimānta shifts the
    # naming boundary to the full moon but keeps the same tithi sequence.
    prev_new = _find_phase(jd, 0.0)
    next_new = _find_phase(jd, 0.0, forward=True)

    # Named for the solar month it opens in: the rāśi the Sun occupies at the
    # new moon, advanced by one.
    rashi_at_start = _sun_rashi(prev_new, ayanamsa)
    month_index = (rashi_at_start + 1) % 12

    # Adhika: no saṅkrānti inside the month at all.
    rashi_at_end = _sun_rashi(next_new - 1e-4, ayanamsa)
    is_adhika = rashi_at_start == rashi_at_end
    # Kṣaya: two saṅkrāntis inside one month, so the next name is skipped.
    spanned = (rashi_at_end - rashi_at_start) % 12
    is_kshaya = spanned >= 2

    elong = _elongation(jd)
    tithi_idx = int(elong // 12.0)
    paksha = "Śukla" if tithi_idx < 15 else "Kṛṣṇa"

    if reckoning == "purnimanta" and paksha == "Kṛṣṇa":
        # The dark fortnight belongs to the *following* month's name in
        # northern reckoning — the fortnight that makes two almanacs disagree.
        month_index = (month_index + 1) % 12

    greg_year = moment.astimezone(timezone.utc).year
    years = {
        "vikrama": greg_year + ERA_OFFSETS["vikrama"],
        "shaka": greg_year + ERA_OFFSETS["shaka"],
        "kali": greg_year + ERA_OFFSETS["kali"],
    }

    from shruti_astro.core.panchanga import tithi as tithi_of
    t = tithi_of(*_sun_moon(jd))

    return HinduDate(
        month=MONTHS[month_index],
        month_index=month_index + 1,
        is_adhika=is_adhika,
        is_kshaya=is_kshaya,
        paksha=paksha,
        tithi_index=t.index,
        tithi_name=t.name,
        reckoning=reckoning,
        years=years,
        month_start=_from_julday(prev_new),
        month_end=_from_julday(next_new),
    )


def _sun_moon(jd: float) -> tuple[float, float]:
    f = _flags()
    return (
        swe.calc_ut(jd, swe.SUN, f)[0][0] % 360.0,
        swe.calc_ut(jd, swe.MOON, f)[0][0] % 360.0,
    )
