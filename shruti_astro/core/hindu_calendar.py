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


# ── the classical authority ─────────────────────────────────────────────────

def hindu_date_ss(moment: datetime, reckoning: str = "amanta") -> HinduDate:
    """
    The same calendar, computed from Sūrya Siddhānta's own tables.

    Not the modern engine with different constants — a separate theory, run in
    its own terms. The two will sometimes name different days, and that is the
    point of offering both.
    """
    from shruti_astro.core.surya_siddhanta import positions as ss_positions

    if reckoning not in RECKONINGS:
        raise ValueError(f"reckoning must be one of {RECKONINGS}")

    jd = _julday(moment)

    def elong(j: float) -> float:
        p = ss_positions(j)
        return (p.moon - p.sun) % 360.0

    def find_new_moon(start: float, forward: bool) -> float:
        step = 0.25 if forward else -0.25
        j = start
        prev = ((elong(j) + 180.0) % 360.0) - 180.0
        for _ in range(200):
            j += step
            cur = ((elong(j) + 180.0) % 360.0) - 180.0
            if (prev < 0) != (cur < 0) and abs(cur - prev) < 180.0:
                lo, hi = (j - step, j) if forward else (j, j - step)
                for _ in range(60):
                    mid = (lo + hi) / 2
                    a = ((elong(lo) + 180.0) % 360.0) - 180.0
                    b = ((elong(mid) + 180.0) % 360.0) - 180.0
                    if (a < 0) != (b < 0):
                        hi = mid
                    else:
                        lo = mid
                return (lo + hi) / 2
            prev = cur
        raise ValueError("could not bracket the Siddhāntic new moon")

    prev_new = find_new_moon(jd, forward=False)
    next_new = find_new_moon(jd, forward=True)

    # Sūrya Siddhānta longitudes are already sidereal in its own frame, so the
    # rāśi comes straight off the Sun without an ayanāṁśa.
    rashi_start = int(ss_positions(prev_new).sun // 30)
    rashi_end = int(ss_positions(next_new - 1e-4).sun // 30)
    month_index = (rashi_start + 1) % 12
    is_adhika = rashi_start == rashi_end
    is_kshaya = ((rashi_end - rashi_start) % 12) >= 2

    e = elong(jd)
    tithi_idx = int(e // 12.0)
    paksha = "Śukla" if tithi_idx < 15 else "Kṛṣṇa"
    if reckoning == "purnimanta" and paksha == "Kṛṣṇa":
        month_index = (month_index + 1) % 12

    from shruti_astro.core.panchanga import tithi as tithi_of
    p = ss_positions(jd)
    t = tithi_of(p.sun, p.moon)

    greg_year = moment.astimezone(timezone.utc).year
    return HinduDate(
        month=MONTHS[month_index], month_index=month_index + 1,
        is_adhika=is_adhika, is_kshaya=is_kshaya,
        paksha=paksha, tithi_index=t.index, tithi_name=t.name,
        reckoning=reckoning,
        years={k: greg_year + v for k, v in ERA_OFFSETS.items()},
        month_start=_from_julday(prev_new), month_end=_from_julday(next_new),
    )


# ── the year as a table of months ───────────────────────────────────────────

def hindu_year(
    gregorian_year: int,
    reckoning: str = "amanta",
    ayanamsa: str = "lahiri",
    authority: str = "drik",
) -> dict:
    """
    Every lunation of a Gregorian year, named, with its span.

    Walks new moon to new moon rather than assuming twelve months, because a
    year with an **adhika māsa** has thirteen and one of them repeats a name.

    The intercalation rule carries a consequence the table must show: an adhika
    month **holds no festivals**. They wait for the *nija* (true) month that
    follows. Software that marks the repeat but lets festivals fall in it puts
    every observance a month early, which is worse than not marking it at all.
    """
    if reckoning not in RECKONINGS:
        raise ValueError(f"reckoning must be one of {RECKONINGS}")

    use_ss = authority == "surya_siddhanta"
    if use_ss:
        from shruti_astro.core.surya_siddhanta import positions as ss_positions

        def elong_at(j: float) -> float:
            p = ss_positions(j)
            return (p.moon - p.sun) % 360.0

        def sun_rashi_at(j: float) -> int:
            return int(ss_positions(j).sun // 30)
    else:
        def elong_at(j: float) -> float:
            return _elongation(j)

        def sun_rashi_at(j: float) -> int:
            return _sun_rashi(j, ayanamsa)

    def next_new_moon(after: float) -> float:
        step = 0.25
        j = after + 1.0            # step off the current root
        prev = ((elong_at(j) + 180.0) % 360.0) - 180.0
        for _ in range(200):
            j += step
            cur = ((elong_at(j) + 180.0) % 360.0) - 180.0
            if (prev < 0) != (cur < 0) and abs(cur - prev) < 180.0:
                lo, hi = j - step, j
                for _ in range(60):
                    mid = (lo + hi) / 2
                    a = ((elong_at(lo) + 180.0) % 360.0) - 180.0
                    b = ((elong_at(mid) + 180.0) % 360.0) - 180.0
                    if (a < 0) != (b < 0):
                        hi = mid
                    else:
                        lo = mid
                return (lo + hi) / 2
            prev = cur
        raise ValueError("could not bracket the next new moon")

    _ensure_init()
    start = _julday(datetime(gregorian_year, 1, 1, tzinfo=timezone.utc)) - 40
    end = _julday(datetime(gregorian_year, 12, 31, 23, 59, tzinfo=timezone.utc))

    # Back up to a new moon before the window opens.
    cursor = next_new_moon(start - 32)
    months: list[dict] = []
    seen_names: dict[str, int] = {}

    while cursor < end:
        nxt = next_new_moon(cursor)
        rashi_start = sun_rashi_at(cursor)
        rashi_end = sun_rashi_at(nxt - 1e-4)
        is_adhika = rashi_start == rashi_end
        spanned = (rashi_end - rashi_start) % 12
        is_kshaya = spanned >= 2

        index = (rashi_start + 1) % 12
        name = MONTHS[index]
        seen_names[name] = seen_names.get(name, 0) + 1

        months.append({
            "name": name,
            "index": index + 1,
            "adhika": is_adhika,
            "kshaya": is_kshaya,
            # The rule that makes intercalation matter rather than decorate.
            "carriesFestivals": not is_adhika,
            "displayName": f"Adhika {name}" if is_adhika else name,
            "start": _from_julday(cursor).isoformat(),
            "end": _from_julday(nxt).isoformat(),
            "days": round(nxt - cursor, 4),
        })
        cursor = nxt

    # Trim to lunations that actually touch the requested year.
    lo = datetime(gregorian_year, 1, 1, tzinfo=timezone.utc).isoformat()
    hi = datetime(gregorian_year, 12, 31, 23, 59, tzinfo=timezone.utc).isoformat()
    months = [m for m in months if m["end"] > lo and m["start"] < hi]

    from shruti_astro.core.samvatsara import eras

    mid_year = _julday(datetime(gregorian_year, 6, 15, tzinfo=timezone.utc))
    return {
        "gregorianYear": gregorian_year,
        "reckoning": reckoning,
        "authority": authority,
        "eras": eras(gregorian_year, sun_rashi_at(mid_year)),
        "hasAdhikaMasa": any(m["adhika"] for m in months),
        "hasKshayaMasa": any(m["kshaya"] for m in months),
        "monthCount": len(months),
        "months": months,
    }
