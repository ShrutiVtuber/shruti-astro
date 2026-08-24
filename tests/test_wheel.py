# SPDX-License-Identifier: AGPL-3.0-only
"""The chart figures. Two traditions, two genuinely different diagrams."""

import pytest

from shruti_astro.core.ephemeris import HOUSE_SYSTEMS
from shruti_astro.core.wheel import hellenistic_wheel, vedic_square

BODIES = [
    {"name": "Sun", "longitude": 280.0, "retrograde": False},
    {"name": "Moon", "longitude": 223.0, "retrograde": False},
    {"name": "Mercury", "longitude": 271.0, "retrograde": True},
    {"name": "Rahu", "longitude": 101.0, "retrograde": True},
]
ASPECTS = [{"from": "Sun", "to": "Moon", "aspect": "sextile"}]


def test_campanus_is_offered():
    """The design names six systems; Campanus was the one missing."""
    for h in ("whole_sign", "equal", "placidus", "porphyry", "regiomontanus", "campanus"):
        assert h in HOUSE_SYSTEMS


def test_the_wheel_is_standalone_scalable_svg():
    svg = hellenistic_wheel(51.4, BODIES, ASPECTS)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert 'viewBox="0 0 100 100"' in svg


def test_every_body_reaches_the_wheel():
    svg = hellenistic_wheel(51.4, BODIES, ASPECTS)
    for glyph in ("☉", "☾", "☿", "☊"):
        assert glyph in svg


def test_retrograde_is_marked_on_the_figure():
    assert "℞" in hellenistic_wheel(51.4, BODIES, ASPECTS)


def test_all_twelve_signs_are_drawn():
    svg = hellenistic_wheel(51.4, BODIES)
    for glyph in "♈♉♊♋♌♍♎♏♐♑♒♓":
        assert glyph in svg


def test_a_conjunction_draws_no_aspect_line():
    """Two bodies in the same place need no line between them."""
    plain = hellenistic_wheel(0.0, BODIES)
    conj = hellenistic_wheel(0.0, BODIES,
                             [{"from": "Sun", "to": "Moon", "aspect": "conjunction"}])
    assert plain.count("<line") == conj.count("<line")


def test_aspects_are_distinguished_without_colour():
    sextile = hellenistic_wheel(0.0, BODIES, [{"from": "Sun", "to": "Moon", "aspect": "sextile"}])
    trine = hellenistic_wheel(0.0, BODIES, [{"from": "Sun", "to": "Moon", "aspect": "trine"}])
    # Dash pattern and weight carry the distinction, not hue.
    assert "stroke-dasharray" in sextile
    assert sextile != trine


def test_the_wheel_rotates_with_the_ascendant():
    assert hellenistic_wheel(0.0, BODIES) != hellenistic_wheel(90.0, BODIES)


@pytest.mark.parametrize("style", ["north", "south"])
def test_the_vedic_figure_is_a_square_not_a_wheel(style):
    svg = vedic_square(3, BODIES, style)
    assert "<rect" in svg
    assert "<circle" not in svg


def test_north_and_south_are_different_diagrams():
    """
    Not two styles of one figure. North fixes the houses and moves the signs;
    South fixes the signs. Relabelling one for the other produces a chart a
    Vedic astrologer cannot read.
    """
    assert vedic_square(3, BODIES, "north") != vedic_square(3, BODIES, "south")


def test_the_north_figure_moves_with_the_lagna():
    assert vedic_square(0, BODIES, "north") != vedic_square(6, BODIES, "north")


def test_the_south_figure_does_not_move_with_the_lagna():
    """Signs are fixed in the South Indian arrangement — only the mark moves."""
    a = vedic_square(0, BODIES, "south")
    b = vedic_square(6, BODIES, "south")
    assert a == b


def test_an_unknown_style_is_refused():
    with pytest.raises(ValueError):
        vedic_square(0, BODIES, "east")
