# SPDX-License-Identifier: AGPL-3.0-only
"""
How the Thelemic date is written.

The line is a date, not a description, so its form is part of its meaning: the
luminaries in glyphs, the signs in glyphs beside them, and the year dated e.v.
Spelling the signs out beside glyph luminaries was the inconsistency this
pins shut.
"""
from datetime import datetime, timezone

from shruti_astro.core import hellenistic as he
from shruti_astro.core.thelemic import thelemic_date

MOMENT = datetime(2026, 8, 25, 2, 30, tzinfo=timezone.utc)


def test_the_signs_are_glyphs_not_names():
    line = thelemic_date(MOMENT).formatted
    for name in he.SIGNS:
        assert name not in line, f"{name} is spelled out; it should be a glyph"
    assert any(g in line for g in he.SIGN_GLYPHS)


def test_the_year_is_dated_e_v():
    line = thelemic_date(MOMENT).formatted
    assert line.endswith("e.v.")
    assert "æræ novæ" not in line


def test_the_luminaries_still_lead_each_half():
    line = thelemic_date(MOMENT).formatted
    assert line.startswith("☉ in ")
    assert " : ☾ in " in line


def test_the_names_survive_in_the_structured_fields():
    """
    The glyphs are for the line. Anything reading the date as data still needs
    a name it can match on, so the fields keep them.
    """
    d = thelemic_date(MOMENT)
    assert d.sun_sign in he.SIGNS
    assert d.moon_sign in he.SIGNS


def test_glyphs_and_names_stay_in_step():
    assert len(he.SIGN_GLYPHS) == len(he.SIGNS) == 12
