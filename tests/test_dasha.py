# SPDX-License-Identifier: AGPL-3.0-only
"""
Vimśottarī. The ladder hangs off one number, so these test the places where a
wrong number becomes a wrong *sequence* rather than a slightly wrong date.
"""

from datetime import datetime, timezone

import pytest

from shruti_astro.core.dasha import (
    LORD_ORDER,
    LORD_YEARS,
    TOTAL_YEARS,
    active_chain,
    balance_at_birth,
    vimshottari,
)

BIRTH = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_the_nine_lords_sum_to_one_hundred_and_twenty():
    assert sum(LORD_YEARS.values()) == TOTAL_YEARS == 120
    assert len(LORD_ORDER) == 9


def test_moon_at_the_very_start_of_a_nakshatra_gets_the_full_period():
    lord, remaining = balance_at_birth(0.0)          # 0° = start of Aśvinī
    assert lord == "Ketu"
    assert remaining == pytest.approx(1.0)


def test_moon_at_the_very_end_gets_almost_nothing():
    span = 360.0 / 27.0
    lord, remaining = balance_at_birth(span - 1e-9)
    assert lord == "Ketu"
    assert remaining < 1e-9


def test_balance_is_the_fraction_remaining_not_elapsed():
    """A Moon a quarter of the way through leaves three quarters, not one."""
    _, remaining = balance_at_birth(13.333333 * 0.25)
    assert remaining == pytest.approx(0.75, abs=1e-4)


def test_sequence_follows_the_fixed_order_from_the_starting_lord():
    periods = vimshottari(BIRTH, 0.0, cycles=1, max_level=1)
    assert [p.lord for p in periods] == [
        "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
    ]


def test_starting_elsewhere_rotates_rather_than_reorders():
    # 140° sidereal is inside Pūrva Phalgunī (133°20'–146°40'), lord Venus.
    periods = vimshottari(BIRTH, 140.0, cycles=1, max_level=1)
    assert periods[0].lord == "Venus"
    assert [p.lord for p in periods] == [
        "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury", "Ketu",
    ]


def test_periods_are_contiguous_with_no_gaps():
    periods = vimshottari(BIRTH, 47.0, cycles=1, max_level=3)
    for a, b in zip(periods, periods[1:]):
        assert a.end == b.start
    for p in periods:
        for a, b in zip(p.children, p.children[1:]):
            assert a.end == b.start
        if p.children:
            assert p.children[0].start == p.start
            assert p.children[-1].end == p.end


def test_a_full_cycle_from_a_nakshatra_start_spans_120_years():
    periods = vimshottari(BIRTH, 0.0, cycles=1, max_level=1)
    span_days = (periods[-1].end - periods[0].start).total_seconds() / 86400
    assert span_days == pytest.approx(120 * 365.25, abs=1.0)


def test_truncated_first_mahadasha_compresses_its_children():
    """
    The subtlety implementations miss: a first mahādaśā cut to its balance does
    not start partway through full-length sub-periods — every antardaśā inside
    it is compressed proportionally, and they must still exactly fill it.
    """
    periods = vimshottari(BIRTH, 6.6666, cycles=1, max_level=2)   # ~half of Aśvinī
    first = periods[0]
    assert first.children[0].start == first.start
    assert first.children[-1].end == first.end
    total = sum((c.end - c.start).total_seconds() for c in first.children)
    assert total == pytest.approx((first.end - first.start).total_seconds(), rel=1e-9)


def test_antardasha_begins_with_its_own_lord():
    periods = vimshottari(BIRTH, 0.0, cycles=1, max_level=2)
    for p in periods:
        assert p.children[0].lord == p.lord


def test_sub_period_proportions_match_the_parent_share():
    periods = vimshottari(BIRTH, 0.0, cycles=1, max_level=2)
    venus = next(p for p in periods if p.lord == "Venus")
    span = (venus.end - venus.start).total_seconds()
    for child in venus.children:
        expected = span * (LORD_YEARS[child.lord] / TOTAL_YEARS)
        assert (child.end - child.start).total_seconds() == pytest.approx(expected, rel=1e-9)


def test_year_length_is_a_choice_and_it_moves_boundaries():
    julian = vimshottari(BIRTH, 0.0, cycles=1, max_level=1, year_length="julian")
    savana = vimshottari(BIRTH, 0.0, cycles=1, max_level=1, year_length="savana")
    # A 360-day year ends the first period materially earlier.
    assert savana[0].end < julian[0].end
    with pytest.raises(ValueError):
        vimshottari(BIRTH, 0.0, year_length="whatever")


def test_active_chain_descends_the_ladder():
    periods = vimshottari(BIRTH, 0.0, cycles=1, max_level=3)
    chain = active_chain(periods, BIRTH)
    assert [c["level"] for c in chain] == [1, 2, 3]
    assert chain[0]["lord"] == chain[1]["lord"] == chain[2]["lord"] == "Ketu"


def test_active_chain_is_empty_before_birth():
    periods = vimshottari(BIRTH, 0.0, cycles=1, max_level=2)
    assert active_chain(periods, datetime(1990, 1, 1, tzinfo=timezone.utc)) == []


# ── the boundary cases that broke the first implementation ──────────────────
@pytest.mark.parametrize(
    "longitude,lord",
    [
        (0.0, "Ketu"),        # 0° Aries — start of Aśvinī
        (120.0, "Ketu"),      # 0° Leo — start of Maghā, and 9 × (360/27) exactly
        (240.0, "Ketu"),      # 0° Sagittarius — start of Mūla
    ],
)
def test_exact_ingress_points_land_in_the_right_nakshatra(longitude, lord):
    """
    360/27 is not representable in binary and rounds up, so `lon // span` puts
    an exact 120° in the *previous* nakṣatra. These are the longitudes a
    practitioner checks against an almanac first.
    """
    got_lord, remaining = balance_at_birth(longitude)
    assert got_lord == lord
    assert remaining == pytest.approx(1.0)
