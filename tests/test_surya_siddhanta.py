# SPDX-License-Identifier: AGPL-3.0-only
"""
Sūrya Siddhānta. Tested against the theory's own claims, not against modern
positions — it is a different authority, and holding it to the ephemeris's
answer would defeat the purpose of having it.
"""

import pytest

from shruti_astro.core.surya_siddhanta import (
    AUTHORITIES, CIVIL_DAYS_PER_MAHAYUGA, KALI_EPOCH_JD, SIDEREAL_YEAR_DAYS,
    YEARS_PER_MAHAYUGA, ahargana, mean_longitude, positions,
)


def test_mean_positions_meet_at_zero_aries_at_the_kali_epoch():
    """The theory's founding claim: a mean conjunction at 0° Meṣa."""
    for body in ("sun", "moon", "moon_apogee"):
        assert mean_longitude(body, 0.0) == pytest.approx(0.0, abs=1e-9)


def test_the_sidereal_year_is_the_canonical_value():
    assert SIDEREAL_YEAR_DAYS == pytest.approx(365.2587565, abs=1e-7)


def test_kali_year_for_2026_is_5127():
    # JD for 2026-08-24 12:00 UTC.
    jd = 2461277.0
    assert round(ahargana(jd) / SIDEREAL_YEAR_DAYS) == 5127


def test_a_mahayuga_of_days_divides_into_its_years():
    assert CIVIL_DAYS_PER_MAHAYUGA / YEARS_PER_MAHAYUGA == SIDEREAL_YEAR_DAYS


def test_the_node_moves_retrograde():
    """Rāhu goes backwards. If this ever reads increasing, the sign flipped."""
    a = mean_longitude("moon_node", 1_000_000.0)
    b = mean_longitude("moon_node", 1_000_100.0)
    assert (a - b) % 360 < 180, "the node must decrease in longitude"


def test_the_moon_runs_far_faster_than_the_sun():
    p1 = positions(KALI_EPOCH_JD + 1_000_000)
    p2 = positions(KALI_EPOCH_JD + 1_000_001)
    moon_step = (p2.moon - p1.moon) % 360
    sun_step = (p2.sun - p1.sun) % 360
    assert 11.0 < moon_step < 16.0        # ~13.2°/day
    assert 0.9 < sun_step < 1.1           # ~1°/day


def test_the_suns_equation_peaks_near_two_degrees_ten_minutes():
    """The concentric epicycle gives arcsin(13°40'/360) ≈ 2.176°."""
    import math
    from shruti_astro.core.surya_siddhanta import EPICYCLE, _mandaphala
    peak = max(abs(_mandaphala(k, EPICYCLE["sun"])) for k in range(0, 360))
    assert 2.10 < peak < 2.25


def test_positions_stay_in_the_circle():
    for offset in (0, 1_000, 1_000_000, 1_872_811):
        p = positions(KALI_EPOCH_JD + offset)
        for value in (p.sun, p.moon, p.moon_apogee, p.moon_node):
            assert 0.0 <= value < 360.0


def test_both_authorities_are_described_and_neither_is_ranked():
    assert set(AUTHORITIES) == {"drik", "surya_siddhanta"}
    for a in AUTHORITIES.values():
        assert a["name"] and a["basis"] and a["note"]
    # The Siddhānta's note must state its own limits rather than hide them.
    assert "bīja" in AUTHORITIES["surya_siddhanta"]["note"]


def test_the_calendar_runs_under_both_authorities_and_they_diverge():
    """
    The two authorities must actually disagree, or the selector is theatre.

    Sampling 2026, they name a different tithi on roughly half of days — the
    Siddhāntic Moon is several degrees adrift, which moves tithi boundaries by
    hours and flips the day's name whenever a boundary falls near the sample.
    """
    from datetime import datetime, timezone

    from shruti_astro.core.hindu_calendar import hindu_date, hindu_date_ss

    disagreed = 0
    sampled = 0
    for month in range(1, 13):
        for day in (5, 19):
            m = datetime(2026, month, day, 12, 0, tzinfo=timezone.utc)
            a, b = hindu_date(m), hindu_date_ss(m)
            sampled += 1
            if (a.month, a.paksha, a.tithi_index) != (b.month, b.paksha, b.tithi_index):
                disagreed += 1

    assert sampled == 24
    # Neither identical (which would mean one engine is unused) nor total chaos.
    assert 3 <= disagreed <= 21, f"{disagreed}/{sampled} disagreed"


def test_the_siddhantic_calendar_is_internally_consistent():
    from datetime import datetime, timezone

    from shruti_astro.core.hindu_calendar import MONTHS, hindu_date_ss

    d = hindu_date_ss(datetime(2026, 8, 24, 12, tzinfo=timezone.utc))
    assert d.month in MONTHS
    assert d.paksha in ("Śukla", "Kṛṣṇa")
    assert 1 <= d.tithi_index <= 30
    assert d.month_start < d.month_end
    # A lunation is 29–30 days; anything else means the root-finder slipped.
    assert 28.0 < (d.month_end - d.month_start).total_seconds() / 86400 < 31.0
