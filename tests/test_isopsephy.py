# SPDX-License-Identifier: AGPL-3.0-only
"""Isopsephy, checked against values the tradition already agrees on."""

import pytest

from shruti_astro.core.isopsephy import LANGUAGES, catalogue, isopsephy, reduce_digits


def test_all_six_scripts_are_present():
    assert set(LANGUAGES) == {"greek", "hebrew", "english", "coptic", "arabic", "sanskrit"}


def test_every_cipher_cites_a_source():
    for c in catalogue():
        assert c["citation"].strip(), f"{c['slug']} has no citation"
        assert c["letters"] > 0


@pytest.mark.parametrize(
    "text,cipher,expected",
    [
        ("Ἰησοῦς", "greek-iso", 888),        # the classical value
        ("ἀγάπη", "greek-iso", 93),
        ("אמת", "heb-hechrachi", 441),       # emet
        ("חי", "heb-hechrachi", 18),         # chai
    ],
)
def test_known_classical_values(text, cipher, expected):
    assert isopsephy(text, cipher)["total"] == expected


def test_unmatched_characters_are_surfaced_not_zeroed():
    """
    A letter outside the cipher is not worth zero — it is outside the cipher.
    A total whose basis is invisible cannot be reproduced.
    """
    r = isopsephy("Ἰησοῦς and friends", "greek-iso")
    assert r["total"] == 888
    assert set(r["unmatched"]) >= {"a", "n", "d"}


def test_punctuation_and_space_are_not_unmatched():
    r = isopsephy("ἀγάπη, ἀγάπη!", "greek-iso")
    assert r["unmatched"] == []
    assert r["total"] == 186


def test_diacritics_fold_by_default_and_can_be_kept():
    assert isopsephy("Ἰησοῦς", "greek-iso", strip_marks=True)["total"] == 888
    kept = isopsephy("Ἰησοῦς", "greek-iso", strip_marks=False)
    assert kept["total"] <= 888        # accented forms fall outside the mapping


def test_final_sigma_shares_its_value():
    assert isopsephy("ς", "greek-iso")["total"] == isopsephy("σ", "greek-iso")["total"]


def test_theosophic_reduction():
    assert reduce_digits(888).final == 6      # 888 → 24 → 6
    assert reduce_digits(888).steps == [24, 6]
    assert reduce_digits(7).final == 7


def test_unknown_cipher_is_refused():
    with pytest.raises(ValueError):
        isopsephy("x", "not-a-cipher")
