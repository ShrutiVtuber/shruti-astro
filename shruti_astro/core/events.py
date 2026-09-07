# SPDX-License-Identifier: AGPL-3.0-only
"""
Everything that happens between two instants.

A horoscope is written from a list of moments, not from a snapshot. "Mercury
turns retrograde on the 14th" is the sentence; a chart for one instant cannot
produce it. This module answers the other question — *what happens between
these two dates* — which is what a column, an ephemeris page and an event table
are all made of.

**Every timestamp is found by root-finding, never by sampling.** A scan finds
the interval a crossing lies in; a bisection then narrows it to well under a
second. Reporting the nearest sampled instant instead would be wrong by up to
half a step, and a step coarse enough to be fast is coarse enough to move an
ingress into the wrong day for half the planet — which is the entire reason the
times matter.

**Second precision is not fussiness.** An ingress at 23:47 UT is the following
day in Athens and the previous day in Los Angeles. The day-level answer that a
reader actually wants can only be derived from an exact instant, so the exact
instant is what is stored and the day is computed per reader.

Scan steps are per body and deliberately conservative. Near a station a planet
can cross the same sign boundary three times, and the risk to guard against is
two crossings inside one step; near a station the planet is slow, so those
crossings are days apart and a half-day step separates them comfortably.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import swisseph as swe

from shruti_astro.core.ephemeris import (
    MODERN,
    TRADITIONAL,
    _ensure_init,
    _flags,
    _from_julday,
    _julday,
)
from shruti_astro.core.hellenistic import SIGNS

# The configurations a classical column speaks in. Minor aspects are a modern
# addition and are offered separately rather than mixed in here.
PTOLEMAIC_ANGLES = (0.0, 60.0, 90.0, 120.0, 180.0)
ASPECT_NAMES = {
    0.0: "conjunction", 60.0: "sextile", 90.0: "square",
    120.0: "trine", 180.0: "opposition",
}

# Days between samples while hunting for a crossing, per body. Chosen from how
# far each can move: the scan only has to guarantee that two crossings never
# share an interval, and the bisection does the precision.
SCAN_STEP = {
    "Moon": 0.25, "Sun": 0.5, "Mercury": 0.5, "Venus": 0.5, "Mars": 0.5,
    "Jupiter": 1.0, "Saturn": 1.0, "Uranus": 1.0, "Neptune": 1.0, "Pluto": 1.0,
}
DEFAULT_STEP = 0.5

# Enough halvings to land inside a millisecond over any interval used here.
BISECTIONS = 60


def _stamp(moment: datetime) -> str:
    """
    UTC, to the second, and said so.

    Rounded rather than truncated, and no finer: the uncertainty in delta-T
    alone is larger than a second across this range, so microseconds in an
    ephemeris timestamp are precision the number does not have. They would also
    triple the size of an event list for nothing.
    """
    rounded = (moment + timedelta(microseconds=500_000)).replace(microsecond=0)
    return rounded.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Event:
    """
    One moment worth writing about.

    `kind` is what happened, `bodies` who it happened to, `at` exactly when in
    UTC. `detail` carries what only that kind needs, so a caller can render a
    table without a branch per kind and without every event growing every
    other event's fields.
    """

    kind: str
    at: datetime
    bodies: tuple[str, ...]
    sign: str = ""
    degree: float = 0.0
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "at": _stamp(self.at),
            "bodies": list(self.bodies),
            "sign": self.sign,
            "degree": round(self.degree, 4),
            **({"detail": self.detail} if self.detail else {}),
        }


def _bodies_for(include_modern: bool, true_node: bool) -> list[tuple[str, int]]:
    out = list(TRADITIONAL)
    if include_modern:
        out += list(MODERN)
    out.append(("Rahu", swe.TRUE_NODE if true_node else swe.MEAN_NODE))
    return out


def _lon(jd: float, body: int) -> float:
    return swe.calc_ut(jd, body, _flags())[0][0] % 360.0


def _speed(jd: float, body: int) -> float:
    return swe.calc_ut(jd, body, _flags())[0][3]


def _sign_of(longitude: float) -> tuple[str, float]:
    index = int(longitude % 360.0 // 30.0) % 12
    return SIGNS[index], longitude % 30.0


def _bisect(f, lo: float, hi: float) -> float:
    """
    Narrow a bracketed sign change in `f` to a fraction of a second.

    `f` must already be known to change sign across [lo, hi]. Bisection rather
    than Brent: the functions here are smooth and the interval is a day at
    most, so the extra machinery buys nothing that sixty halvings do not.
    """
    f_lo = f(lo)
    for _ in range(BISECTIONS):
        mid = (lo + hi) / 2.0
        if (f(mid) < 0.0) == (f_lo < 0.0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _wrapped(delta: float) -> float:
    """A separation folded into (-180, 180]."""
    return ((delta + 180.0) % 360.0) - 180.0


# ── ingresses ───────────────────────────────────────────────────────────────


def ingresses(start: datetime, end: datetime, *, include_modern: bool = False,
              true_node: bool = False) -> list[Event]:
    """
    Every sign boundary crossed, in either direction.

    A retrograde crossing is an ingress too, and is marked as such: a planet
    backing into the previous sign is a real event that a column has to
    account for, and calling both "ingress" without saying which way would make
    the three crossings of a retrograde loop read as three separate arrivals.
    """
    _ensure_init()
    found: list[Event] = []

    for name, body in _bodies_for(include_modern, true_node):
        step = SCAN_STEP.get(name, DEFAULT_STEP)
        jd = _julday(start)
        jd_end = _julday(end)
        index = int(_lon(jd, body) // 30.0)

        while jd < jd_end:
            nxt = min(jd + step, jd_end)
            index_next = int(_lon(nxt, body) // 30.0)
            if index_next != index:
                # Solve on the distance to the boundary being crossed, which is
                # continuous across it while the sign index is not.
                edge = (index_next * 30.0) if (index_next - index) % 12 == 1 \
                    else (index * 30.0)
                at = _bisect(lambda t, e=edge, b=body: _wrapped(_lon(t, b) - e), jd, nxt)
                sign, degree = _sign_of(_lon(at + 1e-4, body))
                found.append(Event(
                    kind="ingress",
                    at=_from_julday(at),
                    bodies=(name,),
                    sign=sign,
                    degree=degree,
                    detail={"retrograde": _speed(at, body) < 0.0,
                            "from": SIGNS[index % 12]},
                ))
                index = index_next
            jd = nxt

    return sorted(found, key=lambda e: e.at)


# ── stations ────────────────────────────────────────────────────────────────


def stations(start: datetime, end: datetime, *, include_modern: bool = False
             ) -> list[Event]:
    """
    Where a planet turns.

    Detected on the sign change of longitudinal speed and refined on the same
    function, so the instant reported is the one where speed is actually zero
    rather than the sample nearest to it. The Sun and Moon never station and
    are not scanned.
    """
    _ensure_init()
    found: list[Event] = []
    scanned = [(n, b) for n, b in _bodies_for(include_modern, False)
               if n not in ("Sun", "Moon", "Rahu")]

    for name, body in scanned:
        step = SCAN_STEP.get(name, DEFAULT_STEP)
        jd, jd_end = _julday(start), _julday(end)
        was = _speed(jd, body)

        while jd < jd_end:
            nxt = min(jd + step, jd_end)
            now = _speed(nxt, body)
            if (now < 0.0) != (was < 0.0):
                at = _bisect(lambda t, b=body: _speed(t, b), jd, nxt)
                sign, degree = _sign_of(_lon(at, body))
                found.append(Event(
                    kind="station",
                    at=_from_julday(at),
                    bodies=(name,),
                    sign=sign,
                    degree=degree,
                    detail={"direction": "retrograde" if now < 0.0 else "direct"},
                ))
            was = now
            jd = nxt

    return sorted(found, key=lambda e: e.at)


# ── lunations ───────────────────────────────────────────────────────────────

PHASES = {0: "new", 1: "first quarter", 2: "full", 3: "last quarter"}


def lunations(start: datetime, end: datetime) -> list[Event]:
    """
    New, first quarter, full and last quarter.

    Solved on the Moon's elongation from the Sun, which increases monotonically
    — the Moon is always the faster body, so the elongation never reverses and
    each quadrant boundary is crossed exactly once per cycle.
    """
    _ensure_init()
    found: list[Event] = []

    def elongation(jd: float) -> float:
        return (_lon(jd, swe.MOON) - _lon(jd, swe.SUN)) % 360.0

    jd, jd_end = _julday(start), _julday(end)
    quadrant = int(elongation(jd) // 90.0)
    step = 0.25

    while jd < jd_end:
        nxt = min(jd + step, jd_end)
        q_next = int(elongation(nxt) // 90.0)
        if q_next != quadrant:
            edge = (q_next * 90.0) % 360.0
            at = _bisect(lambda t, e=edge: _wrapped(elongation(t) - e), jd, nxt)
            sign, degree = _sign_of(_lon(at, swe.MOON))
            found.append(Event(
                kind="lunation",
                at=_from_julday(at),
                bodies=("Moon", "Sun"),
                sign=sign,
                degree=degree,
                detail={"phase": PHASES[q_next % 4]},
            ))
            quadrant = q_next
        jd = nxt

    return found


# ── eclipses ────────────────────────────────────────────────────────────────


def eclipses(start: datetime, end: datetime) -> list[Event]:
    """
    Solar and lunar, from Swiss Ephemeris' own search.

    Not root-found here: an eclipse is a geometric coincidence in three
    dimensions rather than a crossing of one angle, and the library already
    solves it properly. Re-deriving it from longitudes would be both slower and
    less correct.
    """
    _ensure_init()
    found: list[Event] = []
    jd_start, jd_end = _julday(start), _julday(end)

    kinds = (
        ("solar", swe.sol_eclipse_when_glob),
        ("lunar", swe.lun_eclipse_when),
    )
    for which, search in kinds:
        jd = jd_start
        for _ in range(200):                # a decade of eclipses, at most
            try:
                result = search(jd, _flags(), 0, False)
            except Exception:               # noqa: BLE001 — library refuses a range
                break
            retflag, times = result[0], result[1]
            at_jd = times[0]
            if at_jd > jd_end:
                break
            if at_jd >= jd_start:
                lit = swe.MOON if which == "lunar" else swe.SUN
                sign, degree = _sign_of(_lon(at_jd, lit))
                found.append(Event(
                    kind="eclipse",
                    at=_from_julday(at_jd),
                    bodies=("Moon", "Sun"),
                    sign=sign,
                    degree=degree,
                    detail={"of": which, "type": _eclipse_type(retflag)},
                ))
            jd = at_jd + 1.0

    return sorted(found, key=lambda e: e.at)


def _eclipse_type(flags: int) -> str:
    """The library reports the kind as bit flags; name the one that is set."""
    for bit, name in ((swe.ECL_TOTAL, "total"), (swe.ECL_ANNULAR, "annular"),
                      (swe.ECL_PARTIAL, "partial"),
                      (swe.ECL_ANNULAR_TOTAL, "hybrid"),
                      (swe.ECL_PENUMBRAL, "penumbral")):
        if flags & bit:
            return name
    return "unknown"


# ── aspect perfections ──────────────────────────────────────────────────────


def _targets(angle: float) -> tuple[float, ...]:
    """
    The separations at which one configuration perfects.

    A square perfects at +90° and at −90°, which are different moments between
    the same two bodies. Conjunction and opposition have only one each, because
    0 and 360, and 180 and −180, are the same separation.
    """
    return (angle,) if angle in (0.0, 180.0) else (angle, -angle)


def perfections(start: datetime, end: datetime, *, include_modern: bool = False,
                true_node: bool = False, angles: tuple[float, ...] = PTOLEMAIC_ANGLES,
                ) -> list[Event]:
    """
    Every exact configuration between two enabled bodies.

    Solved on the separation folded into (−180, 180], which is continuous
    through every perfection and discontinuous only at the fold. A sign change
    across the fold is rejected by size: a genuine crossing moves the
    separation by a fraction of a degree in half a day, the fold moves it by
    360.

    **Every longitude is computed once.** Ten bodies against forty-five pairs
    and nine targets is fifty thousand samples if each pair walks the ephemeris
    itself, and it was — a month took over eight seconds, nearly all of it
    asking Swiss Ephemeris for the same positions again. The scan now runs over
    one precomputed grid, so the cost is the grid: a few hundred calls instead
    of tens of thousands. Only the bisections touch the ephemeris after that,
    and there is one of those per event rather than per sample.

    Applying or separating is read from the sign of the relative speed at
    perfection, not guessed from which body is faster — a retrograde planet
    reverses that.
    """
    _ensure_init()
    bodies = _bodies_for(include_modern, true_node)
    jd_start, jd_end = _julday(start), _julday(end)

    # One grid, at the finest step any pair needs, shared by all of them.
    step = min(SCAN_STEP.get(name, DEFAULT_STEP) for name, _ in bodies)
    count = max(2, int((jd_end - jd_start) / step) + 2)
    grid = [jd_start + i * step for i in range(count)]
    samples = {name: [_lon(jd, body) for jd in grid] for name, body in bodies}

    found: list[Event] = []
    for i, (name_a, body_a) in enumerate(bodies):
        for name_b, body_b in bodies[i + 1:]:
            # Ketu is not listed: it is exactly opposite Rahu at every instant,
            # so its configurations are Rahu's read the other way round and
            # computing them would double every row for no new fact.
            lon_a, lon_b = samples[name_a], samples[name_b]

            for angle in angles:
                for target in _targets(angle):
                    previous = _wrapped(lon_a[0] - lon_b[0] - target)
                    for k in range(1, count):
                        current = _wrapped(lon_a[k] - lon_b[k] - target)
                        if ((current < 0.0) != (previous < 0.0)
                                and abs(current - previous) < 180.0):
                            def sep(jd: float, t=target, a=body_a, b=body_b) -> float:
                                return _wrapped(_lon(jd, a) - _lon(jd, b) - t)

                            at = _bisect(sep, grid[k - 1], min(grid[k], jd_end))
                            if not (jd_start <= at <= jd_end):
                                previous = current
                                continue
                            sign, degree = _sign_of(_lon(at, body_a))
                            speed = _speed(at, body_a) - _speed(at, body_b)
                            found.append(Event(
                                kind="aspect",
                                at=_from_julday(at),
                                bodies=(name_a, name_b),
                                sign=sign,
                                degree=degree,
                                detail={
                                    "aspect": ASPECT_NAMES.get(angle, f"{angle:g}°"),
                                    "angle": angle,
                                    "separation": round(target, 1),
                                    "closing": speed > 0.0 if target >= 0 else speed < 0.0,
                                },
                            ))
                        previous = current

    return sorted(found, key=lambda e: e.at)


# ── void of course, as windows ──────────────────────────────────────────────


def _moon_back_thirty(perfection_jd: float) -> float:
    """
    When the Moon was thirty degrees short of where she perfects.

    Kenodromia is defined on the Moon's *travel*, not on the clock, so the
    start of a void is found by walking her longitude back thirty degrees and
    solving for the instant — roughly two and a quarter days, but never
    exactly, and the difference is larger than the precision anyone wants here.
    """
    target = _lon(perfection_jd, swe.MOON) - 30.0

    def gone(jd: float) -> float:
        return _wrapped(_lon(jd, swe.MOON) - target)

    lo = perfection_jd - 3.0
    hi = perfection_jd
    return _bisect(gone, lo, hi)


def void_windows(start: datetime, end: datetime, *, rule: str = "thirtyDegrees",
                 ) -> list[Event]:
    """
    The spans during which the Moon is running empty.

    Both rules are derived from the same two lists — the Moon's perfections to
    the six other classical bodies, and her ingresses — because that is what
    makes them comparable. The author's table shows where they disagree, and
    they disagree often and in both directions, so computing them by two
    unrelated routes would leave any divergence looking like a bug in one of
    them.

      - **signExit**: void from her last perfection before leaving a sign,
        until she leaves it.
      - **thirtyDegrees**: void from each perfection until thirty degrees of
        her travel before the next one. This is the Hellenistic rule and the
        daemon's default; it ignores sign boundaries entirely.

    Windows are searched from a fortnight before `start`, because a void in
    progress at the start of a period belongs to that period's table.
    """
    if rule not in ("thirtyDegrees", "signExit"):
        raise ValueError(f"unknown void-of-course rule: {rule}")

    reach_back = start - timedelta(days=14)
    reach_on = end + timedelta(days=14)

    lunar = [e for e in perfections(reach_back, reach_on)
             if "Moon" in e.bodies
             and not ({"Moon", "Rahu"} <= set(e.bodies))]
    moon_ingresses = [e for e in ingresses(reach_back, reach_on)
                      if e.bodies == ("Moon",)]

    windows: list[Event] = []

    if rule == "signExit":
        for entry in moon_ingresses:
            before = [p for p in lunar if p.at < entry.at]
            if not before:
                continue
            began = before[-1].at
            windows.append(_window(began, entry.at, rule, before[-1]))
    else:
        for index, perfection in enumerate(lunar[:-1]):
            nxt = lunar[index + 1]
            ends = _from_julday(_moon_back_thirty(_julday(nxt.at)))
            if ends > perfection.at:
                windows.append(_window(perfection.at, ends, rule, perfection))

    return [w for w in windows
            if w.at < end and w.detail["until"] > _stamp(start)]


def _window(began: datetime, ends: datetime, rule: str, after: Event) -> Event:
    sign, degree = _sign_of(_lon(_julday(began), swe.MOON))
    return Event(
        kind="void",
        at=began,
        bodies=("Moon",),
        sign=sign,
        degree=degree,
        detail={
            "rule": rule,
            "until": _stamp(ends),
            "minutes": round((ends - began).total_seconds() / 60.0),
            "after": f"{after.detail.get('aspect', '')} "
                     f"{next(b for b in after.bodies if b != 'Moon')}".strip(),
        },
    )


# ── everything, in order ────────────────────────────────────────────────────


def events_in_range(start: datetime, end: datetime, *, include_modern: bool = False,
                    true_node: bool = False, void_rule: str = "thirtyDegrees",
                    kinds: tuple[str, ...] | None = None) -> list[Event]:
    """
    The whole list for a period, sorted, ready for a table or a column.

    `kinds` narrows the work as well as the output: perfections between every
    pair of bodies are by far the most expensive thing here, so a caller that
    only wants ingresses should not pay for them.
    """
    wanted = set(kinds) if kinds else {
        "ingress", "station", "lunation", "eclipse", "aspect", "void"}
    out: list[Event] = []

    if "ingress" in wanted:
        out += ingresses(start, end, include_modern=include_modern,
                         true_node=true_node)
    if "station" in wanted:
        out += stations(start, end, include_modern=include_modern)
    if "lunation" in wanted:
        out += lunations(start, end)
    if "eclipse" in wanted:
        out += eclipses(start, end)
    if "aspect" in wanted:
        out += perfections(start, end, include_modern=include_modern,
                           true_node=true_node)
    if "void" in wanted:
        out += void_windows(start, end, rule=void_rule)

    return sorted(out, key=lambda e: e.at)
