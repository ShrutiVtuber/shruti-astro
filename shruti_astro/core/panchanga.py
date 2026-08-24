# SPDX-License-Identifier: AGPL-3.0-only
"""
Pañcāṅga — the five limbs: tithi, nakṣatra, yoga, karaṇa.

All five fall out of two sidereal longitudes, the Sun's and the Moon's. The
arithmetic is simple; the correctness lives in the ayanāṁśa and in being honest
that a limb is a *span*, not an instant — a tithi has a start and an end, and
naming only the one in force at noon is the error most pañcāṅga sites make.
"""

from __future__ import annotations

from dataclasses import dataclass

TITHI_NAMES = [
    "Pratipadā", "Dvitīyā", "Tṛtīyā", "Caturthī", "Pañcamī", "Ṣaṣṭhī", "Saptamī",
    "Aṣṭamī", "Navamī", "Daśamī", "Ekādaśī", "Dvādaśī", "Trayodaśī", "Caturdaśī",
]

NAKSHATRA_NAMES = [
    "Aśvinī", "Bharaṇī", "Kṛttikā", "Rohiṇī", "Mṛgaśīrṣa", "Ārdrā", "Punarvasu",
    "Puṣya", "Āśleṣā", "Maghā", "Pūrva Phalgunī", "Uttara Phalgunī", "Hasta",
    "Citrā", "Svātī", "Viśākhā", "Anurādhā", "Jyeṣṭhā", "Mūla", "Pūrva Āṣāḍhā",
    "Uttara Āṣāḍhā", "Śravaṇa", "Dhaniṣṭhā", "Śatabhiṣā", "Pūrva Bhādrapadā",
    "Uttara Bhādrapadā", "Revatī",
]

YOGA_NAMES = [
    "Viṣkambha", "Prīti", "Āyuṣmān", "Saubhāgya", "Śobhana", "Atigaṇḍa",
    "Sukarman", "Dhṛti", "Śūla", "Gaṇḍa", "Vṛddhi", "Dhruva", "Vyāghāta",
    "Harṣaṇa", "Vajra", "Siddhi", "Vyatīpāta", "Varīyān", "Parigha", "Śiva",
    "Siddha", "Sādhya", "Śubha", "Śukla", "Brahma", "Indra", "Vaidhṛti",
]

# Seven repeating movable karaṇas, then four fixed ones closing the cycle.
MOVABLE_KARANA = ["Bava", "Bālava", "Kaulava", "Taitila", "Gara", "Vaṇija", "Viṣṭi"]
FIXED_KARANA = ["Śakuni", "Catuṣpāda", "Nāga", "Kiṃstughna"]


@dataclass
class Limb:
    index: int          # 1-based, as traditionally counted
    name: str
    fraction: float     # 0..1 — how far through this limb we are


def tithi(sun_long: float, moon_long: float) -> Limb:
    """Tithi = each 12° the Moon gains on the Sun. 30 per lunation."""
    elong = (moon_long - sun_long) % 360.0
    idx = int(elong // 12.0)                    # 0..29
    frac = (elong % 12.0) / 12.0
    paksha = "Śukla" if idx < 15 else "Kṛṣṇa"
    within = idx % 15
    name = "Pūrṇimā" if idx == 14 else "Amāvāsyā" if idx == 29 else f"{paksha} {TITHI_NAMES[within]}"
    return Limb(index=idx + 1, name=name, fraction=frac)


def nakshatra(moon_sidereal_long: float) -> Limb:
    """27 equal segments of 13°20' of the sidereal zodiac."""
    span = 360.0 / 27.0
    idx = int((moon_sidereal_long % 360.0) // span)
    frac = ((moon_sidereal_long % 360.0) % span) / span
    return Limb(index=idx + 1, name=NAKSHATRA_NAMES[idx], fraction=frac)


def yoga(sun_sidereal_long: float, moon_sidereal_long: float) -> Limb:
    """Yoga = the sum of the two sidereal longitudes, in 27 segments."""
    span = 360.0 / 27.0
    total = (sun_sidereal_long + moon_sidereal_long) % 360.0
    idx = int(total // span)
    return Limb(index=idx + 1, name=YOGA_NAMES[idx], fraction=(total % span) / span)


def karana(sun_long: float, moon_long: float) -> Limb:
    """
    Karaṇa = half a tithi, 60 per lunation.

    The cycle is not uniform: Kiṃstughna opens the lunation, the seven movable
    karaṇas then repeat eight times, and three fixed karaṇas close it. Treating
    all sixty as `movable[i % 7]` is the usual bug.
    """
    elong = (moon_long - sun_long) % 360.0
    n = int(elong // 6.0)                        # 0..59
    frac = (elong % 6.0) / 6.0
    if n == 0:
        name = "Kiṃstughna"
    elif n >= 57:
        name = FIXED_KARANA[n - 57]
    else:
        name = MOVABLE_KARANA[(n - 1) % 7]
    return Limb(index=n + 1, name=name, fraction=frac)
