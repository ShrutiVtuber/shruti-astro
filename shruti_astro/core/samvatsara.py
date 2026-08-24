# SPDX-License-Identifier: AGPL-3.0-only
"""
The sixty-year Jovian cycle, and the era reckonings that sit beside it.

Sixty names, one per year, running on Jupiter's roughly twelve-year circuit
five times over. Which name a given year carries depends on the region — the
southern lunisolar reckoning and the northern Jovian one drift apart — and this
implements the southern, which is the one printed in most pañcāṅgas.
"""

from __future__ import annotations

SAMVATSARAS = [
    "Prabhava", "Vibhava", "Śukla", "Pramoda", "Prajāpati", "Āṅgirasa",
    "Śrīmukha", "Bhāva", "Yuvan", "Dhātṛ", "Īśvara", "Bahudhānya",
    "Pramāthin", "Vikrama", "Vṛṣa", "Citrabhānu", "Subhānu", "Tāraṇa",
    "Pārthiva", "Vyaya", "Sarvajit", "Sarvadhārin", "Virodhin", "Vikṛta",
    "Khara", "Nandana", "Vijaya", "Jaya", "Manmatha", "Durmukha",
    "Hemalamba", "Vilamba", "Vikārin", "Śārvarī", "Plava", "Śubhakṛt",
    "Śobhana", "Krodhin", "Viśvāvasu", "Parābhava", "Plavaṅga", "Kīlaka",
    "Saumya", "Sādhāraṇa", "Virodhakṛt", "Paridhāvin", "Pramādin", "Ānanda",
    "Rākṣasa", "Anala", "Piṅgala", "Kālayukta", "Siddhārthin", "Raudra",
    "Durmati", "Dundubhi", "Rudhirodgārin", "Raktākṣa", "Krodhana", "Akṣaya",
]
assert len(SAMVATSARAS) == 60


def samvatsara(shaka_year: int) -> dict:
    """
    The saṃvatsara for a Śaka year, southern reckoning.

    Anchored on Śaka 1948 = Parābhava (2026–27 CE), which is the year printed in
    current almanacs. The northern Jovian reckoning runs ahead of this by a
    varying amount because it counts actual Jovian transits rather than years,
    and is deliberately not offered here rather than being silently conflated.
    """
    index = (shaka_year + 12) % 60          # 1-based; 0 means the sixtieth
    ordinal = index if index else 60
    return {"index": ordinal, "name": SAMVATSARAS[ordinal - 1], "reckoning": "southern"}


# ── era reckonings ──────────────────────────────────────────────────────────

def bengali_san(gregorian_year: int, after_pohela_boishakh: bool) -> int:
    """
    Bengali San. The year turns at Pohela Boishakh, mid-April — not 1 January,
    so the offset depends on where in the Gregorian year you stand.
    """
    return gregorian_year - 593 if after_pohela_boishakh else gregorian_year - 594


def eras(gregorian_year: int, sun_rashi: int) -> dict:
    """
    Every era named together, with the Bengali turn handled.

    `sun_rashi` decides whether Pohela Boishakh has passed: the Bengali year
    turns when the Sun enters Meṣa, so rāśi 0 onward is the new year.
    """
    shaka = gregorian_year - 78
    return {
        "vikrama": gregorian_year + 57,
        "shaka": shaka,
        "kali": gregorian_year + 3101,
        "bengali": bengali_san(gregorian_year, after_pohela_boishakh=sun_rashi >= 0
                               and sun_rashi < 9),
        "samvatsara": samvatsara(shaka),
    }
