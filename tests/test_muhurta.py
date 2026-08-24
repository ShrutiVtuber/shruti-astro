# SPDX-License-Identifier: AGPL-3.0-only
"""The day's windows. Tables that are easy to transcribe wrong and hard to spot."""

from datetime import datetime, timedelta, timezone

import pytest

from shruti_astro.core.muhurta import (
    GULIKA, RAHU_KALA, VARA, YAMAGANDA, ayana, rtu, windows,
)

SUNRISE = datetime(2026, 8, 24, 0, 28, tzinfo=timezone.utc)   # Delhi, a Monday
SUNSET = datetime(2026, 8, 24, 13, 17, tzinfo=timezone.utc)


def test_each_table_assigns_every_weekday_a_distinct_eighth():
    for table in (RAHU_KALA, YAMAGANDA, GULIKA):
        assert sorted(table) == list(range(7))
        assert all(1 <= v <= 8 for v in table.values())
        # Seven weekdays, seven different eighths — no weekday shares a slot.
        assert len(set(table.values())) == 7


def test_the_three_windows_never_coincide_on_a_given_day():
    for weekday in range(7):
        slots = {RAHU_KALA[weekday], YAMAGANDA[weekday], GULIKA[weekday]}
        assert len(slots) == 3, f"weekday {weekday} has overlapping windows"


def test_monday_rahu_kala_is_the_second_eighth():
    """The standard table. Monday 2, Saturday 3, Friday 4, Wednesday 5,
    Thursday 6, Tuesday 7, Sunday 8."""
    assert RAHU_KALA[0] == 2 and RAHU_KALA[5] == 3 and RAHU_KALA[4] == 4
    assert RAHU_KALA[2] == 5 and RAHU_KALA[3] == 6 and RAHU_KALA[1] == 7
    assert RAHU_KALA[6] == 8


def test_windows_sit_inside_the_daylight_and_are_an_eighth_long():
    w = windows(SUNRISE, SUNSET, weekday=0)
    daylight = SUNSET - SUNRISE
    for x in w[:3]:
        assert SUNRISE <= x.start < x.end <= SUNSET
        assert abs((x.end - x.start) - daylight / 8) < timedelta(seconds=1)


def test_abhijit_straddles_local_noon():
    w = next(x for x in windows(SUNRISE, SUNSET, 0) if x.name.startswith("Abhijit"))
    midday = SUNRISE + (SUNSET - SUNRISE) / 2
    assert w.start < midday < w.end
    assert abs((w.end - w.start) - (SUNSET - SUNRISE) / 15) < timedelta(seconds=1)


def test_wednesday_abhijit_carries_the_tradition_note():
    w = next(x for x in windows(SUNRISE, SUNSET, 2) if x.name.startswith("Abhijit"))
    assert "Wednesday" in w.note
    # Recorded, not applied — the window is still returned.
    assert w.start < w.end


def test_vara_names_all_seven_days_with_their_rulers():
    assert VARA[0] == ("Somavāra", "Moon")
    assert VARA[6] == ("Ravivāra", "Sun")
    assert len({name for name, _ in VARA.values()}) == 7


@pytest.mark.parametrize(
    "rashi,expected",
    [(9, "Uttarāyaṇa"), (0, "Uttarāyaṇa"), (2, "Uttarāyaṇa"),
     (3, "Dakṣiṇāyana"), (4, "Dakṣiṇāyana"), (8, "Dakṣiṇāyana")],
)
def test_ayana_turns_at_makara_and_karka(rashi, expected):
    assert ayana(rashi) == expected


def test_rtu_pairs_months_into_six_seasons():
    assert rtu(0) == rtu(1) == "Vasanta"        # Chaitra, Vaiśākha
    assert rtu(4) == rtu(5) == "Varṣā"          # Śrāvaṇa, Bhādrapada
    assert len({rtu(i) for i in range(12)}) == 6
