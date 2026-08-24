# SPDX-License-Identifier: AGPL-3.0-only
"""
Vedic (jyotiṣa) chart furniture: rāśi, nakṣatra with pāda, and the navāṁśa.

Two things a Western-built "sidereal mode" almost always omits, and without
which a chart is not usable by a Vedic astrologer at all:

  - **Rāhu and Ketu.** The lunar nodes are full participants, not optional
    points. Ketu is always exactly opposite Rāhu.
  - **The navāṁśa (D9).** The most consulted divisional chart in the tradition.
    Judging a chart without it is judging half of it.
"""

from __future__ import annotations

RASHIS = [
    "Meṣa", "Vṛṣabha", "Mithuna", "Karka", "Siṃha", "Kanyā",
    "Tulā", "Vṛścika", "Dhanu", "Makara", "Kumbha", "Mīna",
]

NAKSHATRAS = [
    "Aśvinī", "Bharaṇī", "Kṛttikā", "Rohiṇī", "Mṛgaśīrṣa", "Ārdrā", "Punarvasu",
    "Puṣya", "Āśleṣā", "Maghā", "Pūrva Phalgunī", "Uttara Phalgunī", "Hasta",
    "Citrā", "Svātī", "Viśākhā", "Anurādhā", "Jyeṣṭhā", "Mūla", "Pūrva Āṣāḍhā",
    "Uttara Āṣāḍhā", "Śravaṇa", "Dhaniṣṭhā", "Śatabhiṣā", "Pūrva Bhādrapadā",
    "Uttara Bhādrapadā", "Revatī",
]

# Vimśottarī lords, in order, aligned to the nakṣatras.
NAKSHATRA_LORDS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
] * 3

NAKSHATRA_SPAN = 360.0 / 27.0        # 13°20'
PADA_SPAN = NAKSHATRA_SPAN / 4.0     # 3°20'


def rashi(sidereal_longitude: float) -> dict:
    idx = int(sidereal_longitude % 360 // 30)
    return {
        "index": idx + 1,
        "name": RASHIS[idx],
        "degree": round((sidereal_longitude % 360) % 30, 4),
    }


def nakshatra_of(sidereal_longitude: float) -> dict:
    lon = sidereal_longitude % 360.0
    idx = int(lon // NAKSHATRA_SPAN)
    within = lon % NAKSHATRA_SPAN
    return {
        "index": idx + 1,
        "name": NAKSHATRAS[idx],
        "pada": int(within // PADA_SPAN) + 1,
        "lord": NAKSHATRA_LORDS[idx],
        "fraction": round(within / NAKSHATRA_SPAN, 6),
    }


def navamsa(sidereal_longitude: float) -> dict:
    """
    D9.

    The traditional rule is stated per modality — movable signs begin their
    navāṁśa from themselves, fixed from the ninth, dual from the fifth — but all
    three collapse into one expression: nine navāṁśas per sign, counted
    continuously from Aries. Both forms agree; this one cannot drift out of
    step with itself.
    """
    lon = sidereal_longitude % 360.0
    sign = int(lon // 30)
    part = int((lon % 30) // (30.0 / 9.0))
    idx = (sign * 9 + part) % 12
    return {"index": idx + 1, "name": RASHIS[idx]}


def ketu_from_rahu(rahu_longitude: float) -> float:
    """Ketu is the south node — always exactly opposite Rāhu."""
    return (rahu_longitude + 180.0) % 360.0
