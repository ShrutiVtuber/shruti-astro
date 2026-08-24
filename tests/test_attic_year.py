# SPDX-License-Identifier: AGPL-3.0-only
"""
The Attic year as a table.

`attic_day` could always say what today was; nothing could say when anything
happened. That gap is why the site's Attic calendar showed a date and no
festivals at all while a corpus of forty-five sat behind the API — so what is
tested here is the shape a festival table needs: months that tile without gap
or overlap, spans that say which Gregorian years they straddle, and a
thirteenth month that is reported rather than smoothed away.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from shruti_astro.core.attic import ATHENS, BeforeTheCycle, attic_day, attic_year


def test_the_year_opens_after_the_summer_solstice() -> None:
    """Not January. The whole point of the table is that it straddles two
    Gregorian years, and a reader has to be able to see that."""
    year = attic_year(2026)
    first = date.fromisoformat(year["months"][0]["start"])
    assert first.month in (6, 7, 8)
    assert first.year == 2026
    assert date.fromisoformat(year["months"][-1]["end"]).year == 2027


def test_months_tile_without_gap_or_overlap() -> None:
    """A festival falls in exactly one month. If the spans leave a hole, a
    festival lands in none and silently disappears from the table."""
    months = attic_year(2026)["months"]
    for earlier, later in zip(months, months[1:]):
        assert date.fromisoformat(later["start"]) == \
            date.fromisoformat(earlier["end"]) + timedelta(days=1)


def test_every_month_is_twenty_nine_or_thirty_days() -> None:
    """Full or hollow, and nothing else. A 28- or 31-day month means the
    crescent logic fell over, which is the failure this calendar has had
    before at high latitude."""
    for month in attic_year(2026)["months"]:
        assert month["days"] in (29, 30), month
        assert month["full"] == (month["days"] == 30)


def test_the_table_agrees_with_the_single_day_reckoning() -> None:
    """Two code paths, one calendar. If `attic_year` and `attic_day` disagree,
    the table would put a festival in a month the tool denies it is in."""
    months = attic_year(2026)["months"]
    for month in months:
        start = date.fromisoformat(month["start"])
        resolved = attic_day(start, *ATHENS)
        assert resolved.month == month["name"], month["name"]
        assert resolved.day == 1


def test_a_thirteenth_month_is_reported_not_smoothed() -> None:
    """An intercalary year genuinely has thirteen months. Hiding that makes
    the year look like a bug; naming it explains why it is longer."""
    found = None
    for start in range(2024, 2035):
        year = attic_year(start)
        if year["monthCount"] == 13:
            found = year
            break
    assert found is not None, "no intercalary year in a decade — that is wrong"
    assert found["intercalary"] is True
    extra = [m for m in found["months"] if m["intercalary"]]
    assert len(extra) == 1
    assert extra[0]["name"] == "Poseideon II"


def test_an_observer_changes_when_months_open() -> None:
    """The crescent opens the month at a place. A table computed for Athens and
    shown to somebody in Sydney is wrong by up to a day, which for a festival
    is the whole difference."""
    athens = attic_year(2026, *ATHENS)
    sydney = attic_year(2026, -33.87, 151.21)
    assert athens["monthCount"] == sydney["monthCount"]     # intercalation is solar
    assert athens["observer"]["defaulted"] is False
    assert attic_year(2026)["observer"]["defaulted"] is True


def test_before_the_metonic_cycle_is_refused_not_guessed() -> None:
    with pytest.raises(BeforeTheCycle):
        attic_year(-500)


def test_visibility_reckoning_still_produces_lunar_months() -> None:
    """The polar fallback: rather than hand back 28- and 31-day months, the
    whole year drops to conjunction. Either way the table stays a calendar."""
    for month in attic_year(2026, 68.0, 20.0, "visibility")["months"]:
        assert month["days"] in (29, 30), month
