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
