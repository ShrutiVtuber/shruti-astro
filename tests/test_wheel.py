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


def test_every_glyph_lands_inside_a_cell():
    """
    A glyph on a grid line belongs to no house.

    The South Indian figure is a 4×4 grid running 2..98 in steps of 24, so the
    only x and y a cell centre can have are 14, 38, 62 and 86. Two signs were
    drawn at x=50 and x=74 — exactly on the lines between cells — which reads
    as a chart whose first two signs are in the wrong houses, and which every
    other test here passed happily: the figure was still a square, still
    differed from North, and still did not move with the lagna.
    """
    import re

    CENTRES = {14.0, 38.0, 62.0, 86.0}
    svg = vedic_square(0, BODIES, "south")
    placed = re.findall(r'<text x="([\d.]+)" y="([\d.]+)"', svg)
    assert placed, "no glyphs were drawn at all"
    for x, y in placed:
        assert float(x) in CENTRES, f"a glyph sits at x={x}, between cells"
        # Sign labels sit 5 above the centre and bodies 3 below it.
        assert float(y) in {c + d for c in CENTRES for d in (0, -5, 3)}, (
            f"a glyph sits at y={y}, outside every cell"
        )


def test_the_south_figure_puts_the_signs_where_they_are_read():
    """
    Mīna in the top-left corner, Meṣa beside it, running clockwise.

    This is the whole of what makes a South Indian chart readable: the reader
    knows where each sign is before they look. Getting the order right but the
    starting corner wrong produces a figure that is internally consistent and
    still unreadable.
    """
    import re

    svg = vedic_square(0, BODIES, "south")
    # The sign glyphs are two codepoints now — the character plus U+FE0E, which
    # asks for text presentation instead of the coloured emoji badge the zodiac
    # block defaults to. Strip it before comparing.
    at = {(float(x), float(y)): g.replace("\ufe0e", "")
          for x, y, g in re.findall(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*>(.\ufe0e?)</text>', svg)}
    assert at.get((14.0, 9.0)) == "♓", "Mīna is not in the top-left corner"
    assert at.get((38.0, 9.0)) == "♈", "Meṣa is not beside it"
    assert at.get((62.0, 9.0)) == "♉", "the signs do not run clockwise from Meṣa"
    assert at.get((86.0, 33.0)) == "♋", "the right-hand column is not in order"


# ── legibility, which is a property and not a matter of taste ───────────────

def test_the_zodiac_is_asked_for_in_text_presentation():
    """
    U+2648..U+2653 default to EMOJI presentation.

    Left alone the twelve signs render as filled coloured badges while the
    planets — which default to text presentation — come out as thin outlines.
    The frame of the chart shouts and the reading whispers, and it reads as a
    styling problem rather than a character-encoding one. U+FE0E is the fix and
    it has to be on every one of them.
    """
    from shruti_astro.core.wheel import SIGN_GLYPHS

    assert len(SIGN_GLYPHS) == 12
    for g in SIGN_GLYPHS:
        assert g.endswith("︎"), f"{g!r} would render as an emoji badge"


def test_the_planets_are_drawn_larger_than_the_signs():
    """The planets are the reading; the signs are the frame."""
    import re

    svg = hellenistic_wheel(0.0, BODIES)
    sizes = [float(m) for m in re.findall(r'font-size="([\d.]+)"', svg)]
    # The body group is the largest text in the figure.
    assert max(sizes) >= 4.6, "the planets are not the loudest thing on the wheel"


def test_two_bodies_at_the_same_degree_are_not_drawn_on_top_of_each_other():
    """
    A conjunction is the most interesting fact a chart has, and drawn honestly
    it is one smudge. Spreading the glyphs and ticking the true degree keeps
    both the legibility and the accuracy.
    """
    import re

    stacked = [
        {"name": "Sun", "longitude": 100.0, "retrograde": False},
        {"name": "Mercury", "longitude": 100.4, "retrograde": False},
        {"name": "Venus", "longitude": 101.0, "retrograde": False},
    ]
    svg = hellenistic_wheel(0.0, stacked)
    points = [(float(x), float(y))
              for x, y in re.findall(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*>[☉☿♀]', svg)]
    assert len(points) == 3
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        apart = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
        assert apart > 1.5, f"two glyphs are {apart:.2f} apart — they overlap"


def test_the_aspect_hairball_is_quieter_than_everything_else():
    """
    Forty lines at full strength turn the middle of the chart into wool and
    bury the twelve marks somebody came to read.
    """
    import re

    aspects = [{"from": a["name"], "to": b["name"], "aspect": "square"}
               for a in BODIES for b in BODIES if a["name"] != b["name"]]
    svg = hellenistic_wheel(0.0, BODIES, aspects)
    group = re.search(r'<g stroke="currentColor" fill="none" opacity="([\d.]+)">', svg)
    assert group, "the aspect group no longer declares an opacity"
    assert float(group.group(1)) <= 0.35, "the aspect lines dominate the figure"


def test_retrograde_does_not_sit_on_the_glyph_it_marks():
    import re

    svg = hellenistic_wheel(0.0, [{"name": "Mars", "longitude": 10.0, "retrograde": True}])
    marks = re.findall(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*>(♂|℞)', svg)
    assert len(marks) == 2
    (x1, y1, _), (x2, y2, _) = marks
    assert (float(x1), float(y1)) != (float(x2), float(y2)), (
        "the retrograde mark is drawn at the same point as the body"
    )
