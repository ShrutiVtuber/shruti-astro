# SPDX-License-Identifier: AGPL-3.0-only
"""
Void of course — kenodromia.

Two rules, and they were misnamed in an earlier pass, which is worth recording
because the names are the whole distinction:

  - **thirtyDegrees** — the Hellenistic rule. The Moon is void when no exact
    configuration perfects within her next **thirty degrees of travel**, sign
    boundaries crossed freely. This is *kenodromia*, "running empty".
  - **signExit** — the later rule. The Moon is void when she completes no more
    exact aspects **before leaving her present sign**.

They disagree often, and they disagree in both directions: the Moon can be void
by one rule and busy by the other. Neither is a refinement of the other.
"""

from __future__ import annotations

import swisseph as swe

from shruti_astro.core.ephemeris import _ensure_init, _flags, _julday

RULES = ("thirtyDegrees", "signExit")

# The classical configurations. Aversion is not an aspect.
ASPECT_ANGLES = (0.0, 60.0, 90.0, 120.0, 180.0)

CLASSICAL_BODIES = (swe.SUN, swe.MERCURY, swe.VENUS, swe.MARS,
                    swe.JUPITER, swe.SATURN)


def is_void_of_course(moment, rule: str = "thirtyDegrees") -> dict:
    """
    Whether the Moon is void, under the chosen rule.

    Walks the Moon forward in small steps and watches for an aspect angle being
    crossed exactly — an aspect that is already separating does not count, since
    perfection is what matters, not proximity.
    """
    if rule not in RULES:
        raise ValueError(f"rule must be one of {RULES}")

    _ensure_init()
    jd = _julday(moment)
    f = _flags()

    moon0 = swe.calc_ut(jd, swe.MOON, f)[0][0] % 360.0
    limit_deg = 30.0 if rule == "thirtyDegrees" else (30.0 - (moon0 % 30.0))

    def separations(j: float) -> dict[int, float]:
        moon = swe.calc_ut(j, swe.MOON, f)[0][0]
        out = {}
        for body in CLASSICAL_BODIES:
            lon = swe.calc_ut(j, body, f)[0][0]
            out[body] = ((moon - lon + 180.0) % 360.0) - 180.0
        return out

    # The Moon covers ~13.2°/day; step in hours and watch for a crossing.
    steps = max(4, int(limit_deg / 13.2 * 24 * 4))
    step_days = (limit_deg / 13.2) / steps

    prev = separations(jd)
    perfections: list[dict] = []
    for i in range(1, steps + 1):
        j = jd + step_days * i
        cur = separations(j)
        for body, sep in cur.items():
            for angle in ASPECT_ANGLES:
                for target in ({angle, -angle} if angle else {0.0}):
                    a, b = prev[body] - target, sep - target
                    if a == 0 or (a < 0) != (b < 0):
                        if abs(a - b) < 180.0:
                            perfections.append({
                                "body": int(body),
                                "aspect": angle,
                                "withinDegrees": round(13.2 * step_days * i, 3),
                            })
        prev = cur

    return {
        "rule": rule,
        "void": not perfections,
        "searchedDegrees": round(limit_deg, 4),
        "perfections": perfections[:6],
        "note": (
            "kenodromia: no exact configuration within the Moon's next thirty "
            "degrees, sign boundaries crossed"
            if rule == "thirtyDegrees" else
            "no exact configuration before the Moon leaves her present sign"
        ),
    }
