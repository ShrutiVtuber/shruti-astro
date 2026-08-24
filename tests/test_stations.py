# SPDX-License-Identifier: AGPL-3.0-only
"""
Station times and their export.

The tests are about the two things that make a station tracker wrong in ways
nobody notices: treating noon as a clock time, and treating a missing moonrise
as an error.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from shruti_astro.core.ical import to_ical
from shruti_astro.core.stations import (
    LUNAR_STATIONS, MAX_DAYS, PRESETS, SOLAR_STATIONS,
    next_station, stations_for_day, stations_for_range,
)

ATHENS = (37.9838, 23.7275)
TROMSO = (69.6492, 18.9553)


def test_four_solar_stations_named():
    assert SOLAR_STATIONS == ("sunrise", "noon", "sunset", "midnight")
    assert LUNAR_STATIONS == ("moonrise", "culmination", "moonset", "nadir")


def test_noon_is_the_meridian_transit_not_the_clock():
    """
    Athens sits about 21° west of its zone meridian, so solar noon runs well
    over an hour after 12:00 local — and the equation of time moves it further
    across the year. A rite kept by the clock is kept at the wrong moment.
    """
    d = stations_for_day(date(2026, 8, 24), *ATHENS)
    noon = next(s for s in d.stations if s.name == "noon")
    local = noon.at + timedelta(hours=3)          # EEST
    assert local.hour == 13, f"expected ~13:27 local, got {local.time()}"
    # And it must not be 12:00 on the nose on any day of the year.
    for month in (1, 4, 7, 10):
        n = next(s for s in stations_for_day(date(2026, month, 15), *ATHENS).stations
                 if s.name == "noon")
        assert (n.at + timedelta(hours=2)).strftime("%H:%M") != "12:00"


def test_midnight_is_half_a_day_from_noon():
    d = stations_for_day(date(2026, 8, 24), *ATHENS)
    noon = next(s for s in d.stations if s.name == "noon").at
    midnight = next(s for s in d.stations if s.name == "midnight").at
    gap = abs((noon - midnight).total_seconds()) / 3600
    assert 11.5 < min(gap, 24 - gap) < 12.5


def test_every_station_falls_inside_its_own_day():
    """A station belonging to tomorrow is not this day's station."""
    for d in stations_for_range(date(2026, 8, 24), 5, *ATHENS):
        start = datetime(d.date.year, d.date.month, d.date.day, tzinfo=timezone.utc)
        for s in d.stations:
            if s.occurred:
                assert start <= s.at < start + timedelta(days=1)


def test_the_moon_skips_days_and_says_so():
    """
    The Moon rises ~50 minutes later each day and therefore misses a civil day
    regularly. A blank cell would read as broken; an absent station carries a
    reason.
    """
    absent = [
        s for d in stations_for_range(date(2026, 8, 1), 31, *ATHENS, body="moon")
        for s in d.stations
        if s.name in ("moonrise", "moonset") and not s.occurred
    ]
    assert absent, "expected the Moon to skip at least one rise or set in a month"
    assert all(s.absent_reason for s in absent)
    assert any("fifty minutes" in s.absent_reason for s in absent)


def test_high_latitude_loses_solar_stations_without_erroring():
    """Above the Arctic circle in midsummer there is no sunrise. Not an error."""
    d = stations_for_day(date(2026, 6, 21), *TROMSO)
    names = {s.name for s in d.stations if not s.occurred}
    assert "sunrise" in names or "sunset" in names
    for s in d.stations:
        if not s.occurred:
            assert s.absent_reason


def test_presets_dedicate_solar_stations_only():
    solar = stations_for_day(date(2026, 8, 24), *ATHENS, "sun", preset="hellenic")
    assert any(s.dedication == "Apollo" for s in solar.stations)
    # The preset dedicates the solar stations only; the Moon's four have no
    # godform in either set.
    lunar = stations_for_day(date(2026, 8, 24), *ATHENS, "moon", preset="hellenic")
    assert all(s.dedication == "" for s in lunar.stations)


def test_thelemic_preset_carries_the_resh_godforms():
    d = stations_for_day(date(2026, 8, 24), *ATHENS, "sun", preset="thelemic")
    assert [s.dedication for s in d.stations] == ["Ra", "Ahathoor", "Tum", "Khephra"]


def test_the_month_cap_is_enforced_not_truncated():
    assert len(stations_for_range(date(2026, 8, 1), MAX_DAYS, *ATHENS)) == MAX_DAYS
    with pytest.raises(ValueError, match="maximum"):
        stations_for_range(date(2026, 8, 1), MAX_DAYS + 1, *ATHENS)


def test_next_station_looks_past_today():
    found = next_station(datetime(2026, 8, 24, 23, 0, tzinfo=timezone.utc), *ATHENS)
    assert found is not None
    station, _ = found
    assert station.at > datetime(2026, 8, 24, 23, 0, tzinfo=timezone.utc)


def test_bad_body_and_preset_are_refused():
    with pytest.raises(ValueError):
        stations_for_day(date(2026, 8, 24), *ATHENS, body="mars")
    with pytest.raises(ValueError):
        stations_for_day(date(2026, 8, 24), *ATHENS, preset="druidic")


# ── iCal ────────────────────────────────────────────────────────────────────

def _ics(days=3, body="sun", **kw):
    rows = stations_for_range(date(2026, 8, 24), days, *ATHENS, body=body,
                              preset=kw.pop("preset", "hellenic"))
    return to_ical(rows, *ATHENS, generated_at=datetime(2026, 8, 24, tzinfo=timezone.utc), **kw)


def test_times_are_written_in_utc():
    """
    Floating local times ring at the wrong moment on a phone that has crossed a
    timezone. Every instant carries a Z.
    """
    import re
    ics = _ics()
    starts = re.findall(r"DTSTART:(\S+)", ics)
    assert starts and all(s.endswith("Z") for s in starts)


def test_uids_are_stable_across_regeneration():
    """
    A calendar client matches on UID. Stable, and a refetch updates the event;
    unstable, and it accumulates duplicates until the calendar is unusable.
    """
    import re
    a = to_ical(stations_for_range(date(2026, 8, 24), 3, *ATHENS), *ATHENS,
                generated_at=datetime(2026, 8, 24, tzinfo=timezone.utc))
    b = to_ical(stations_for_range(date(2026, 8, 24), 3, *ATHENS), *ATHENS,
                generated_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    assert set(re.findall(r"UID:(\S+)", a)) == set(re.findall(r"UID:(\S+)", b))
    assert "DTSTAMP:20260824" in a and "DTSTAMP:20260901" in b


def test_absent_stations_produce_no_event():
    """
    A calendar cannot say "no moonrise today", and a zero-length event claiming
    to would put a misleading entry in someone's day.
    """
    rows = stations_for_range(date(2026, 8, 1), 31, *ATHENS, body="moon")
    occurred = sum(1 for d in rows for s in d.stations if s.occurred)
    assert _ics.__name__  # keep flake quiet
    ics = to_ical(rows, *ATHENS, generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert ics.count("BEGIN:VEVENT") == occurred
    assert occurred < 31 * 4          # some were skipped


def test_the_calendar_is_rfc_shaped():
    ics = _ics()
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.rstrip("\r\n").endswith("END:VCALENDAR")
    assert "VERSION:2.0" in ics and "PRODID:" in ics
    assert "\r\n" in ics                       # CRLF, per RFC 5545
    assert "REFRESH-INTERVAL" in ics           # so subscribers refetch


def test_alarms_are_optional():
    assert "BEGIN:VALARM" in _ics(alarm_minutes_before=10)
    assert "BEGIN:VALARM" not in _ics(alarm_minutes_before=None)


def test_special_characters_are_escaped():
    ics = _ics()
    # Commas inside a DESCRIPTION must be escaped or the field is truncated.
    assert r"\," in ics


def test_dedications_reach_the_summary():
    assert "Hekate Phosphoros" in _ics(preset="hellenic")


def test_the_moon_carries_its_phase():
    """
    The lunar tracker is designed around a phase column beside the times, and
    the payload had neither phase nor age. A moonrise at the dark moon and one
    at the full are not the same event to anyone keeping the stations.
    """
    from datetime import date

    from shruti_astro.core.stations import stations_for_day

    day = stations_for_day(date(2026, 8, 24), 37.98, 23.73, body="moon")
    assert day.phase in {
        "new", "waxing crescent", "first quarter", "waxing gibbous",
        "full", "waning gibbous", "last quarter", "waning crescent",
    }
    assert day.moon_age_days is not None and 0 <= day.moon_age_days <= 29.6
    assert day.illumination is not None and 0.0 <= day.illumination <= 1.0


def test_the_sun_has_no_phase_column():
    """Phase belongs to the Moon; the solar table must not sprout an empty one."""
    from datetime import date

    from shruti_astro.core.stations import stations_for_day

    day = stations_for_day(date(2026, 8, 24), 37.98, 23.73, body="sun")
    assert day.phase == "" and day.moon_age_days is None


def test_phase_tracks_the_month():
    """Age must actually advance, and the name change with it."""
    from datetime import date, timedelta

    from shruti_astro.core.stations import stations_for_day

    names = set()
    for offset in range(0, 28, 4):
        day = stations_for_day(date(2026, 8, 1) + timedelta(days=offset), 37.98, 23.73, body="moon")
        names.add(day.phase)
    assert len(names) >= 5, f"a month should pass through most phases, saw {names}"
