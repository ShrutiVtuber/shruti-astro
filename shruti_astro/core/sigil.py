# SPDX-License-Identifier: AGPL-3.0-only
"""
Sigil construction by the letter-elimination method.

Statement of intent → upper case → letters only → vowels struck (or kept) →
repeats struck → the remaining letter set → a figure drawn through it.

**Every step is shown.** A sigil you cannot reconstruct is one you have to take
somebody else's word for, and taking somebody else's word for it is the one
thing the method exists to avoid.

Two properties the drawing must have:

  - **Deterministic.** The same statement yields the same figure, always. A
    sigil that changes between sittings cannot be returned to.
  - **The statement never travels with the image.** It is not written into the
    file, the metadata, or the path. The whole point of the method is that the
    intent becomes unreadable; a tool that quietly embeds it in an EXIF comment
    has undone the work.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

VOWELS = set("AEIOU")


@dataclass
class Step:
    label: str
    value: str
    note: str = ""


@dataclass
class Sigil:
    steps: list[Step]
    letters: str
    points: list[tuple[float, float]]
    path: str
    exhausted: bool = False
    exhausted_reason: str = ""
    options: dict = field(default_factory=dict)


def _letters_only(text: str) -> str:
    return "".join(ch for ch in text.upper() if ch.isalpha())


def _strike_repeats(text: str) -> str:
    seen: set[str] = set()
    out = []
    for ch in text:
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return "".join(out)


def _positions(letters: str, enclosure: str) -> list[tuple[float, float]]:
    """
    Letters onto a circle, in alphabetical order around the rim.

    Alphabetical placement — rather than hashing the letters to angles — keeps
    the figure legible as a construction: two statements sharing letters share
    vertices, which is visible and checkable. The hash is used only to rotate
    the whole figure, so the shape stays a function of the letters alone.
    """
    if not letters:
        return []

    # Deterministic rotation from the letter set, not from the statement.
    seed = int(hashlib.sha256(letters.encode()).hexdigest()[:8], 16)
    rotation = (seed % 3600) / 10.0

    radius = 46.0 if enclosure != "none" else 48.0
    pts = []
    for ch in letters:
        # A..Z onto 0..360.
        angle = math.radians((ord(ch) - 65) * (360.0 / 26.0) + rotation - 90.0)
        pts.append((50.0 + radius * math.cos(angle), 50.0 + radius * math.sin(angle)))
    return pts


def _path_from(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    d = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    for x, y in points[1:]:
        d.append(f"L {x:.2f} {y:.2f}")
    return " ".join(d)


def build(
    statement: str,
    keep_vowels: bool = False,
    enclosure: str = "circle",
    line_weight: str = "hairline",
) -> Sigil:
    """
    Construct the figure, showing the reduction.

    Cannot-compute: the reduction can consume the sentence entirely — a
    statement of all vowels, or one whose consonants all repeat. That is
    reported with what to do about it, not silently drawn as an empty circle.
    """
    if enclosure not in ("none", "circle", "vesica"):
        raise ValueError("enclosure must be none, circle or vesica")
    if line_weight not in ("hairline", "broad", "engraved"):
        raise ValueError("line_weight must be hairline, broad or engraved")

    steps = [Step("Statement of intent", statement)]

    upper = statement.upper()
    steps.append(Step("Upper case", upper))

    alpha = _letters_only(upper)
    steps.append(Step("Letters only", alpha, "punctuation and spaces struck"))

    if keep_vowels:
        devowelled = alpha
        steps.append(Step("Vowels", alpha, "kept, by request"))
    else:
        devowelled = "".join(ch for ch in alpha if ch not in VOWELS)
        struck = "".join(ch for ch in alpha if ch in VOWELS)
        steps.append(Step("Vowels struck", devowelled, f"removed: {struck or '—'}"))

    letters = _strike_repeats(devowelled)
    repeats = len(devowelled) - len(letters)
    steps.append(Step("Repeats struck", letters, f"{repeats} repeated letter(s) removed"))

    # Alphabetical, so the figure is a function of the SET, not the order —
    # which is what makes the same intent phrased differently draw the same.
    ordered = "".join(sorted(letters))
    steps.append(Step("Letter set", ordered, "alphabetical; the figure is drawn through these"))

    exhausted = len(ordered) < 2
    reason = ""
    if exhausted:
        reason = (
            "The reduction consumed the statement — fewer than two letters remain, "
            "so there is no figure to draw. Keep the vowels, write a longer "
            "statement, or draw it by hand: the tool is a convenience, never a "
            "requirement."
        )

    points = _positions(ordered, enclosure)
    return Sigil(
        steps=steps, letters=ordered, points=points,
        path=_path_from(points), exhausted=exhausted, exhausted_reason=reason,
        options={"keepVowels": keep_vowels, "enclosure": enclosure,
                 "lineWeight": line_weight},
    )


STROKE = {"hairline": 0.6, "broad": 2.4, "engraved": 1.4}


def to_svg(sigil: Sigil) -> str:
    """
    A standalone SVG.

    Carries no title, no description and no metadata — the statement must not
    travel with the image.
    """
    if sigil.exhausted:
        raise ValueError(sigil.exhausted_reason)

    w = STROKE[sigil.options["lineWeight"]]
    enclosure = sigil.options["enclosure"]

    shapes = []
    if enclosure == "circle":
        shapes.append(f'<circle cx="50" cy="50" r="48" fill="none" '
                      f'stroke="currentColor" stroke-width="{w}"/>')
    elif enclosure == "vesica":
        shapes.append(f'<circle cx="38" cy="50" r="34" fill="none" '
                      f'stroke="currentColor" stroke-width="{w}"/>')
        shapes.append(f'<circle cx="62" cy="50" r="34" fill="none" '
                      f'stroke="currentColor" stroke-width="{w}"/>')

    shapes.append(
        f'<path d="{sigil.path}" fill="none" stroke="currentColor" '
        f'stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    # A mark at the first vertex, so the figure has a starting point.
    if sigil.points:
        x, y = sigil.points[0]
        shapes.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{w * 1.6:.2f}" '
                      f'fill="currentColor"/>')

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
        f'width="512" height="512" role="img">{"".join(shapes)}</svg>'
    )
