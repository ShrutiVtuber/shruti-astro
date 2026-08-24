# SPDX-License-Identifier: AGPL-3.0-only
"""
Solar phase — cazimi, combustion, under the beams.

A planet near the Sun is variously destroyed, hidden or enthroned depending on
how near, and **the boundaries are genuinely contested**. Paulus is not Lilly,
and neither is the anonymous medieval set. The practitioner chooses; the
software does not get to pick a "standard".

The three states, from nearest out:

  - **Cazimi** — in the heart of the Sun. The strongest condition there is.
  - **Combust** — burned. The worst.
  - **Under the beams** — hidden, but not destroyed.

Whether the distance is measured in longitude alone or in the true body-to-body
separation is itself a doctrinal question; longitude is used here, which is the
usual reading, and stated so rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

# (cazimi, combust, under_beams) in degrees of longitude.
BOUNDARIES = {
    # Paulus Alexandrinus: 1° cazimi, 7° combust, 15° under the beams.
    "paulus": (1.0, 7.0, 15.0),
    # Lilly, Christian Astrology (1647): 17 arcminutes cazimi, 8°30' combust,
    # 17° under the beams.
    "lilly1647": (17.0 / 60.0, 8.5, 17.0),
    # The medieval set that circulates without clear attribution. Kept because
    # it is widely used, labelled because its source is not established.
    "medievalUnattributed": (0.5, 6.0, 12.0),
}

DESCRIPTIONS = {
    "paulus": "Paulus Alexandrinus, 4th c. — 1° / 7° / 15°",
    "lilly1647": "Lilly, Christian Astrology 1647 — 17′ / 8°30′ / 17°",
    "medievalUnattributed": "medieval, unattributed — 0°30′ / 6° / 12°",
}


@dataclass
class SolarPhase:
    state: str                 # cazimi | combust | under_beams | free
    separation: float
    doctrine: str
    boundaries: dict


def solar_phase(planet_longitude: float, sun_longitude: float,
                doctrine: str = "paulus") -> SolarPhase:
    if doctrine not in BOUNDARIES:
        raise ValueError(f"unknown solar phase doctrine: {doctrine}")

    cazimi, combust, beams = BOUNDARIES[doctrine]
    sep = abs(((planet_longitude - sun_longitude + 180.0) % 360.0) - 180.0)

    if sep <= cazimi:
        state = "cazimi"
    elif sep <= combust:
        state = "combust"
    elif sep <= beams:
        state = "under_beams"
    else:
        state = "free"

    return SolarPhase(
        state=state, separation=round(sep, 6), doctrine=doctrine,
        boundaries={"cazimi": cazimi, "combust": combust, "underBeams": beams},
    )
