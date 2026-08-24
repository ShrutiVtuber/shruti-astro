# SPDX-License-Identifier: AGPL-3.0-only
"""
Aspects — and the two traditions do not mean the same thing by the word.

**Both are classically counted in whole signs, not orbs.** Modern Western
practice measures degrees and allows an orb; neither Hellenistic nor jyotiṣa
does that natively. Implementing orb-based aspects and calling the result
"Hellenistic" is the single most common way a Western-built engine gets a
traditional chart wrong — planets in aspect by sign but 11° apart are *in
aspect*, and planets 3° apart across a sign boundary are *not*.

Degree-based aspects are offered too, because they are genuinely useful for
judging application and separation. They are a refinement layered on the
sign-based configuration, never a replacement for it.

**Vedic dṛṣṭi is asymmetric.** Every graha aspects the 7th from itself, and
Mars, Jupiter and Saturn have additional special aspects that are *not*
reciprocated. Saturn aspects the 3rd from itself; the planet in that 3rd does
not aspect Saturn back. Symmetric aspect code cannot express this.
"""

from __future__ import annotations

from dataclasses import dataclass

PTOLEMAIC = {
    0: ("conjunction", 0),
    1: ("semisextile", 30),      # not a Ptolemaic configuration; see below
    2: ("sextile", 60),
    3: ("square", 90),
    4: ("trine", 120),
    5: ("quincunx", 150),        # likewise
    6: ("opposition", 180),
}

# The five configurations the tradition actually recognises. Signs 1, 5, 7 and
# 11 places apart are "aversion" — they do not behold each other at all, which
# is a positive statement in Hellenistic doctrine, not an absence of data.
CLASSICAL_SEPARATIONS = {0, 2, 3, 4, 6}

# Special dṛṣṭi, as counted-from-self house numbers (1 = own sign).
SPECIAL_DRISHTI = {
    "Mars": (4, 7, 8),
    "Jupiter": (5, 7, 9),
    "Saturn": (3, 7, 10),
}
DEFAULT_DRISHTI = (7,)
# Some schools give the nodes Jupiter-like aspects. Off by default: it is a
# school-dependent claim, not a settled one.
NODE_DRISHTI = (5, 7, 9)


@dataclass
class Aspect:
    from_body: str
    to_body: str
    name: str
    exact_degrees: int
    separation_signs: int
    orb: float | None = None
    applying: bool | None = None
    mutual: bool = True


def _sign(longitude: float) -> int:
    return int(longitude % 360 // 30)


def whole_sign_aspects(positions: dict[str, float]) -> list[Aspect]:
    """
    Hellenistic configuration by sign — the tradition's own definition.

    Two bodies are configured if their *signs* are 0, 2, 3, 4 or 6 apart.
    Degrees are irrelevant to whether the aspect exists.
    """
    names = list(positions)
    out: list[Aspect] = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            sep = abs(_sign(positions[a]) - _sign(positions[b]))
            sep = min(sep, 12 - sep)
            if sep not in CLASSICAL_SEPARATIONS:
                continue
            name, exact = PTOLEMAIC[sep]
            out.append(
                Aspect(from_body=a, to_body=b, name=name,
                       exact_degrees=exact, separation_signs=sep)
            )
    return out


def degree_aspects(
    positions: dict[str, float], speeds: dict[str, float] | None = None, orb: float = 8.0
) -> list[Aspect]:
    """
    Degree-based configurations with an orb, for judging application.

    A refinement over the sign-based configuration, not a substitute. `applying`
    means the faster body is still closing on exactness.
    """
    names = list(positions)
    speeds = speeds or {}
    out: list[Aspect] = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            # Signed separation folded to (-180, 180], so its sign tells us
            # which way the gap runs; the magnitude is the separation itself.
            signed = ((positions[b] - positions[a] + 180.0) % 360.0) - 180.0
            diff = abs(signed)

            for sep, (name, exact) in PTOLEMAIC.items():
                if sep not in CLASSICAL_SEPARATIONS:
                    continue
                delta = diff - exact
                if abs(delta) > orb:
                    continue

                applying = None
                if a in speeds and b in speeds:
                    # How fast the separation itself is changing. The gap runs
                    # b − a, so it grows at (speed_b − speed_a); whether the
                    # *separation* grows depends on which side of a the b body
                    # sits, hence the sign of `signed`.
                    d_separation = (1.0 if signed >= 0 else -1.0) * (speeds[b] - speeds[a])
                    # Applying means moving toward exactness: a narrow aspect
                    # must widen, a wide one must narrow.
                    applying = d_separation > 0 if delta < 0 else d_separation < 0
                out.append(
                    Aspect(from_body=a, to_body=b, name=name, exact_degrees=exact,
                           separation_signs=abs(_sign(positions[a]) - _sign(positions[b])),
                           orb=round(abs(delta), 4), applying=applying)
                )
                break
    return out


def graha_drishti(positions: dict[str, float], node_aspects: bool = False) -> list[Aspect]:
    """
    Vedic dṛṣṭi, counted in whole signs from the aspecting graha.

    Asymmetric by design: `mutual=False` marks a special aspect that is not
    returned. Saturn in Aries aspects Gemini (the 3rd); a planet in Gemini does
    not aspect Saturn back unless it has its own aspect reaching there.
    """
    out: list[Aspect] = []
    for a, a_lon in positions.items():
        if a in ("Rahu", "Ketu"):
            houses = NODE_DRISHTI if node_aspects else ()
        else:
            houses = SPECIAL_DRISHTI.get(a, DEFAULT_DRISHTI)

        for h in houses:
            target_sign = (_sign(a_lon) + h - 1) % 12
            for b, b_lon in positions.items():
                if b == a or _sign(b_lon) != target_sign:
                    continue
                out.append(
                    Aspect(from_body=a, to_body=b, name=f"{h}th-house dṛṣṭi",
                           exact_degrees=(h - 1) * 30, separation_signs=h - 1,
                           mutual=(h == 7))
                )
    return out
