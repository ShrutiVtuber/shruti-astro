# SPDX-License-Identifier: AGPL-3.0-only
"""Sigil construction. The two properties that matter are determinism and silence."""

import pytest

from shruti_astro.core.sigil import build, to_svg

STATEMENT = "IT IS MY WILL TO FINISH THE WORK"


def test_the_same_statement_always_draws_the_same_figure():
    """A sigil that changes between sittings cannot be returned to."""
    assert build(STATEMENT).path == build(STATEMENT).path


def test_the_figure_depends_on_the_letter_set_not_the_phrasing():
    a = build("WILL TO FINISH")
    b = build("FINISH TO WILL")
    assert a.letters == b.letters and a.path == b.path


def test_every_step_of_the_reduction_is_shown():
    labels = [s.label for s in build(STATEMENT).steps]
    assert labels == [
        "Statement of intent", "Upper case", "Letters only",
        "Vowels struck", "Repeats struck", "Letter set",
    ]


def test_vowels_are_struck_by_default_and_can_be_kept():
    assert "A" not in build("A CAT").letters
    assert "A" in build("A CAT", keep_vowels=True).letters


def test_repeats_are_struck():
    s = build("LLL MMM NNN")
    assert s.letters == "LMN"


def test_the_statement_never_reaches_the_image():
    """
    The method exists to make the intent unreadable. A tool that writes it into
    the file has undone the work.
    """
    svg = to_svg(build(STATEMENT))
    for fragment in ("WILL", "FINISH", "WORK", "<title", "<desc", "<metadata"):
        assert fragment not in svg


def test_the_svg_is_standalone_and_scalable():
    svg = to_svg(build(STATEMENT))
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert 'viewBox="0 0 100 100"' in svg


@pytest.mark.parametrize("enclosure,circles", [("none", 0), ("circle", 1), ("vesica", 2)])
def test_enclosures_draw_what_they_say(enclosure, circles):
    svg = to_svg(build(STATEMENT, enclosure=enclosure))
    # The start-point mark is also a circle, hence the +1.
    assert svg.count("<circle") == circles + 1


def test_line_weights_change_the_stroke():
    widths = {w: to_svg(build(STATEMENT, line_weight=w)) for w in
              ("hairline", "broad", "engraved")}
    assert len({v[v.index("stroke-width"):][:20] for v in widths.values()}) == 3


def test_a_statement_of_only_vowels_is_exhausted_not_drawn():
    s = build("AEIOU")
    assert s.exhausted is True
    assert "longer statement" in s.exhausted_reason
    with pytest.raises(ValueError):
        to_svg(s)


def test_a_single_surviving_letter_is_also_exhausted():
    assert build("BOB").exhausted is True      # B only


def test_bad_options_are_refused():
    with pytest.raises(ValueError):
        build(STATEMENT, enclosure="hexagon")
    with pytest.raises(ValueError):
        build(STATEMENT, line_weight="thick")
