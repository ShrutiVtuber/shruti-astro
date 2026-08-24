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


# ── recurring anchors ───────────────────────────────────────────────────────

def test_a_recurring_anchor_returns_every_occurrence():
    """
    Ekādaśī falls about twenty-four times a year. Collapsing that to one date
    would be a different and wrong answer rather than a partial one, so the
    return type differs from an annual anchor's.
    """
    r = resolve({"kind": "lunar", "month": "*", "paksha": "shukla", "tithi": 11}, 2026)
    assert isinstance(r, list)
    assert 11 <= len(r) <= 13          # one per lunation, minus any kṣaya
    assert all(x.date for x in r)


def test_an_annual_anchor_still_returns_one_result():
    r = resolve({"kind": "lunar", "month": "Phālguna", "paksha": "shukla", "tithi": 15}, 2026)
    assert not isinstance(r, list)
    assert r.date == date(2026, 3, 3)


def test_recurring_amavasyas_match_the_lunation_starts():
    """Cross-check against the calendar: every amāvāsyā ends a lunation."""
    from shruti_astro.core.hindu_calendar import hindu_year

    amavasyas = {x.date.isoformat()
                 for x in resolve({"kind": "lunar", "month": "*",
                                   "paksha": "krishna", "tithi": 15}, 2026)}
    starts = {m["start"][:10] for m in hindu_year(2026)["months"]}
    # A new moon ends one month and begins the next, so the amāvāsyā day sits
    # within a day of a lunation boundary.
    near = sum(1 for a in amavasyas
               if any(abs((date.fromisoformat(a) - date.fromisoformat(s)).days) <= 1
                      for s in starts))
    assert near >= len(amavasyas) - 1


def test_an_intercalary_only_observance_is_empty_in_ordinary_years():
    """
    Padminī and Paramā Ekādaśī exist only in an adhika māsa. In a year without
    one, an empty list is the correct answer and not a failure.
    """
    anchor = {"kind": "lunar", "month": "adhika", "paksha": "shukla", "tithi": 11}
    assert resolve(anchor, 2025) == []
    assert resolve(anchor, 2027) == []
    # 2026 has Adhika Jyeṣṭha and 2029 Adhika Chaitra.
    assert resolve(anchor, 2026)
    assert resolve(anchor, 2029)


def test_a_doubled_tithi_is_marked_not_silently_deduped():
    """
    On a vṛddhi Ekādaśī the Smārta and Vaiṣṇava traditions fast on different
    days. Dropping one would be making that ruling for the practitioner.
    """
    r = resolve({"kind": "lunar", "month": "adhika", "paksha": "shukla",
                 "tithi": 11}, 2026)
    if len(r) > 1 and (r[1].date - r[0].date).days == 1:
        assert r[0].doubled and r[1].doubled
        assert "vṛddhi" in r[0].note


def test_a_recurring_anchor_honours_its_day_rule():
    sunrise = resolve({"kind": "lunar", "month": "*", "paksha": "krishna",
                       "tithi": 13}, 2026)
    pradosha = resolve({"kind": "lunar", "month": "*", "paksha": "krishna",
                        "tithi": 13, "dayRule": "pradosha"}, 2026)
    assert [x.date for x in sunrise] != [x.date for x in pradosha]


# ── Attic anchors ───────────────────────────────────────────────────────────

def test_a_monthly_attic_observance_recurs_every_month():
    r = resolve({"kind": "crescent", "day": 1, "recurrence": "monthly"}, 2026)
    assert isinstance(r, list)
    assert 12 <= len(r) <= 13          # thirteen in an intercalary Attic year


def test_the_deipnon_follows_the_month_length_not_a_fixed_number():
    """
    Hekate's Deipnon is the LAST day — ἕνη καὶ νέα — which is day 30 of a full
    month and day 29 of a hollow one. Anchoring it to 30 would silently skip
    every hollow month, and about half of them are.
    """
    from shruti_astro.core.attic import attic_day

    r = resolve({"kind": "crescent", "dayFromEnd": 1, "recurrence": "monthly"}, 2026)
    assert len(r) >= 12
    for occurrence in r:
        a = attic_day(occurrence.date)
        assert a.day == a.month_length          # always the last day
        assert a.day_name_greek == "ἕνη καὶ νέα"
    # Both month lengths must actually appear, or the test proves nothing.
    lengths = {attic_day(o.date).month_length for o in r}
    assert lengths == {29, 30}


def test_the_contested_hollow_rule_is_carried_forward_not_decided():
    r = resolve({"kind": "crescent", "dayFromEnd": 1, "recurrence": "monthly",
                 "hollowMonthRuleContested": "Pritchett vs Meritt"}, 2026)
    hollow = [o for o in r if "hollow" in o.note]
    assert hollow, "expected some hollow months in a year"
    assert all("Pritchett vs Meritt" in o.note for o in hollow)


def test_an_undatable_festival_returns_its_reconstructions_not_a_guess():
    """
    Several Attic festivals are known to have happened and cannot be dated. A
    confident wrong date is worse than an honest absent one.
    """
    r = resolve({
        "kind": "crescent", "month": "Gamelion",
        "dayCertainty": "unknown",
        "dayReconstructions": [
            {"days": [12, 15], "author": "Deubner"},
            {"days": [8, 11], "author": "A. Mommsen"},
        ],
    }, 2026)
    assert r.date is None and r.skipped
    assert "Deubner" in r.skipped_reason and "Mommsen" in r.skipped_reason


def test_a_relative_anchor_asks_for_the_occasion_it_follows():
    r = resolve({"kind": "relative", "month": "Elaphebolion",
                 "after": "occasions:city-dionysia", "dayRange": [14, 17]}, 2026)
    assert r.date is None
    assert "city-dionysia" in r.skipped_reason


def test_a_container_entry_has_no_date_of_its_own():
    """
    Anthesteria names a three-day festival whose days are separate entries.
    Giving the container an anchor too would put four events on three days —
    the empty anchor is deliberate, not a defect.
    """
    for empty in (None, {}):
        r = resolve(empty, 2026)
        assert r.date is None and r.skipped
        assert "container" in r.skipped_reason


def test_the_deipnon_and_amavasya_are_the_same_dark_moon():
    """
    A cross-calendar check worth more than either alone: ἕνη καὶ νέα ends the
    Attic month and amāvāsyā ends the amānta Hindu month, and both are the dark
    of the Moon. Two calendars, two code paths, one sky — if these ever diverge,
    one of the calendars has drifted.
    """
    deipnon = {o.date for o in resolve(
        {"kind": "crescent", "dayFromEnd": 1, "recurrence": "monthly"}, 2026)}
    amavasya = {o.date for o in resolve(
        {"kind": "lunar", "month": "*", "paksha": "krishna", "tithi": 15}, 2026)}
    overlap = deipnon & amavasya
    assert len(overlap) >= 10, (
        f"expected the two calendars to agree on most new moons, "
        f"got {len(overlap)} of {len(amavasya)}"
    )


# ── bhadrā ──────────────────────────────────────────────────────────────────

def test_bhadra_defers_holika_dahan_by_a_day():
    """
    On 2 March 2026 pūrṇimā IS current at pradoṣa — but the karaṇa is Viṣṭi,
    which is bhadrā, and the bonfire must not be lit in it. The rite waits until
    bhadrā ends, which lands on the 3rd. Every published almanac gives the 3rd.

    Without this the pradoṣa rule alone picks the 2nd, which is a day early.
    """
    anchor = {"kind": "lunar", "month": "Phālguna", "paksha": "shukla",
              "tithi": 15, "dayRule": "pradosha", "avoidBhadra": True}
    r = resolve(anchor, 2026)
    assert r.date == date(2026, 3, 3)
    assert "bhadrā" in r.note and "deferred" in r.note


def test_without_the_bhadra_rule_it_lands_a_day_early():
    """The control: the same anchor without the exclusion is wrong, which is
    what makes the exclusion load-bearing rather than decorative."""
    anchor = {"kind": "lunar", "month": "Phālguna", "paksha": "shukla",
              "tithi": 15, "dayRule": "pradosha"}
    assert resolve(anchor, 2026).date == date(2026, 3, 2)


def test_bhadra_defers_raksha_bandhan_too():
    anchor = {"kind": "lunar", "month": "Śrāvaṇa", "paksha": "shukla",
              "tithi": 15, "dayRule": "aparahna", "avoidBhadra": True}
    assert resolve(anchor, 2026).date == date(2026, 8, 28)


def test_bhadra_postpones_rather_than_cancels():
    """
    The first implementation SKIPPED a bhadrā-covered day, which lost the
    festival entirely — by the next day's reckoning moment the tithi has usually
    ended. Bhadrā postpones a rite; it does not abolish it.
    """
    anchor = {"kind": "lunar", "month": "Phālguna", "paksha": "shukla",
              "tithi": 15, "dayRule": "pradosha", "avoidBhadra": True}
    r = resolve(anchor, 2026)
    assert r.date is not None, "a bhadrā-covered festival must still have a date"


def test_bhadra_is_the_vishti_karana_and_is_computed():
    from datetime import datetime, timezone

    from shruti_astro.core.festivals import _is_bhadra, _reckoning_moment, UJJAIN
    from shruti_astro.core.panchanga import karana
    from shruti_astro.core.ephemeris import longitudes

    moment = _reckoning_moment(date(2026, 3, 2), *UJJAIN, "pradosha")
    L = longitudes(moment)
    assert karana(L.sun_tropical, L.moon_tropical).name == "Viṣṭi"
    assert _is_bhadra(moment) is True


def test_a_refined_rule_that_finds_no_day_falls_back_to_sunrise():
    """
    A day rule can find no day at all: the tithi begins and ends between two
    consecutive madhyāhna or pradoṣa moments, so no day carries it AT THAT
    MOMENT even though every day carries it at some moment.

    Measured across 2026–30 this made Rāma Navamī vanish in 2029 and Dhanteras
    in 2028 and 2029. A festival missing from the calendar is a worse error than
    one placed by the base rule, so it falls back and says it fell back.
    """
    anchor = {"kind": "lunar", "month": "Chaitra", "paksha": "shukla",
              "tithi": 9, "dayRule": "madhyahna"}
    r = resolve(anchor, 2029)
    assert r.date is not None, "Rāma Navamī must not disappear from 2029"
    assert "falls back" in r.note


def test_no_dated_festival_disappears_across_five_years():
    """
    The regression this guards: an entry that resolves in the year it was
    checked and vanishes in another. Five years is enough to catch the kṣaya
    cases that one year hides.
    """
    import json
    from pathlib import Path

    data = json.loads(
        (Path(__file__).resolve().parent.parent
         / "shruti_astro" / "data" / "hindu-festivals.json").read_text()
    )
    keep = ("kind", "month", "paksha", "tithi", "reckoning", "dayRule", "avoidBhadra")
    vanished = []
    for entry in data:
        a = entry.get("anchor") or {}
        if not a.get("dayRule") or a.get("month") in ("*", "adhika"):
            continue
        anchor = {k: v for k, v in a.items() if k in keep}
        for year in range(2026, 2031):
            result = resolve(anchor, year)
            if not isinstance(result, list) and result.date is None:
                vanished.append((entry["key"], year))
    assert not vanished, f"these vanish in some years: {vanished}"


# ── a universal service: location, and choice where traditions disagree ─────

def test_festival_dates_depend_on_location():
    """
    A tithi is current at an instant; which civil day owns it depends on when
    the Sun rises where you are. Serving one place's answer to everyone is the
    easiest way for a calendar to be quietly wrong for most of its users.
    """
    anchor = {"kind": "lunar", "month": "Śrāvaṇa", "paksha": "krishna",
              "tithi": 8, "reckoning": "purnimanta", "dayRule": "nishitha"}
    ujjain = resolve(anchor, 2026, lat=23.1765, lon=75.7885).date
    sydney = resolve(anchor, 2026, lat=-33.8688, lon=151.2093).date
    assert ujjain != sydney


def test_a_missing_location_is_reported_not_hidden():
    from shruti_astro.core.festival_registry import year

    defaulted = year("hindu", 2026)["location"]
    assert defaulted["defaulted"] is True
    assert "may not be the answer where you are" in defaulted["note"]

    given = year("hindu", 2026, lat=51.5074, lon=-0.1278)["location"]
    assert given["defaulted"] is False and given["note"] is None


def test_variants_are_all_returned_when_no_school_is_chosen():
    """
    Picking one silently would make a doctrinal ruling for the practitioner.
    """
    from shruti_astro.core.festival_registry import year

    everything = year("hindu", 2026)
    kaushiki = [f for f in everything["festivals"] if f["key"] == "kaushiki-amavasya"]
    assert len(kaushiki) == 2
    assert {f["school"] for f in kaushiki} == {"sunrise", "nishitha"}
    assert kaushiki[0]["date"] != kaushiki[1]["date"]


def test_choosing_a_school_narrows_to_one_answer():
    from shruti_astro.core.festival_registry import year

    for school in ("sunrise", "nishitha"):
        chosen = year("hindu", 2026, school=school)
        kaushiki = [f for f in chosen["festivals"] if f["key"] == "kaushiki-amavasya"]
        assert len(kaushiki) == 1 and kaushiki[0]["school"] == school


def test_the_vaishnava_variant_actually_differs():
    """
    The regression this guards: `avoidDashamiViddha` was read only in the annual
    path, while every ekādaśī anchors with month "*" and routes through the
    recurring one — so the Vaiṣṇava variant returned dates identical to the
    Smārta one. A choice that is not a choice is worse than not offering one.
    """
    base = {"kind": "lunar", "month": "*", "paksha": "shukla", "tithi": 11}
    smarta = {r.date for r in resolve(base, 2026)}
    vaishnava = {r.date for r in resolve({**base, "avoidDashamiViddha": True}, 2026)}
    assert smarta != vaishnava
    assert smarta - vaishnava == {date(2026, 5, 26)}


def test_a_year_with_no_vrddhi_ekadashi_gives_the_schools_the_same_answer():
    """Correct, not a failure — the traditions only diverge on a doubled tithi."""
    base = {"kind": "lunar", "month": "*", "paksha": "shukla", "tithi": 11}
    assert ({r.date for r in resolve(base, 2027)}
            == {r.date for r in resolve({**base, "avoidDashamiViddha": True}, 2027)})


def test_restriction_is_one_uniform_field():
    import json
    from pathlib import Path

    data = json.loads(
        (Path(__file__).resolve().parent.parent
         / "shruti_astro" / "data" / "hindu-festivals.json").read_text()
    )
    levels = {e.get("restriction") for e in data}
    assert levels <= {"none", "detail-withheld", "initiatory"}
    assert all("restriction" in e for e in data), "every entry must declare a level"
    # The three overlapping tags it replaced must be gone.
    for e in data:
        assert not ({"initiatory", "restricted", "restricted-detail"}
                    & set(e.get("tags") or []))


def test_the_cheap_day_rules_were_added_and_candrodaya_was_not():
    from shruti_astro.core.festivals import DAY_RULES

    assert {"arunodaya", "pratahkala", "purvahna"} <= set(DAY_RULES)
    # candrodaya needs a moonrise computation and is longitude-dependent enough
    # to split one festival across two civil days for two cities. It waits for a
    # surface that can express that.
    assert "candrodaya" not in DAY_RULES
