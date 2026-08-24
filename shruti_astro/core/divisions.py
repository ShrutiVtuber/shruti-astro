# SPDX-License-Identifier: AGPL-3.0-only
"""
Dividing the circle, without the boundary bug.

`int(longitude // (360/27))` looks obviously correct and is not. 360/27 is not
representable in binary and rounds *up*, so nine spans measure 120.00000000000001°
and a longitude of exactly 120° floors to the eighth nakṣatra instead of the
ninth. The affected points are the exact ingresses — 0° Leo, 0° Sagittarius —
which is exactly where a practitioner checks the software against an almanac.

Multiplying before dividing keeps the arithmetic exact for those cases:
`120 * 27 / 360` is 9.0 on the nose.
"""

from __future__ import annotations


def division_index(longitude: float, divisions: int, of_degrees: float = 360.0) -> int:
    """Which of `divisions` equal parts of `of_degrees` this longitude falls in."""
    x = longitude % of_degrees
    idx = int(x * divisions / of_degrees)
    # Guard the top edge against a longitude a hair under the wrap.
    return min(idx, divisions - 1)


def division_fraction(longitude: float, divisions: int, of_degrees: float = 360.0) -> float:
    """How far through its own division this longitude sits, 0..1."""
    x = longitude % of_degrees
    span = of_degrees / divisions
    return (x - division_index(longitude, divisions, of_degrees) * span) / span
