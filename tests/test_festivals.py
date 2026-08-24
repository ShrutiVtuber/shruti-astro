# SPDX-License-Identifier: AGPL-3.0-only
"""
Festival anchor resolution, checked against published almanac dates for 2026.

These are regression tests for three errors that were live in the first cut,
each of which silently moved a festival:

  1. Comparing an ASCII "shukla" against the transliterated "Śukla", which sent
     every bright-fortnight anchor to the wrong tithi.
  2. Reading the tithi at pradoṣa but the month at noon, which could straddle a
     new moon and move a festival a whole lunation.
  3. Applying the sunrise rule to festivals that are not judged at sunrise.
"""

from datetime import date

import pytest

from shruti_astro.core.festivals import DAY_RULES, resolve

# (anchor, expected 2026 date). Anchors carry the reckoning and day rule the
# tradition actually uses, which is the point.
ALMANAC_2026 = [
    ({"kind": "lunar", "month": "Kārtika", "paksha": "krishna", "tithi": 15,
      "reckoning": "purnimanta", "dayRule": "pradosha"}, date(2026, 11, 8), "Dīpāvalī"),
    ({"kind": "lunar", "month": "Bhādrapada", "paksha": "krishna", "tithi": 8,
      "reckoning": "purnimanta", "dayRule": "nishitha"}, date(2026, 9, 4), "Janmāṣṭamī"),
    ({"kind": "lunar", "month": "Phālguna", "paksha": "shukla", "tithi": 15},
     date(2026, 3, 3), "Holī"),
    ({"kind": "lunar", "month": "Māgha", "paksha": "krishna", "tithi": 14,
      "dayRule": "nishitha"}, date(2026, 2, 15), "Mahā Śivarātri"),
    ({"kind": "lunar", "month": "Āśvina", "paksha": "shukla", "tithi": 10,
      "dayRule": "aparahna"}, date(2026, 10, 20), "Vijayadaśamī"),
    ({"kind": "lunar", "month": "Āśvina", "paksha": "shukla", "tithi": 1},
     date(2026, 10, 11), "Śāradīya Navarātri"),
    ({"kind": "lunar", "month": "Bhādrapada", "paksha": "shukla", "tithi": 4,
      "dayRule": "madhyahna"}, date(2026, 9, 14), "Gaṇeśa Caturthī"),
]


@pytest.mark.parametrize("anchor,expected,name", ALMANAC_2026)
def test_resolves_to_the_published_almanac_date(anchor, expected, name):
    assert resolve(anchor, 2026).date == expected, name


def test_shukla_anchors_are_not_sent_to_the_wrong_tithi():
    """
    Regression: "shukla".capitalize() does not start with "Ś", so an ASCII
    pakṣa silently added fifteen to the tithi and resolved the dark fortnight
    instead of the bright one.
    """
    a = {"kind": "lunar", "month": "Phālguna", "paksha": "shukla", "tithi": 15}
    assert resolve(a, 2026).date == date(2026, 3, 3)
    # Every spelling the data might arrive in must agree.
    for spelling in ("shukla", "Shukla", "SHUKLA", "śukla", "Śukla"):
        assert resolve({**a, "paksha": spelling}, 2026).date == date(2026, 3, 3)


def test_a_nonsense_paksha_is_refused_rather_than_guessed():
    with pytest.raises(ValueError):
        resolve({"kind": "lunar", "month": "Māgha", "paksha": "waxing", "tithi": 5}, 2026)


def test_the_reckoning_moves_the_answer_by_a_whole_lunation():
    """
    Dīpāvalī is "Kārtika Amāvāsyā" in *pūrṇimānta* terms. Under amānta that
    same amāvāsyā ends Āśvina, and reading the label naively lands a month out.
    """
    base = {"kind": "lunar", "month": "Kārtika", "paksha": "krishna", "tithi": 15,
            "dayRule": "pradosha"}
    assert resolve({**base, "reckoning": "purnimanta"}, 2026).date == date(2026, 11, 8)
    assert resolve({**base, "reckoning": "amanta"}, 2026).date == date(2026, 12, 8)


def test_the_day_rule_changes_which_civil_day_owns_the_tithi():
    base = {"kind": "lunar", "month": "Kārtika", "paksha": "krishna", "tithi": 15,
            "reckoning": "purnimanta"}
    assert resolve({**base, "dayRule": "sunrise"}, 2026).date == date(2026, 11, 9)
    assert resolve({**base, "dayRule": "pradosha"}, 2026).date == date(2026, 11, 8)


def test_every_day_rule_is_accepted():
    base = {"kind": "lunar", "month": "Āśvina", "paksha": "shukla", "tithi": 10}
    for rule in DAY_RULES:
        assert resolve({**base, "dayRule": rule}, 2026).date is not None


def test_an_unknown_day_rule_is_refused():
    with pytest.raises(ValueError):
        resolve({"kind": "lunar", "month": "Māgha", "paksha": "shukla",
                 "tithi": 5, "dayRule": "moonrise"}, 2026)


def test_attic_anchors_resolve_by_walking_the_attic_year():
    r = resolve({"kind": "crescent", "month": "Hekatombaion", "day": 28}, 2026)
    assert r.date is not None
    from shruti_astro.core.attic import attic_day
    a = attic_day(r.date)
    assert a.month == "Hekatombaion" and a.day == 28


def test_a_day_a_hollow_month_does_not_have_is_reported_not_faked():
    """Asking for day 30 of a month that ran 29 must not silently return day 29."""
    for year in (2024, 2025, 2026):
        r = resolve({"kind": "crescent", "month": "Poseideon", "day": 30}, year)
        if r.skipped:
            assert "hollow" in r.skipped_reason
            return
        from shruti_astro.core.attic import attic_day
        assert attic_day(r.date).day == 30
