# SPDX-License-Identifier: AGPL-3.0-only
"""The Attic calendar — chiefly the backwards third, which is what makes it Attic."""

from datetime import date

import pytest

from shruti_astro.core.attic import (
    ATHENS, INTERCALARY_NAME, MONTH_GREEK, MONTH_NAMES, RECKONINGS,
    BeforeTheCycle, _attic_year, _day_name, attic_day,
)

SYDNEY = (-33.8688, 151.2093)
ANCHORAGE = (61.2181, -149.9003)   # the crescent is not reliably catchable here
USHUAIA = (-54.8019, -68.3029)
QUITO = (-0.1807, -78.4678)


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


# --- the observer -----------------------------------------------------------
#
# The month opens at a sighting, and a sighting happens somewhere. Until this
# was fixed the calendar had no observer at all and quietly answered in UTC,
# which is nobody's calendar.


def test_no_observer_means_athens_and_says_so():
    d = attic_day(date(2026, 8, 24))
    assert (d.latitude, d.longitude) == ATHENS
    assert d.location_defaulted is True


def test_giving_an_observer_clears_the_defaulted_flag():
    d = attic_day(date(2026, 8, 24), *SYDNEY)
    assert d.location_defaulted is False
    assert (d.latitude, d.longitude) == SYDNEY


def test_the_two_reckonings_genuinely_disagree():
    """If they agreed there would be no choice worth offering."""
    con = [m[2] for m in _attic_year(2026, *ATHENS, "conjunction")]
    vis = [m[2] for m in _attic_year(2026, *ATHENS, "visibility")]
    assert sum(a != b for a, b in zip(con, vis)) >= 4


def test_the_same_reckoning_disagrees_between_places():
    ath = [m[2] for m in _attic_year(2026, *ATHENS, "visibility")]
    syd = [m[2] for m in _attic_year(2026, *SYDNEY, "visibility")]
    assert sum(a != b for a, b in zip(ath, syd)) >= 4


def test_an_unknown_reckoning_is_refused():
    with pytest.raises(ValueError, match="reckoning"):
        _attic_year(2026, *ATHENS, "whatever-i-like")


# --- the guard --------------------------------------------------------------


@pytest.mark.parametrize("place", [ATHENS, SYDNEY, QUITO, ANCHORAGE, USHUAIA])
@pytest.mark.parametrize("reckoning", RECKONINGS)
def test_every_month_is_lunar_everywhere(place, reckoning):
    """
    The regression that matters. Swiss Ephemeris will happily report a first
    crescent 21 days after the conjunction at 61°N, and taking that literally
    built a forty-day Metageitnion — and 28- and 31-day months once a fallen
    back month sat beside one that had not. A month runs 29 or 30 days or the
    thing is not a calendar.
    """
    for y in (2025, 2026, 2027):
        months = _attic_year(y, *place, reckoning)
        edges = [m[2] for m in months] + [_attic_year(y + 1, *place, reckoning)[0][2]]
        lengths = {(edges[i + 1] - edges[i]).days for i in range(len(months))}
        assert lengths <= {29, 30}, f"{place} {reckoning} {y}: {sorted(lengths)}"


def test_high_latitude_falls_back_and_admits_it():
    months = _attic_year(2026, *ANCHORAGE, "visibility")
    notes = [m[4] for m in months if m[4]]
    assert notes, "Anchorage cannot catch the crescent; it must say so"
    assert "conjunction" in notes[0]


def test_the_fallback_matches_conjunction_exactly():
    """Falling back has to actually fall back, not land somewhere in between."""
    vis = [m[2] for m in _attic_year(2026, *ANCHORAGE, "visibility")]
    con = [m[2] for m in _attic_year(2026, *ANCHORAGE, "conjunction")]
    assert vis == con


def test_a_non_lunar_month_has_no_attic_day_name():
    """Rather than an IndexError off the end of the ordinals."""
    with pytest.raises(ValueError, match="not lunar"):
        _day_name(21, 31)


def test_intercalation_does_not_depend_on_the_observer():
    """
    The count of months comes from the conjunctions between one solstice and
    the next. Only where each month *opens* is local, so a year is thirteen
    months for everyone or twelve for everyone.
    """
    for y in (2025, 2026, 2027):
        counts = {
            len(_attic_year(y, *place, rk))
            for place in (ATHENS, SYDNEY, ANCHORAGE, QUITO)
            for rk in RECKONINGS
        }
        assert len(counts) == 1, f"{y}: year length disagrees across observers"
