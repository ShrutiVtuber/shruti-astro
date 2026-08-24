# SPDX-License-Identifier: AGPL-3.0-only
"""
Kaṭapayādi is positional. These tests exist because the obvious implementation
— treat it as one more additive cipher — is wrong, and was what shipped first.
"""

import pytest

from shruti_astro.core.katapayadi import encode


def test_the_name_of_the_system_is_its_own_rule():
    """ka, ṭa, pa and ya all mean 1. That is what kaṭapayādi names."""
    for ch in ("क", "ट", "प", "य"):
        assert encode(ch)["number"] == 1


def test_digits_are_read_right_to_left():
    """भारत is bha·ra·ta → 4,2,6 written → 624 read. Not 426, and not 12."""
    r = encode("भारत")
    assert r["digitsInWrittenOrder"] == [4, 2, 6]
    assert r["number"] == 624


def test_only_the_last_consonant_of_a_cluster_counts():
    r = encode("क्ष")
    assert r["digitsInWrittenOrder"] == [6]        # ṣa, not ka
    assert "last consonant" in r["syllables"][0]["reason"]


def test_independent_vowels_are_zero():
    assert encode("अ")["digitsInWrittenOrder"] == [0]


def test_matras_carry_no_digit_of_their_own():
    # भा is one syllable: bha plus a mātrā. One digit, not two.
    assert encode("भा")["digitsInWrittenOrder"] == [4]


def test_no_total_is_offered_and_that_is_deliberate():
    r = encode("भारत")
    assert r["total"] is None
    assert "positional" in r["totalNote"]


def test_other_scripts_are_unreckonable_not_zero():
    r = encode("भारत abc")
    assert r["number"] == 624
    assert set(r["unreckonable"]) == {"a", "b", "c"}


def test_empty_input_yields_no_number():
    assert encode("")["number"] is None


def test_the_rule_is_quoted_in_devanagari():
    assert encode("क")["rule"] == "अङ्कानां वामतो गतिः"
