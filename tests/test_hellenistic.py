# SPDX-License-Identifier: AGPL-3.0-only
"""
Hellenistic judgment. The tests target the places where implementations
usually go wrong, not the places where they usually go right.
"""

import pytest

from shruti_astro.core.doctrine import DEFAULT, Doctrine
from shruti_astro.core.hellenistic import (
    dignities,
    lots,
    sect,
    sign_of,
    whole_sign_places,
)


# ── sect: the true degree rule ──────────────────────────────────────────────
def test_sun_just_past_the_ascendant_is_night():
    """
    The Sun one degree past the ascending degree has not yet risen — it is in
    the twelfth. A whole-sign house approximation puts it in the first place and
    calls the chart diurnal. This is the exact case that rule is retired for.
    """
    assert sect(sun_longitude=101.0, ascendant=100.0).is_day is False


def test_sun_just_before_the_ascendant_is_day():
    """One degree *before* the ascendant is the first place: risen, so diurnal."""
    assert sect(sun_longitude=99.0, ascendant=100.0).is_day is True


def test_sect_survives_the_zodiacal_wrap():
    assert sect(sun_longitude=5.0, ascendant=350.0).is_day is False
    assert sect(sun_longitude=340.0, ascendant=350.0).is_day is True


def test_sect_members_swap_wholesale():
    day, night = sect(99.0, 100.0), sect(101.0, 100.0)
    assert (day.luminary, day.benefic, day.malefic) == ("Sun", "Jupiter", "Saturn")
    assert (night.luminary, night.benefic, night.malefic) == ("Moon", "Venus", "Mars")


# ── lots: every one reverses by sect ────────────────────────────────────────
POS = {
    "Sun": 120.0, "Moon": 200.0, "Venus": 100.0, "Mercury": 130.0,
    "Mars": 60.0, "Jupiter": 300.0, "Saturn": 20.0,
}


def test_fortune_and_spirit_are_mirror_images():
    day = lots(0.0, POS, is_day=True)
    night = lots(0.0, POS, is_day=False)
    assert day["Fortune"] == night["Spirit"]
    assert day["Spirit"] == night["Fortune"]


def test_every_lot_moves_with_sect():
    """
    If any lot came out identical in both sects, its formula is missing the
    reversal — the classic silent error.
    """
    day, night = lots(0.0, POS, True), lots(0.0, POS, False)
    for name in day:
        assert day[name] != night[name], f"{name} did not reverse by sect"


def test_lots_stay_in_the_circle():
    for is_day in (True, False):
        for value in lots(275.0, POS, is_day).values():
            assert 0.0 <= value < 360.0


# ── dignities ───────────────────────────────────────────────────────────────
def test_domicile_and_detriment_oppose():
    assert dignities("Mars", 5.0, True)["domicile"] is True          # Aries
    assert dignities("Mars", 185.0, True)["detriment"] is True       # Libra


def test_exaltation_sign_level_is_the_default():
    # Saturn exalts in Libra. At sign level, anywhere in Libra counts.
    assert dignities("Saturn", 185.0, True)["exaltation"] is True


def test_degree_mode_is_where_the_saturn_choice_bites():
    deg21 = Doctrine(exaltation_degrees="degree", saturn_exaltation_degree=21)
    deg20 = Doctrine(exaltation_degrees="degree", saturn_exaltation_degree=20)
    # 21° Libra = 180 + 21
    assert dignities("Saturn", 201.5, True, deg21)["exaltation"] is True
    assert dignities("Saturn", 201.5, True, deg20)["exaltation"] is False
    assert dignities("Saturn", 200.5, True, deg20)["exaltation"] is True


def test_fall_is_opposite_the_exaltation():
    # Sun exalts in Aries, falls in Libra.
    assert dignities("Sun", 190.0, True)["fall"] is True


def test_triplicity_follows_sect():
    # Fire: Sun by day, Jupiter by night, Saturn participating in both.
    assert dignities("Sun", 5.0, True)["triplicity"] is True
    assert dignities("Sun", 5.0, False)["triplicity"] is False
    assert dignities("Jupiter", 5.0, False)["triplicity"] is True
    assert dignities("Saturn", 5.0, True)["triplicity"] is True
    assert dignities("Saturn", 5.0, False)["triplicity"] is True


def test_egyptian_bounds_at_their_edges():
    # Aries: Jupiter 0–6, Venus 6–12.
    assert dignities("Jupiter", 5.99, True)["bound"] == "Jupiter"
    assert dignities("Jupiter", 6.00, True)["bound"] == "Venus"
    # Pisces closes with Saturn 28–30.
    assert dignities("Saturn", 359.0, True)["bound"] == "Saturn"


def test_faces_run_chaldean_order_continuously():
    assert dignities("Mars", 5.0, True)["face"] == "Mars"        # Aries I
    assert dignities("Sun", 15.0, True)["face"] == "Sun"         # Aries II
    assert dignities("Venus", 25.0, True)["face"] == "Venus"     # Aries III
    assert dignities("Mercury", 35.0, True)["face"] == "Mercury"  # Taurus I
    assert dignities("Mars", 355.0, True)["face"] == "Mars"      # Pisces III


# ── places ──────────────────────────────────────────────────────────────────
def test_whole_sign_places_start_at_the_rising_sign():
    places = whole_sign_places(100.0)          # 10° Cancer
    assert places[0]["sign"] == "Cancer" and places[0]["name"] == "Horoskopos"
    assert places[6]["sign"] == "Capricorn" and places[6]["name"] == "Descendant"
    assert places[9]["name"] == "Midheaven"
    assert len(places) == 12


def test_sign_of_wraps():
    assert sign_of(0.0) == 0 and sign_of(359.9) == 11 and sign_of(360.0) == 0
