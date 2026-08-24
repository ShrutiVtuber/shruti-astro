# SPDX-License-Identifier: AGPL-3.0-only
"""Aspects. The two traditions disagree, and the tests hold both to their own rules."""

import pytest

from shruti_astro.core.aspects import degree_aspects, graha_drishti, whole_sign_aspects


def _find(aspects, a, b):
    return [x for x in aspects
            if {x.from_body, x.to_body} == {a, b}]


# ── Hellenistic: configuration is by SIGN ───────────────────────────────────
def test_wide_by_degree_but_configured_by_sign():
    """
    Aries 1° and Leo 29° are 148° apart — nowhere near a trine by orb — but the
    signs are four apart, so the tradition says trine. An orb-based engine
    reports nothing here, and that is the classic error.
    """
    got = _find(whole_sign_aspects({"Sun": 1.0, "Mars": 149.0}), "Sun", "Mars")
    assert got and got[0].name == "trine"


def test_close_by_degree_but_averse_by_sign():
    """
    Taurus 29° and Gemini 1° are 2° apart and in aversion — one sign apart is
    not a configuration at all. An orb-based engine calls this a conjunction.
    """
    assert _find(whole_sign_aspects({"Sun": 59.0, "Mars": 61.0}), "Sun", "Mars") == []


@pytest.mark.parametrize(
    "sep_signs,name",
    [(0, "conjunction"), (2, "sextile"), (3, "square"), (4, "trine"), (6, "opposition")],
)
def test_the_five_classical_configurations(sep_signs, name):
    got = _find(whole_sign_aspects({"A": 5.0, "B": 5.0 + sep_signs * 30}), "A", "B")
    assert got and got[0].name == name


@pytest.mark.parametrize("sep_signs", [1, 5])
def test_aversion_produces_no_aspect(sep_signs):
    assert _find(whole_sign_aspects({"A": 5.0, "B": 5.0 + sep_signs * 30}), "A", "B") == []


# ── degree-based, as a refinement ───────────────────────────────────────────
def test_degree_aspect_respects_the_orb():
    assert _find(degree_aspects({"A": 0.0, "B": 117.0}, orb=8.0), "A", "B")
    assert _find(degree_aspects({"A": 0.0, "B": 105.0}, orb=8.0), "A", "B") == []


def test_applying_versus_separating():
    # B is 3° short of a trine and moving faster forward → still closing.
    applying = _find(degree_aspects({"A": 0.0, "B": 117.0},
                                    speeds={"A": 1.0, "B": 13.0}, orb=8.0), "A", "B")[0]
    assert applying.applying is True
    # B is 3° past exact and still moving away → separating.
    separating = _find(degree_aspects({"A": 0.0, "B": 123.0},
                                      speeds={"A": 1.0, "B": 13.0}, orb=8.0), "A", "B")[0]
    assert separating.applying is False


# ── Vedic dṛṣṭi is asymmetric ───────────────────────────────────────────────
def test_every_graha_aspects_the_seventh():
    got = graha_drishti({"Venus": 5.0, "Mercury": 185.0})
    assert any(a.from_body == "Venus" and a.to_body == "Mercury" for a in got)
    assert any(a.from_body == "Mercury" and a.to_body == "Venus" for a in got)


def test_saturns_third_aspect_is_not_returned():
    """
    Saturn in Aries aspects Gemini by its special third. The planet in Gemini
    does not aspect Saturn back — it is five signs away, which is aversion.
    Symmetric aspect code cannot express this and gets it wrong in both
    directions.
    """
    got = graha_drishti({"Saturn": 5.0, "Mercury": 65.0})
    forward = [a for a in got if a.from_body == "Saturn" and a.to_body == "Mercury"]
    back = [a for a in got if a.from_body == "Mercury" and a.to_body == "Saturn"]
    assert forward and forward[0].mutual is False
    assert back == []


def test_mars_and_jupiter_have_their_own_special_aspects():
    # Mars: 4th and 8th. Aries → Cancer is the 4th.
    mars = graha_drishti({"Mars": 5.0, "Moon": 95.0})
    assert any(a.from_body == "Mars" and "4th" in a.name for a in mars)
    # Jupiter: 5th and 9th. Aries → Leo is the 5th.
    jup = graha_drishti({"Jupiter": 5.0, "Sun": 125.0})
    assert any(a.from_body == "Jupiter" and "5th" in a.name for a in jup)


def test_node_aspects_are_opt_in():
    off = graha_drishti({"Rahu": 5.0, "Venus": 125.0}, node_aspects=False)
    on = graha_drishti({"Rahu": 5.0, "Venus": 125.0}, node_aspects=True)
    assert not [a for a in off if a.from_body == "Rahu"]
    assert [a for a in on if a.from_body == "Rahu"]
