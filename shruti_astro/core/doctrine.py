# SPDX-License-Identifier: AGPL-3.0-only
"""
Contested doctrine, as the practitioner decides it.

Sophia's governing ruling, recorded in Theourgia:

    where the tradition genuinely holds two opinions the practitioner chooses;
    where it holds one, we implement the one.

Field names and enum values deliberately mirror Theourgia's `astro.doctrine`
setting so the two systems speak the same vocabulary. **No code is shared** —
Theourgia runs under a commercial Swiss Ephemeris licence and this daemon under
the AGPL arm, so the decisions travel and the implementation does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class DoctrineError(ValueError):
    pass


# Attested variants only. 19 for Saturn is an OCR artefact in the literature and
# must never be storable — Theourgia rejects it and so does this.
SATURN_EXALTATION_DEGREES = (21, 20)
VENUS_EXALTATION_DEGREES = (27, 26)

SOLAR_PHASE = ("paulus", "lilly1647", "medievalUnattributed")
PREDOMINATOR = (
    "valensWholeSign", "porphyry", "dorotheus", "valensQuadrant", "ptolemy", "paulus",
)
EXALTATION_MODE = ("signLevel", "degree")
VOID_OF_COURSE = ("thirtyDegrees", "signExit")


@dataclass(frozen=True)
class Doctrine:
    """Defaults are Sophia's defaults, not arbitrary ones."""

    solar_phase: str = "paulus"
    predominator: str = "valensWholeSign"
    exaltation_degrees: str = "signLevel"
    saturn_exaltation_degree: int = 21
    venus_exaltation_degree: int = 27
    maltreatment_contested_sextile: bool = True
    # kenodromia: no exact configuration perfecting within the Moon's next
    # thirty degrees of travel, sign boundaries crossed. `signExit` is the
    # later rule that stops at the sign's edge.
    void_of_course: str = "thirtyDegrees"

    def __post_init__(self) -> None:
        def check(name: str, value, allowed) -> None:
            if value not in allowed:
                raise DoctrineError(f"{name}={value!r} is not attested; choose from {allowed}")

        check("solar_phase", self.solar_phase, SOLAR_PHASE)
        check("predominator", self.predominator, PREDOMINATOR)
        check("exaltation_degrees", self.exaltation_degrees, EXALTATION_MODE)
        check("void_of_course", self.void_of_course, VOID_OF_COURSE)
        check("saturn_exaltation_degree", self.saturn_exaltation_degree, SATURN_EXALTATION_DEGREES)
        check("venus_exaltation_degree", self.venus_exaltation_degree, VENUS_EXALTATION_DEGREES)


DEFAULT = Doctrine()
