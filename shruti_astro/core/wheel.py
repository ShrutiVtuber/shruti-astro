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

SIGN_GLYPHS = "♈♉♊♋♌♍♎♏♐♑♒♓"
BODY_GLYPHS = {
    "Sun": "☉", "Moon": "☾", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
    "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅", "Neptune": "♆", "Pluto": "♇",
    "Rahu": "☊", "Ketu": "☋",
}

# Configurations, and the stroke that distinguishes them without colour.
ASPECT_STROKE = {
    "conjunction": (0.0, "none"),
    "sextile": (0.5, "2 2"),
    "square": (0.7, "none"),
    "trine": (0.7, "none"),
    "opposition": (0.9, "none"),
}


def _pt(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return cx + r * math.cos(a), cy - r * math.sin(a)


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
    """
    cx = cy = 50.0
    aspects = aspects or []

    def angle(longitude: float) -> float:
        # Ascendant to the left (180°), increasing longitude anticlockwise.
        return (longitude - ascendant) % 360.0 + 180.0

    out: list[str] = []
    out.append('<g stroke="currentColor" fill="none" stroke-width="0.4">')
    for r in (48, 38, 26):
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}"/>')
    out.append("</g>")

    # Sign boundaries and glyphs.
    out.append('<g stroke="currentColor" stroke-width="0.3" opacity="0.55">')
    for i in range(12):
        a = angle(i * 30.0)
        x1, y1 = _pt(cx, cy, 38, a)
        x2, y2 = _pt(cx, cy, 48, a)
        out.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"/>')
    out.append("</g>")

    out.append('<g fill="currentColor" font-size="4.2" text-anchor="middle" '
               'dominant-baseline="central" stroke="none">')
    for i in range(12):
        a = angle(i * 30.0 + 15.0)
        x, y = _pt(cx, cy, 43, a)
        out.append(f'<text x="{x:.2f}" y="{y:.2f}">{SIGN_GLYPHS[i]}</text>')
    out.append("</g>")

    # Aspect lines, inside the inner circle.
    by_name = {b["name"]: b["longitude"] for b in bodies}
    if aspects:
        out.append('<g stroke="currentColor" fill="none">')
        for asp in aspects:
            a, b = asp.get("from"), asp.get("to")
            if a not in by_name or b not in by_name:
                continue
            width, dash = ASPECT_STROKE.get(asp.get("aspect", ""), (0.4, "1 2"))
            if width == 0.0:
                continue                       # conjunction needs no line
            x1, y1 = _pt(cx, cy, 26, angle(by_name[a]))
            x2, y2 = _pt(cx, cy, 26, angle(by_name[b]))
            d = f' stroke-dasharray="{dash}"' if dash != "none" else ""
            out.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" '
                       f'y2="{y2:.2f}" stroke-width="{width}" opacity="0.5"{d}/>')
        out.append("</g>")

    # Bodies on the ring between the inner circles.
    out.append('<g fill="currentColor" font-size="4.6" text-anchor="middle" '
               'dominant-baseline="central" stroke="none">')
    for b in bodies:
        a = angle(b["longitude"])
        x, y = _pt(cx, cy, 32, a)
        glyph = BODY_GLYPHS.get(b["name"], b["name"][:2])
        retro = "℞" if b.get("retrograde") else ""
        out.append(f'<text x="{x:.2f}" y="{y:.2f}">{glyph}{retro}</text>')
        # A tick at the exact degree, since the glyph is only approximate.
        tx1, ty1 = _pt(cx, cy, 37, a)
        tx2, ty2 = _pt(cx, cy, 38, a)
        out.append(f'<line x1="{tx1:.2f}" y1="{ty1:.2f}" x2="{tx2:.2f}" '
                   f'y2="{ty2:.2f}" stroke="currentColor" stroke-width="0.4"/>')
    out.append("</g>")

    # The horizon: ascendant to descendant.
    ax, ay = _pt(cx, cy, 48, angle(ascendant))
    dx, dy = _pt(cx, cy, 48, angle(ascendant + 180))
    out.append(f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{dx:.2f}" y2="{dy:.2f}" '
               'stroke="currentColor" stroke-width="0.6" opacity="0.8"/>')

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
        ring = [(50, 14), (74, 14), (86, 14), (86, 38), (86, 62), (86, 86),
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
