# SPDX-License-Identifier: AGPL-3.0-only
"""
Hellenistic judgment: sect, whole-sign places, essential dignities, the lots.

Contested points read the practitioner's Doctrine rather than hardcoding a
winner. Uncontested points are simply implemented.
"""

from __future__ import annotations

from dataclasses import dataclass

from shruti_astro.core.doctrine import DEFAULT, Doctrine

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

DOMICILE = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]

# (planet, sign index, degree). Saturn and Venus degrees come from Doctrine.
_EXALTATIONS = [
    ("Sun", 0, 19), ("Moon", 1, 3), ("Mercury", 5, 15),
    ("Venus", 11, None), ("Mars", 9, 28), ("Jupiter", 3, 15), ("Saturn", 6, None),
]

# Dorothean triplicity rulers: (day, night, participating), by element.
_TRIPLICITY = {
    "fire":  ("Sun", "Jupiter", "Saturn"),
    "earth": ("Venus", "Moon", "Mars"),
    "air":   ("Saturn", "Mercury", "Jupiter"),
    "water": ("Venus", "Mars", "Moon"),
}
_ELEMENTS = ["fire", "earth", "air", "water"] * 3

# Egyptian bounds: per sign, (ruler, cumulative end degree).
_BOUNDS = [
    [("Jupiter", 6), ("Venus", 12), ("Mercury", 20), ("Mars", 25), ("Saturn", 30)],
    [("Venus", 8), ("Mercury", 14), ("Jupiter", 22), ("Saturn", 27), ("Mars", 30)],
    [("Mercury", 6), ("Jupiter", 12), ("Venus", 17), ("Mars", 24), ("Saturn", 30)],
    [("Mars", 7), ("Venus", 13), ("Mercury", 19), ("Jupiter", 26), ("Saturn", 30)],
    [("Jupiter", 6), ("Venus", 11), ("Saturn", 18), ("Mercury", 24), ("Mars", 30)],
    [("Mercury", 7), ("Venus", 17), ("Jupiter", 21), ("Mars", 28), ("Saturn", 30)],
    [("Saturn", 6), ("Mercury", 14), ("Jupiter", 21), ("Venus", 28), ("Mars", 30)],
    [("Mars", 7), ("Venus", 11), ("Mercury", 19), ("Jupiter", 24), ("Saturn", 30)],
    [("Jupiter", 12), ("Venus", 17), ("Mercury", 21), ("Saturn", 26), ("Mars", 30)],
    [("Mercury", 7), ("Jupiter", 14), ("Venus", 22), ("Saturn", 26), ("Mars", 30)],
    [("Mercury", 7), ("Venus", 13), ("Jupiter", 20), ("Mars", 25), ("Saturn", 30)],
    [("Venus", 12), ("Jupiter", 16), ("Mercury", 19), ("Mars", 28), ("Saturn", 30)],
]

# Faces/decans run the Chaldean order continuously through all 36, beginning
# with Mars at 0° Aries.
_FACE_ORDER = ["Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter"]

PLACE_NAMES = [
    "Horoskopos", "Gate of Hades", "Goddess", "Subterranean", "Good Fortune",
    "Bad Fortune", "Descendant", "Idle Place", "God", "Midheaven",
    "Good Spirit", "Evil Spirit",
]


def sign_of(longitude: float) -> int:
    return int(longitude % 360 // 30)


def degree_in_sign(longitude: float) -> float:
    return (longitude % 360) % 30


@dataclass
class Sect:
    is_day: bool
    luminary: str          # the sect light
    benefic: str           # sect benefic
    malefic: str           # sect malefic (the one of the sect, i.e. less harmful)


def sect(sun_longitude: float, ascendant: float) -> Sect:
    """
    Sect by the **true degree rule**.

    The direction matters and is easy to get backwards. Signs rise in increasing
    zodiacal order, so a degree slightly *past* the ascending degree has not yet
    risen — it is in the first place, below the horizon. A degree slightly
    *before* it rose moments ago and stands in the twelfth, above the horizon.

    So the Sun is above the horizon when it lies in the arc running *backwards*
    from the ascendant: (Sun − ASC) mod 360 ∈ (180°, 360°), which is the twelfth
    through the seventh.

    Deliberately *not* derived from whole-sign house numbers. That approximation
    misjudges every chart where the Sun shares the rising sign but sits on the
    other side of the horizon degree, and it is retired in Theourgia too.
    """
    above = 180.0 < (sun_longitude - ascendant) % 360.0 < 360.0
    return (
        Sect(True, "Sun", "Jupiter", "Saturn") if above
        else Sect(False, "Moon", "Venus", "Mars")
    )


def whole_sign_places(ascendant: float) -> list[dict]:
    asc_sign = sign_of(ascendant)
    return [
        {
            "place": i + 1,
            "name": PLACE_NAMES[i],
            "sign": SIGNS[(asc_sign + i) % 12],
            "ruler": DOMICILE[(asc_sign + i) % 12],
        }
        for i in range(12)
    ]


def _exaltation_table(doc: Doctrine) -> list[tuple[str, int, int]]:
    out = []
    for planet, sign_idx, deg in _EXALTATIONS:
        if planet == "Saturn":
            deg = doc.saturn_exaltation_degree
        elif planet == "Venus":
            deg = doc.venus_exaltation_degree
        out.append((planet, sign_idx, deg))
    return out


def dignities(planet: str, longitude: float, is_day: bool, doc: Doctrine = DEFAULT) -> dict:
    """Essential dignities of one planet at one longitude."""
    s = sign_of(longitude)
    d = degree_in_sign(longitude)

    domicile = DOMICILE[s] == planet

    exaltation = False
    for p, sign_idx, deg in _exaltation_table(doc):
        if p != planet or sign_idx != s:
            continue
        # signLevel: anywhere in the sign exalts. degree: only the exact degree,
        # which is why the Saturn/Venus choice only bites in this mode.
        exaltation = True if doc.exaltation_degrees == "signLevel" else int(d) == deg
        break

    day_r, night_r, part_r = _TRIPLICITY[_ELEMENTS[s]]
    triplicity = planet in ((day_r, part_r) if is_day else (night_r, part_r))

    bound_ruler = next(r for r, end in _BOUNDS[s] if d < end)
    face_ruler = _FACE_ORDER[(s * 3 + int(d // 10)) % 7]

    return {
        "sign": SIGNS[s],
        "degree": round(d, 4),
        "domicile": domicile,
        "exaltation": exaltation,
        "triplicity": triplicity,
        "bound": bound_ruler,
        "inOwnBound": bound_ruler == planet,
        "face": face_ruler,
        "inOwnFace": face_ruler == planet,
        "detriment": DOMICILE[(s + 6) % 12] == planet,
        "fall": any(
            p == planet and (sign_idx + 6) % 12 == s for p, sign_idx, _ in _exaltation_table(doc)
        ),
    }


def lots(asc: float, positions: dict[str, float], is_day: bool) -> dict[str, float]:
    """
    The seven Hermetic lots, in Paulus's formulation.

    Every one of them reverses by sect. Computing Fortune the day way at night
    is the single most common error in Hellenistic software, and it silently
    poisons Spirit, Eros, Necessity, Courage, Victory and Nemesis with it.
    """
    sun, moon = positions["Sun"], positions["Moon"]

    def norm(x: float) -> float:
        return x % 360.0

    fortune = norm(asc + (moon - sun)) if is_day else norm(asc + (sun - moon))
    spirit = norm(asc + (sun - moon)) if is_day else norm(asc + (moon - sun))

    venus, mercury, mars, jupiter, saturn = (
        positions["Venus"], positions["Mercury"], positions["Mars"],
        positions["Jupiter"], positions["Saturn"],
    )

    return {
        "Fortune": fortune,
        "Spirit": spirit,
        "Eros": norm(asc + (venus - spirit)) if is_day else norm(asc + (spirit - venus)),
        "Necessity": norm(asc + (fortune - mercury)) if is_day else norm(asc + (mercury - fortune)),
        "Courage": norm(asc + (fortune - mars)) if is_day else norm(asc + (mars - fortune)),
        "Victory": norm(asc + (jupiter - spirit)) if is_day else norm(asc + (spirit - jupiter)),
        "Nemesis": norm(asc + (fortune - saturn)) if is_day else norm(asc + (saturn - fortune)),
    }
