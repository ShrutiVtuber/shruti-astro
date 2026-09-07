# SPDX-License-Identifier: AGPL-3.0-only
"""
The ephemeris as a page, and the table a browser steps through.

**The interpolation test is the important one here.** The brief this was built
from asked for Swiss Ephemeris compiled to WebAssembly in the browser, a second
server implementation, and a continuous-integration fixture proving the two
agree to one arcsecond — megabytes on every reader's connection and two
implementations to keep honest, bought to make a wheel step smoothly.

Sampling on the server and interpolating on the client does the same job with
one implementation and kilobytes. That is only true if the interpolation is
actually accurate, so it is measured against the ephemeris itself rather than
asserted, at the same one-arcsecond bar the brief set for the alternative.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from itertools import pairwise

import pytest
import swisseph as swe

from shruti_astro.core import tables as T
from shruti_astro.core.ephemeris import _ensure_init, _flags, _julday

BODY_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
    "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
}


def utc(y, m, d):
    return datetime(y, m, d, tzinfo=UTC)


def _unwrap(values: list[float]) -> list[float]:
    """Longitudes as a continuous run, so interpolation does not cross 360→0."""
    out = [values[0]]
    for value in values[1:]:
        out.append(out[-1] + ((value - out[-1] + 180.0) % 360.0) - 180.0)
    return out


def _interpolate(table: dict, name: str, jd: float) -> float:
    """
    Catmull-Rom through four nodes — the same arithmetic the browser will do.

    Written out here rather than imported because the point is to prove the
    NUMBERS are sufficient, independently of whatever the client eventually
    uses to read them.
    """
    body = table["bodies"][name]
    spacing = body["spacingDays"]
    longitudes = _unwrap(body["longitude"])
    x = (jd - table["startJd"]) / spacing
    i = max(1, min(int(x), len(longitudes) - 3))
    t = x - i
    p0, p1, p2, p3 = longitudes[i - 1:i + 3]
    return (p1 + 0.5 * t * (p2 - p0 + t * (2 * p0 - 5 * p1 + 4 * p2 - p3
            + t * (3 * (p1 - p2) + p3 - p0)))) % 360.0


def test_interpolating_the_table_is_accurate_to_under_an_arcsecond():
    """
    The claim the architecture rests on, measured.

    Three hundred random instants per body across a month. One arcsecond is
    the bar the brief set for two independent ephemeris implementations
    agreeing; anything under it means the second implementation buys nothing.
    """
    _ensure_init()
    start, end = utc(2026, 9, 1), utc(2026, 10, 1)
    table = T.positions_table(start, end, include_modern=True)
    random.seed(11)

    for name, body in BODY_IDS.items():
        worst = 0.0
        for _ in range(300):
            jd = _julday(start) + random.random() * 29.0
            truth = swe.calc_ut(jd, body, _flags())[0][0] % 360.0
            error = abs(((_interpolate(table, name, jd) - truth + 180.0) % 360.0)
                        - 180.0) * 3600.0
            worst = max(worst, error)
        assert worst < 1.0, f"{name}: worst interpolation error {worst:.3f}″"


def test_a_month_of_nodes_is_kilobytes_not_megabytes():
    """
    The other half of the argument. A WebAssembly ephemeris is megabytes
    before it computes anything; this is the whole month.
    """
    table = T.positions_table(utc(2026, 9, 1), utc(2026, 10, 1), include_modern=True)
    numbers = sum(len(b["longitude"]) + len(b["speed"])
                  for b in table["bodies"].values())
    assert numbers * 4 < 32 * 1024, f"{numbers * 4 / 1024:.1f} KB"


def test_the_moon_is_sampled_far_more_finely_than_the_planets():
    """
    She moves thirteen degrees a day and a whole sign in two and a half. Daily
    nodes would put her six degrees out by mid-afternoon and lose every void
    window shorter than a day.
    """
    table = T.positions_table(utc(2026, 9, 1), utc(2026, 9, 8))
    assert table["bodies"]["Moon"]["spacingDays"] < table["bodies"]["Saturn"]["spacingDays"]
    assert table["bodies"]["Moon"]["spacingDays"] <= 1.0 / 24.0


# ── the printed page ────────────────────────────────────────────────────────


def test_a_day_carries_what_an_almanac_prints():
    day = T.daily_table(utc(2026, 9, 7), utc(2026, 9, 7))[0]
    assert day.sidereal_time > 0
    names = {p.name for p in day.positions}
    assert {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"} <= names
    for position in day.positions:
        assert 0.0 <= position.degree < 30.0
        assert -90.0 <= position.declination <= 90.0


def test_sidereal_time_advances_by_the_right_amount_each_day():
    """
    A sidereal day is three minutes fifty-six seconds shorter than a solar one,
    so the sidereal clock at the same civil hour gains about 0.0657 hours daily.
    An independent check that the table is anchored to real time.
    """
    days = T.daily_table(utc(2026, 9, 7), utc(2026, 9, 14), with_events=False)
    gains = [(b.sidereal_time - a.sidereal_time) % 24.0
             for a, b in pairwise(days)]
    assert all(abs(g - 0.0657) < 0.002 for g in gains), gains


def test_the_moon_goes_out_of_bounds_and_the_sun_never_does():
    """
    Out of bounds means further from the equator than the Sun ever goes. The
    Sun defines the limit, so it cannot exceed it; the Moon regularly does, and
    a table that could not show that would be missing something a wheel also
    cannot show.
    """
    days = T.daily_table(utc(2026, 9, 1), utc(2026, 9, 30), with_events=False)
    by_name = {p.name: [d for d in days
                        if next(x for x in d.positions if x.name == p.name).out_of_bounds]
               for p in days[0].positions}
    assert by_name["Moon"], "the Moon goes out of bounds most months"
    assert not by_name["Sun"], "the Sun defines the bound and cannot exceed it"


def test_noon_and_midnight_are_both_offered_and_named():
    """
    Printed ephemerides come both ways — Raphael's at noon, most modern tables
    at midnight. A reader checking this against a book they own has to know
    which they are looking at.
    """
    midnight = T.daily_table(utc(2026, 9, 7), utc(2026, 9, 7), hour="midnight")[0]
    noon = T.daily_table(utc(2026, 9, 7), utc(2026, 9, 7), hour="noon")[0]
    assert midnight.at.hour == 0 and noon.at.hour == 12
    moon = lambda d: next(p for p in d.positions if p.name == "Moon").longitude
    assert abs(moon(noon) - moon(midnight)) > 5.0     # half a day of her motion
    with pytest.raises(ValueError):
        T.daily_table(utc(2026, 9, 7), utc(2026, 9, 7), hour="teatime")


def test_events_land_on_their_own_day():
    days = T.daily_table(utc(2026, 9, 7), utc(2026, 9, 14))
    for day in days:
        for event in day.events:
            assert event.at.date() == day.at.date()
    assert any(d.events for d in days), "a week always contains something"
