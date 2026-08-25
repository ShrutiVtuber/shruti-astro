# SPDX-License-Identifier: AGPL-3.0-only
"""
The chart wheel, as SVG.

The design treats the wheel as a plate and the tables as the primary reading,
which is the right order: a wheel is a way of *seeing* what the table already
says, and it must be drawn from the same numbers or it becomes a second,
disagreeing source.

Two traditions, two figures. A Hellenistic chart is a circular wheel; a Vedic
chart is conventionally a square North or South Indian diagram. Relabelling one
wheel for both is the tell that software has not understood the difference.
"""

from __future__ import annotations

import math

# VARIATION SELECTOR-15 after every one of these, and it is not decoration.
#
# U+2648..U+2653 have **emoji presentation by default** in Unicode. Left alone
# they render as filled coloured badges — the zodiac as a row of app icons —
# while the planets (U+2609, U+263F…) default to text presentation and come out
# as thin outlines. So the frame of the chart shouts and the reading whispers,
# which is exactly backwards, and it looks like a styling problem rather than a
# character-encoding one. U+FE0E asks for the text form.
TEXT = "\ufe0e"
SIGN_GLYPHS = [g + TEXT for g in "♈♉♊♋♌♍♎♏♐♑♒♓"]
BODY_GLYPHS = {
    "Sun": "☉", "Moon": "☾", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
    "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅", "Neptune": "♆", "Pluto": "♇",
    "Rahu": "☊", "Ketu": "☋",
}

# Configurations, and the stroke that distinguishes them without colour.
# Widths are in viewBox units, where the whole chart is 100 across. These were
# 0.5–0.9, which at that scale draws forty ropes through the middle of the
# figure: the lines came out heavier than the planets they connect, so the eye
# lands on the web instead of on the marks. Halved, and the hard aspects stay a
# touch stronger than the soft ones so the distinction survives at any size and
# without colour.
ASPECT_STROKE = {
    "conjunction": (0.0, "none"),
    "sextile": (0.22, "2 2"),
    "square": (0.34, "none"),
    "trine": (0.28, "none"),
    "opposition": (0.4, "none"),
}


def _pt(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return cx + r * math.cos(a), cy - r * math.sin(a)


def _spread(angles: list[float], least: float = 7.0) -> list[float]:
    """
    Push glyphs apart until none is closer than `least` degrees to its neighbour.

    Two planets a degree apart are drawn on top of each other, and the reader
    sees one smudge where the chart's most interesting fact — a conjunction —
    ought to be. Nudging them apart and ticking the true degree keeps both the
    legibility and the accuracy; drawing them where they really are keeps only
    the accuracy, which nobody can read.

    Relaxation over the angular order, and the order is fixed for the whole run:
    the first version reversed it between passes, which flips the sign of every
    gap and drives a tight cluster further into itself rather than opening it.
    """
    if len(angles) < 2:
        return list(angles)
    order = sorted(range(len(angles)), key=lambda i: angles[i])
    placed = list(angles)
    for _ in range(32):
        moved = False
        for a, b in zip(order, order[1:]):
            gap = placed[b] - placed[a]
            if gap < least:
                push = (least - gap) / 2.0
                placed[a] -= push
                placed[b] += push
                moved = True
        if not moved:
            break
    return placed


def hellenistic_wheel(
    ascendant: float,
    bodies: list[dict],
    aspects: list[dict] | None = None,
    size: int = 640,
) -> str:
    """
    A circular wheel with the ascendant on the left, as the tradition draws it.

    Longitudes are rotated so the ascending degree sits due west on the page —
    the horizon — which is what makes the houses read anticlockwise from it.

    **The planets are the reading and are drawn loudest.** The signs are the
    frame and are drawn quietly; the aspect lines are the faintest thing here,
    because forty of them at full strength turn the middle of the chart into a
    ball of wool and bury the twelve marks somebody actually came to read.
    """
    cx = cy = 50.0
    aspects = aspects or []

    def angle(longitude: float) -> float:
        # Ascendant to the left (180°), increasing longitude anticlockwise.
        return (longitude - ascendant) % 360.0 + 180.0

    out: list[str] = []

    # Rings. The outer band holds the signs; the inner circle holds the lines.
    out.append('<g stroke="currentColor" fill="none" stroke-width="0.35" opacity="0.55">')
    for r in (48, 38, 24):
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}"/>')
    out.append("</g>")

    # Sign boundaries, only across the outer band.
    out.append('<g stroke="currentColor" stroke-width="0.3" opacity="0.4">')
    for i in range(12):
        a = angle(i * 30.0)
        x1, y1 = _pt(cx, cy, 38, a)
        x2, y2 = _pt(cx, cy, 48, a)
        out.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"/>')
    out.append("</g>")

    # Every fifth degree, ticked inside the band. Cheap, and it turns a smooth
    # ring into something you can measure a position against by eye.
    out.append('<g stroke="currentColor" stroke-width="0.2" opacity="0.3">')
    for step in range(0, 360, 5):
        a = angle(float(step))
        long_tick = step % 30 == 0
        x1, y1 = _pt(cx, cy, 38, a)
        x2, y2 = _pt(cx, cy, 40 if long_tick else 39.2, a)
        out.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"/>')
    out.append("</g>")

    # Signs: quiet, and in text presentation. See the note on SIGN_GLYPHS.
    out.append('<g fill="currentColor" font-size="3.6" text-anchor="middle" '
               'dominant-baseline="central" stroke="none" opacity="0.65">')
    for i in range(12):
        a = angle(i * 30.0 + 15.0)
        x, y = _pt(cx, cy, 43.5, a)
        out.append(f'<text x="{x:.2f}" y="{y:.2f}">{SIGN_GLYPHS[i]}</text>')
    out.append("</g>")

    # Aspect lines, faint, inside the inner circle.
    by_name = {b["name"]: b["longitude"] for b in bodies}
    if aspects:
        out.append('<g stroke="currentColor" fill="none" opacity="0.28">')
        for asp in aspects:
            a, b = asp.get("from"), asp.get("to")
            if a not in by_name or b not in by_name:
                continue
            width, dash = ASPECT_STROKE.get(asp.get("aspect", ""), (0.25, "1 2"))
            if width == 0.0:
                continue                       # conjunction needs no line
            x1, y1 = _pt(cx, cy, 24, angle(by_name[a]))
            x2, y2 = _pt(cx, cy, 24, angle(by_name[b]))
            d = f' stroke-dasharray="{dash}"' if dash != "none" else ""
            out.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" '
                       f'y2="{y2:.2f}" stroke-width="{width}"{d}/>')
        out.append("</g>")

    # The horizon, drawn over the lines so it stays findable.
    ax, ay = _pt(cx, cy, 48, angle(ascendant))
    dx, dy = _pt(cx, cy, 48, angle(ascendant + 180))
    out.append(f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{dx:.2f}" y2="{dy:.2f}" '
               'stroke="currentColor" stroke-width="0.5" opacity="0.7"/>')

    # Bodies, spread so none is drawn on top of another, each with a leader
    # back to a tick at its true degree.
    true_angles = [angle(b["longitude"]) for b in bodies]
    drawn = _spread(true_angles)

    out.append('<g stroke="currentColor" stroke-width="0.25" opacity="0.45" fill="none">')
    for real, shown in zip(true_angles, drawn):
        tx1, ty1 = _pt(cx, cy, 37.6, real)
        tx2, ty2 = _pt(cx, cy, 34.5, real)
        out.append(f'<line x1="{tx1:.2f}" y1="{ty1:.2f}" x2="{tx2:.2f}" y2="{ty2:.2f}"/>')
        if abs(shown - real) > 0.4:
            lx, ly = _pt(cx, cy, 31.6, shown)
            out.append(f'<line x1="{tx2:.2f}" y1="{ty2:.2f}" x2="{lx:.2f}" y2="{ly:.2f}"/>')
    out.append("</g>")

    out.append('<g fill="currentColor" font-size="5" text-anchor="middle" '
               'dominant-baseline="central" stroke="none" font-weight="600">')
    for body, shown in zip(bodies, drawn):
        x, y = _pt(cx, cy, 30.5, shown)
        glyph = BODY_GLYPHS.get(body["name"], body["name"][:2])
        out.append(f'<text x="{x:.2f}" y="{y:.2f}">{glyph}</text>')
        if body.get("retrograde"):
            # Beside the glyph, not inside it. Drawn inline it overlapped the
            # body it belonged to and both became unreadable.
            rx, ry = _pt(cx, cy, 30.5, shown)
            out.append(f'<text x="{rx + 2.6:.2f}" y="{ry - 2.2:.2f}" font-size="2.6" '
                       f'font-weight="400" opacity="0.8">℞</text>')
    out.append("</g>")

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
            f'width="{size}" height="{size}" role="img">{"".join(out)}</svg>')


def vedic_square(
    lagna_sign: int, bodies: list[dict], style: str = "north", size: int = 640
) -> str:
    """
    The North or South Indian square chart.

    They are genuinely different diagrams, not styles of one. In the **North**
    figure the houses are fixed on the page and the *signs* move — the lagna
    sign is written into the top-centre diamond. In the **South** figure the
    *signs* are fixed in a known arrangement and the lagna is marked. Getting
    this backwards produces a chart a Vedic astrologer cannot read.
    """
    if style not in ("north", "south"):
        raise ValueError("style must be north or south")

    out: list[str] = ['<g stroke="currentColor" fill="none" stroke-width="0.5">',
                      '<rect x="2" y="2" width="96" height="96"/>']

    houses: dict[int, tuple[float, float]] = {}

    if style == "north":
        out.append('<line x1="2" y1="2" x2="98" y2="98"/>')
        out.append('<line x1="98" y1="2" x2="2" y2="98"/>')
        out.append('<line x1="50" y1="2" x2="2" y2="50"/>')
        out.append('<line x1="2" y1="50" x2="50" y2="98"/>')
        out.append('<line x1="50" y1="98" x2="98" y2="50"/>')
        out.append('<line x1="98" y1="50" x2="50" y2="2"/>')
        centres = [(50, 26), (26, 14), (14, 26), (26, 50), (14, 74), (26, 86),
                   (50, 74), (74, 86), (86, 74), (74, 50), (86, 26), (74, 14)]
        for h, c in enumerate(centres, start=1):
            houses[h] = c
    else:
        # Signs fixed: Meṣa top-left-but-one, running clockwise.
        for i in range(1, 4):
            out.append(f'<line x1="{2 + i * 24}" y1="2" x2="{2 + i * 24}" y2="98"/>')
            out.append(f'<line x1="2" y1="{2 + i * 24}" x2="98" y2="{2 + i * 24}"/>')
        # Cell centres, not arbitrary points: the grid runs 2..98 in steps of
        # 24, so the only centres are 14, 38, 62 and 86. Meṣa sits second along
        # the top and the signs run clockwise from it, which puts Mīna in the
        # corner to its left — the arrangement a South Indian chart is read by.
        ring = [(38, 14), (62, 14), (86, 14), (86, 38), (86, 62), (86, 86),
                (62, 86), (38, 86), (14, 86), (14, 62), (14, 38), (14, 14)]
        for idx, c in enumerate(ring):
            houses[idx + 1] = c
    out.append("</g>")

    out.append('<g fill="currentColor" font-size="4" text-anchor="middle" '
               'dominant-baseline="central" stroke="none">')
    for h, (x, y) in houses.items():
        sign = (lagna_sign + h - 1) % 12 if style == "north" else (h - 1)
        out.append(f'<text x="{x}" y="{y - 5}" opacity="0.6">{SIGN_GLYPHS[sign]}</text>')

    for b in bodies:
        sign = int(b["longitude"] // 30)
        house = ((sign - lagna_sign) % 12) + 1 if style == "north" else sign + 1
        x, y = houses[house]
        glyph = BODY_GLYPHS.get(b["name"], b["name"][:2])
        out.append(f'<text x="{x}" y="{y + 3}">{glyph}</text>')
    out.append("</g>")

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
            f'width="{size}" height="{size}" role="img">{"".join(out)}</svg>')
