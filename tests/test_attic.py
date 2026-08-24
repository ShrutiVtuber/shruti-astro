# SPDX-License-Identifier: AGPL-3.0-only
"""The Attic calendar — chiefly the backwards third, which is what makes it Attic."""

from datetime import date

import pytest

from shruti_astro.core.attic import (
    INTERCALARY_NAME, MONTH_GREEK, MONTH_NAMES, BeforeTheCycle, _attic_year,
    _day_name, attic_day,
)


def test_twelve_months_named_in_both_scripts():
    assert len(MONTH_NAMES) == len(MONTH_GREEK) == 12


def test_the_first_third_counts_forward():
    g, t, decad = _day_name(1, 30)
    assert g == "πρώτη ἱσταμένου" and decad == "ἱσταμένου"


def test_the_twentieth_is_eikas_not_an_ordinal():
    g, _, _ = _day_name(20, 30)
    assert g == "εἰκάς"


def test_the_last_third_counts_backwards():
    """
    Day 21 of a full month is the *tenth from the end*, not the twenty-first.
    Counting it forward is the mistake that makes an Attic date meaningless.
    """
    g, t, decad = _day_name(21, 30)
    assert g == "δεκάτη φθίνοντος"
    assert t == "10 phthinontos"
    assert decad == "φθίνοντος"


def test_the_last_day_belongs_to_both_months():
    for length in (29, 30):
        g, t, _ = _day_name(length, length)
        assert g == "ἕνη καὶ νέα"


def test_a_hollow_month_shifts_the_backwards_count():
    """The same civil day-number names a different day in a hollow month."""
    assert _day_name(21, 30)[0] == "δεκάτη φθίνοντος"
    assert _day_name(21, 29)[0] == "ἐνάτη φθίνοντος"


def test_months_are_twentynine_or_thirty_days():
    for m in range(1, 13):
        d = attic_day(date(2026, m, 15))
        assert d.month_length in (29, 30)
        assert d.is_full == (d.month_length == 30)
        assert 1 <= d.day <= d.month_length


def test_days_remaining_and_day_number_are_consistent():
    for m in (1, 5, 9):
        for day in (3, 17, 26):
            d = attic_day(date(2026, m, day))
            assert d.days_remaining == d.month_length - d.day + 1


def test_an_intercalary_year_inserts_poseideon_two_after_poseideon():
    for start in range(2020, 2030):
        months = _attic_year(start)
        if len(months) == 13:
            names = [m[0] for m in months]
            assert INTERCALARY_NAME in names
            assert names.index(INTERCALARY_NAME) == names.index("Poseideon") + 1
            return
    pytest.fail("no intercalary year found in a decade — 7 in 19 expected")


def test_intercalation_happens_seven_times_in_nineteen():
    counts = sum(1 for y in range(2000, 2019) if len(_attic_year(y)) == 13)
    assert counts == 7, f"expected 7 intercalations in 19 years, got {counts}"


def test_before_the_metonic_cycle_is_refused_not_invented():
    with pytest.raises(BeforeTheCycle):
        _attic_year(-500)


def test_moon_age_tracks_the_day_of_the_month():
    d = attic_day(date(2026, 8, 24))
    # Early in the month the Moon is young; the two must not contradict.
    assert 0.0 <= d.moon_age_days < 29.6
    assert abs(d.moon_age_days - (d.day - 1)) < 3.0
