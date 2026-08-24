# SPDX-License-Identifier: AGPL-3.0-only
"""
The contested settings, now doing something.

They were accepted and ignored for several passes — the same state Theourgia's
own note flagged. These tests exist so that cannot silently return.
"""

from datetime import datetime, timezone

import pytest

from shruti_astro.core.solar_phase import BOUNDARIES, solar_phase
from shruti_astro.core.void_of_course import RULES, is_void_of_course


def test_all_three_solar_phase_doctrines_are_offered():
    assert set(BOUNDARIES) == {"paulus", "lilly1647", "medievalUnattributed"}


def test_the_doctrines_disagree_where_it_matters():
    """
    At 0.3° from the Sun, Paulus says cazimi and Lilly says combust, because
    Lilly's cazimi is 17 arcminutes and Paulus's is a whole degree. A tool that
    picks one silently gives the opposite verdict to half its users.
    """
    assert solar_phase(0.3, 0.0, "paulus").state == "cazimi"
    assert solar_phase(0.3, 0.0, "lilly1647").state == "combust"


def test_lilly_reaches_further_out_than_paulus():
    assert solar_phase(16.0, 0.0, "lilly1647").state == "under_beams"
    assert solar_phase(16.0, 0.0, "paulus").state == "free"


@pytest.mark.parametrize("doctrine", list(BOUNDARIES))
def test_the_states_nest_correctly(doctrine):
    cazimi, combust, beams = BOUNDARIES[doctrine]
    assert cazimi < combust < beams
    assert solar_phase(cazimi / 2, 0.0, doctrine).state == "cazimi"
    assert solar_phase((cazimi + combust) / 2, 0.0, doctrine).state == "combust"
    assert solar_phase((combust + beams) / 2, 0.0, doctrine).state == "under_beams"
    assert solar_phase(beams + 1, 0.0, doctrine).state == "free"


def test_separation_wraps_the_short_way():
    assert solar_phase(359.0, 1.0, "paulus").separation == pytest.approx(2.0)


def test_an_unknown_doctrine_is_refused():
    with pytest.raises(ValueError):
        solar_phase(5.0, 0.0, "whichever")


def test_both_void_rules_exist_with_the_corrected_names():
    """The first cut shipped signBounded/orbBased. Both names were wrong."""
    assert set(RULES) == {"thirtyDegrees", "signExit"}


def test_the_two_void_rules_search_different_arcs():
    m = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    a = is_void_of_course(m, "thirtyDegrees")
    b = is_void_of_course(m, "signExit")
    assert a["searchedDegrees"] == 30.0
    assert b["searchedDegrees"] < 30.0        # only to the sign's edge


def test_the_rules_reach_different_verdicts_across_a_month():
    """
    If these ever agree everywhere, one of them has stopped being applied.
    Measured: they differ on roughly a third of moments.
    """
    from datetime import timedelta

    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    disagreed = 0
    for h in range(0, 24 * 5, 6):
        m = base + timedelta(hours=h)
        if (is_void_of_course(m, "thirtyDegrees")["void"]
                != is_void_of_course(m, "signExit")["void"]):
            disagreed += 1
    assert disagreed > 0, "the two void rules never disagreed — one is inert"


def test_an_unknown_void_rule_is_refused():
    with pytest.raises(ValueError):
        is_void_of_course(datetime(2026, 9, 1, tzinfo=timezone.utc), "orbBased")
