# SPDX-License-Identifier: AGPL-3.0-only
"""The edge cases are the whole point, so they are the tests."""

from datetime import datetime, timezone

import pytest

from shruti_astro.core.planetary_hours import (
    NoPlanetaryHours,
    build_hours,
    current_hour,
)

SR = datetime(2026, 8, 24, 3, 30, tzinfo=timezone.utc)
SS = datetime(2026, 8, 24, 17, 10, tzinfo=timezone.utc)
NSR = datetime(2026, 8, 25, 3, 31, tzinfo=timezone.utc)


def test_first_hour_belongs_to_the_weekday_ruler():
    # 2026-08-24 is a Monday; the first hour after sunrise is the Moon's.
    assert build_hours(SR, SS, NSR, weekday=0)[0].ruler == "Moon"


def test_chaldean_order_advances_into_the_night():
    hours = build_hours(SR, SS, NSR, weekday=0)
    # Moon, Saturn, Jupiter, Mars, Sun, Venus, Mercury, repeating -> hour 13 is Venus.
    assert hours[12].ruler == "Venus"
    assert hours[12].is_night is True


def test_hours_are_unequal_and_seasonal():
    hours = build_hours(SR, SS, NSR, weekday=0)
    day = (hours[0].ends_at - hours[0].starts_at).total_seconds()
    night = (hours[12].ends_at - hours[12].starts_at).total_seconds()
    # A long summer day means day-hours are longer than night-hours. If these
    # ever come out equal, someone has quietly reintroduced clock hours.
    assert day > night


def test_twentyfour_hours_tile_the_cycle_without_gaps():
    hours = build_hours(SR, SS, NSR, weekday=0)
    assert len(hours) == 24
    for a, b in zip(hours, hours[1:]):
        assert a.ends_at == b.starts_at
    assert hours[0].starts_at == SR
    assert hours[-1].ends_at == NSR


def test_polar_day_refuses_rather_than_inventing_hours():
    with pytest.raises(NoPlanetaryHours):
        build_hours(None, None, None, weekday=0)


def test_current_hour_outside_the_cycle_is_none():
    hours = build_hours(SR, SS, NSR, weekday=0)
    assert current_hour(hours, datetime(2026, 8, 26, tzinfo=timezone.utc)) is None


# ── the cycle a moment is actually in ───────────────────────────────────────
#
# `sun_events` brackets a calendar day and starts looking from UTC midnight, so
# between midnight and dawn it returns the sunrise that is still to come. Built
# on that, the hours describe a cycle beginning *after* the moment asked about,
# and the moment falls into none of them.
#
# The symptom was quiet: a journal entry published at half past five in the
# morning came back with no planetary hour at all, and the record simply left
# the line out. Every instant is inside some sunrise-to-sunrise cycle.

ATHENS = (37.9838, 23.7275)


def test_a_pre_dawn_moment_is_inside_its_cycle():
    from shruti_astro.core.ephemeris import sun_cycle

    # 05:30 in Athens, well before an August sunrise.
    moment = datetime(2026, 8, 25, 2, 30, tzinfo=timezone.utc)
    sunrise, _sunset, next_sunrise = sun_cycle(moment, *ATHENS)

    assert sunrise <= moment < next_sunrise, (
        "the cycle returned does not contain the moment it was asked about"
    )
    # It is the night that began the previous evening, so the cycle opened on
    # the day before.
    assert sunrise.date() < moment.date()


def test_every_hour_of_a_day_falls_in_some_planetary_hour():
    """
    The invariant, checked directly rather than at the one time that broke.

    There is no such thing as a moment with no planetary hour — the hours
    tile the whole cycle and the cycles tile all of time. A gap anywhere is a
    bug wherever it is.
    """
    from shruti_astro.core.ephemeris import sun_cycle

    for hour in range(24):
        moment = datetime(2026, 8, 25, hour, 0, tzinfo=timezone.utc)
        sunrise, sunset, next_sunrise = sun_cycle(moment, *ATHENS)
        hours = build_hours(sunrise, sunset, next_sunrise, sunrise.weekday())
        assert current_hour(hours, moment) is not None, (
            f"{moment.isoformat()} fell into no planetary hour"
        )


def test_the_day_ruler_of_a_pre_dawn_moment_is_the_previous_day(): 
    """
    The planetary day runs sunrise to sunrise, so a moment before dawn still
    belongs to yesterday's ruler. Reading the calendar date instead moves the
    ruler on at midnight, which is the wrong boundary.
    """
    from shruti_astro.core.ephemeris import sun_cycle

    moment = datetime(2026, 8, 25, 2, 30, tzinfo=timezone.utc)   # a Tuesday
    sunrise, sunset, next_sunrise = sun_cycle(moment, *ATHENS)
    hours = build_hours(sunrise, sunset, next_sunrise, sunrise.weekday())

    # The cycle opened on Monday, whose ruler is the Moon.
    assert hours[0].ruler == "Moon"
