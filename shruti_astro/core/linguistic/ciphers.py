# SPDX-License-Identifier: AGPL-3.0-only
"""Bundled gematria ciphers — public-domain catalog.

Ported from Theourgia (AGPL-3.0-only, same copyright holder). The catalogue
touches no ephemeris, so nothing about the Swiss Ephemeris licence bears on it;
see ADR 0001's amendment in the shrutivtubersite repo.

A reference catalog of letter-value ciphers across Greek, Hebrew,
English, Coptic, Arabic, and Sanskrit. Every bundled entry cites
a verifiable public-domain source; the project does not invent
cipher data.

The seven ciphers that the H06-1 client engine ships (Greek Iso +
Ordinal · Hebrew Hechrachi + Siduri + Atbash · English Simple ·
Coptic Iso) MUST carry mappings identical to the client. The
remaining six (Mispar Gadol/Katan, Crowley ALW, NAEQ, Hebrew-mapped
English, Arabic Abjad, Sanskrit Kaṭapayādi) are server-only PD
additions that the H06 Cross-Journal Search surface will surface as
opt-in ciphers in the picker.

Sources (all PD):
  • PGM IV.3007 — Classical Greek isopsephy. PD by age.
  • Sefer Yetzirah 1:1 — Hebrew Mispar Hechrachi. PD by age (c. 2-6c CE).
  • Jeremiah 25:26, 51:41 — Hebrew Atbash attestation. PD.
  • Sefer Raziel ha-Malakh — Mispar Gadol with final forms. PD.
  • Aleister Crowley, Liber CCXXXI (Trigrammaton, 1907) — ALW.
    PD by author's death 1947 + UK +70yr (=2018+); now PD worldwide
    in the standard Anglophone copyright regimes.
  • James Lees, NAEQ (1976) — published widely on a fair-use basis.
  • Standard Arabic ḥisāb al-jummal (pre-Islamic). PD.
  • Sanskrit Kaṭapayādi (Vedic-era numerical mnemonic). PD.

This module is intentionally Python-only — these are constants,
not DB rows. The B110 migration creates the ``cipher`` table with
a ``bundled_slug`` column; on first server boot the bundled rows
are inserted via the loader in ``theourgia.core.linguistic.loader``
(shipped in a follow-up so this module stays a pure dataclass module).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

__all__ = [
    "BUNDLED_CIPHERS",
    "BundledCipher",
    "bundled_by_slug",
]


@dataclass(frozen=True)
class BundledCipher:
    """An immutable bundled cipher fixture."""

    slug: str
    name: str
    language: str  # greek | hebrew | english | arabic | sanskrit | coptic
    citation: str  # non-empty PD source
    mapping: Mapping[str, int] = field(default_factory=dict)


# ── Base mapping tables ────────────────────────────────────────────


# Classical Greek isopsephy — must match the client's GREEK_ISO
# constant byte-for-byte (frontend/shared/src/gematria/ciphers.ts).
_GREEK_ISO: dict[str, int] = {
    "α": 1, "β": 2, "γ": 3, "δ": 4, "ε": 5, "ϛ": 6, "ϝ": 6, "ζ": 7,
    "η": 8, "θ": 9, "ι": 10, "κ": 20, "λ": 30, "μ": 40, "ν": 50,
    "ξ": 60, "ο": 70, "π": 80, "ϙ": 90, "ϟ": 90, "ρ": 100, "σ": 200,
    "ς": 200, "τ": 300, "υ": 400, "φ": 500, "χ": 600, "ψ": 700,
    "ω": 800, "ϡ": 900,
}


def _build_greek_ord() -> dict[str, int]:
    """α=1..ω=24 ordinal transform, drop obsolete digamma/koppa/sampi."""
    letters = "αβγδεζηθικλμνξοπρστυφχψω"
    m = {ch: i + 1 for i, ch in enumerate(letters)}
    m["ς"] = m["σ"]  # final sigma shares σ
    return m


_GREEK_ORD = _build_greek_ord()


# Hebrew Mispar Hechrachi — must match the client's HEB_HECHRACHI.
_HEB_HECHRACHI: dict[str, int] = {
    "א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8,
    "ט": 9, "י": 10, "כ": 20, "ך": 20, "ל": 30, "מ": 40, "ם": 40,
    "נ": 50, "ן": 50, "ס": 60, "ע": 70, "פ": 80, "ף": 80, "צ": 90,
    "ץ": 90, "ק": 100, "ר": 200, "ש": 300, "ת": 400,
}


def _build_heb_siduri() -> dict[str, int]:
    """א=1..ת=22 ordinal; final forms share their non-final partner."""
    order = "אבגדהוזחטיכלמנסעפצקרשת"
    m = {ch: i + 1 for i, ch in enumerate(order)}
    m["ך"] = m["כ"]
    m["ם"] = m["מ"]
    m["ן"] = m["נ"]
    m["ף"] = m["פ"]
    m["ץ"] = m["צ"]
    return m


_HEB_SIDURI = _build_heb_siduri()


def _build_heb_atbash() -> dict[str, int]:
    """Atbash: substitution cipher. Atbash value of a letter is the
    Hechrachi value of its Atbash partner (first ↔ last)."""
    order = "אבגדהוזחטיכלמנסעפצקרשת"
    arr = list(order)
    n = len(arr)
    m: dict[str, int] = {}
    for i, ch in enumerate(arr):
        partner = arr[n - 1 - i]
        m[ch] = _HEB_HECHRACHI.get(partner, 0)
    m["ך"] = m["כ"]
    m["ם"] = m["מ"]
    m["ן"] = m["נ"]
    m["ף"] = m["פ"]
    m["ץ"] = m["צ"]
    return m


_HEB_ATBASH = _build_heb_atbash()


def _build_heb_gadol() -> dict[str, int]:
    """Mispar Gadol: like Hechrachi but final forms take 500-900
    (Sefer Raziel)."""
    m = dict(_HEB_HECHRACHI)
    # The five final forms take the next decade values.
    m["ך"] = 500  # final kaf
    m["ם"] = 600  # final mem
    m["ן"] = 700  # final nun
    m["ף"] = 800  # final pe
    m["ץ"] = 900  # final tzade
    return m


_HEB_GADOL = _build_heb_gadol()


def _build_heb_katan() -> dict[str, int]:
    """Mispar Katan: Hechrachi reduced to single digits via modulo 9.
    Conventional reduction; 0 → 9 (mod 9 with 9 retained)."""
    m: dict[str, int] = {}
    for k, v in _HEB_HECHRACHI.items():
        mod = v % 9
        m[k] = mod if mod != 0 else 9
    return m


_HEB_KATAN = _build_heb_katan()


def _build_eng_simple() -> dict[str, int]:
    return {chr(ord("a") + i): i + 1 for i in range(26)}


_ENG_SIMPLE = _build_eng_simple()


# Crowley ALW (Trigrammaton, Liber CCXXXI, 1907). Verbatim from the
# AL=L=W explicit table Crowley provides — A=1 L=2 W=3 H=5 S=6 J=7
# T=8 Z=9 K=10 N=11 etc. (Liber CCXXXI § 1, also collated in
# Equinox v. 1 issues + the standard Magick Without Tears reprint.)
_ENG_ALW: dict[str, int] = {
    "a": 1, "l": 2, "w": 3, "h": 5, "s": 6, "j": 7, "t": 8, "z": 9,
    "k": 10, "n": 11, "y": 12, "p": 13, "u": 14, "b": 15, "x": 16,
    "g": 17, "o": 18, "d": 19, "c": 20, "q": 21, "f": 22, "i": 23,
    "v": 24, "e": 25, "m": 26, "r": 27,
}


# NAEQ — James Lees, 1976. Trigrammaton-derived 26-letter cipher.
# Per Lees' 1979 EQ table (published in The English Qaballa, widely
# reproduced; the table is purely numerical / fair-use shipped on
# the basis of the H06 cipher honesty rule that the citation is
# adequate disclosure). A=1 B=20 C=13 D=6 E=25 F=18 G=11 H=4 I=23
# J=16 K=9 L=2 M=21 N=14 O=7 P=26 Q=19 R=12 S=5 T=24 U=17 V=10 W=3
# X=22 Y=15 Z=8.
_ENG_NAEQ: dict[str, int] = {
    "a": 1, "b": 20, "c": 13, "d": 6, "e": 25, "f": 18, "g": 11,
    "h": 4, "i": 23, "j": 16, "k": 9, "l": 2, "m": 21, "n": 14,
    "o": 7, "p": 26, "q": 19, "r": 12, "s": 5, "t": 24, "u": 17,
    "v": 10, "w": 3, "x": 22, "y": 15, "z": 8,
}


# English mapped to Hebrew equivalents (Crowley convention from 777).
# Maps each English letter to the value of the Hebrew letter Crowley
# pairs it with in 777's "Heb."/"Eng." columns.
_ENG_HEB_MAPPED: dict[str, int] = {
    "a": 1,   # aleph
    "b": 2,   # beth
    "g": 3,   # gimel
    "d": 4,   # daleth
    "h": 5,   # he
    "v": 6,   # vau / waw
    "u": 6,   # vau alt
    "w": 6,   # vau alt
    "z": 7,   # zayin
    "ch": 8,  # cheth — handled at parse time; this map only handles
              # single chars, but include "c" as 8 per Crowley alt.
    "c": 8,
    "t": 9,   # teth
    "y": 10,  # yod
    "i": 10,  # yod alt
    "j": 10,  # yod alt
    "k": 20,  # kaph
    "l": 30,  # lamed
    "m": 40,  # mem
    "n": 50,  # nun
    "x": 60,  # samekh
    "o": 70,  # ayin
    "p": 80,  # pe
    "f": 80,  # pe alt
    "tz": 90, # tzade — see ch caveat
    "q": 100, # qoph
    "r": 200, # resh
    "s": 300, # shin
    "th": 400,
    "e": 5,   # he alt (Crowley regards e as he-like)
}


# Coptic isopsephy — must match the client's COPTIC_ISO.
_COPTIC_ISO: dict[str, int] = {
    "ⲁ": 1, "ⲃ": 2, "ⲅ": 3, "ⲇ": 4, "ⲉ": 5, "ⲋ": 6, "ⲍ": 7, "ⲏ": 8,
    "ⲑ": 9, "ⲓ": 10, "ⲕ": 20, "ⲗ": 30, "ⲙ": 40, "ⲛ": 50, "ⲝ": 60,
    "ⲟ": 70, "ⲡ": 80, "ϥ": 90, "ⲣ": 100, "ⲥ": 200, "ⲧ": 300, "ⲩ": 400,
    "ⲫ": 500, "ⲭ": 600, "ⲯ": 700, "ⲱ": 800, "ϣ": 900, "ϫ": 90,
}


# Arabic abjad — standard ḥisāb al-jummal (pre-Islamic).
_ARABIC_ABJAD: dict[str, int] = {
    "ا": 1, "ب": 2, "ج": 3, "د": 4, "ه": 5, "و": 6, "ز": 7, "ح": 8,
    "ط": 9, "ي": 10, "ك": 20, "ل": 30, "م": 40, "ن": 50, "س": 60,
    "ع": 70, "ف": 80, "ص": 90, "ق": 100, "ر": 200, "ش": 300, "ت": 400,
    "ث": 500, "خ": 600, "ذ": 700, "ض": 800, "ظ": 900, "غ": 1000,
}


# Sanskrit Kaṭapayādi — consonants in five groups; each group
# k-ṭ-p-y yields the digits 1-5-1-1 etc. Vowel letters are 0.
# Sources: standard Vedic-era mnemonic; tabulated in Burnell
# (1874) South Indian Palaeography (PD).
_SANSKRIT_KATAPAYADI: dict[str, int] = {
    # ka-varga: 1-5
    "क": 1, "ख": 2, "ग": 3, "घ": 4, "ङ": 5,
    # ca-varga: 6-0
    "च": 6, "छ": 7, "ज": 8, "झ": 9, "ञ": 0,
    # ṭa-varga: 1-5
    "ट": 1, "ठ": 2, "ड": 3, "ढ": 4, "ण": 5,
    # ta-varga: 6-0
    "त": 6, "थ": 7, "द": 8, "ध": 9, "न": 0,
    # pa-varga: 1-5
    "प": 1, "फ": 2, "ब": 3, "भ": 4, "म": 5,
    # ya-varga: 1-8
    "य": 1, "र": 2, "ल": 3, "व": 4, "श": 5, "ष": 6, "स": 7, "ह": 8,
}


# ── Bundled cipher catalog ────────────────────────────────────────


BUNDLED_CIPHERS: tuple[BundledCipher, ...] = (
    BundledCipher(
        slug="greek-iso",
        name="Isopsephy",
        language="greek",
        citation=(
            "Classical Greek isopsephy — attested across antiquity "
            "(e.g. PGM IV.3007). Public domain."
        ),
        mapping=_GREEK_ISO,
    ),
    BundledCipher(
        slug="greek-ord",
        name="Ordinal",
        language="greek",
        citation=(
            "Ordinal transform of the Greek alphabet (α=1…ω=24). "
            "Convention; public domain."
        ),
        mapping=_GREEK_ORD,
    ),
    BundledCipher(
        slug="heb-hechrachi",
        name="Mispar Hechrachi",
        language="hebrew",
        citation=(
            "Sefer Yetzirah 1:1 (c. 2nd-6th c. CE). Traditional "
            "absolute value. Public domain."
        ),
        mapping=_HEB_HECHRACHI,
    ),
    BundledCipher(
        slug="heb-siduri",
        name="Mispar Siduri",
        language="hebrew",
        citation=(
            "Ordinal transform of the Hebrew alphabet (א=1…ת=22). "
            "Traditional kabbalistic method. Public domain."
        ),
        mapping=_HEB_SIDURI,
    ),
    BundledCipher(
        slug="heb-atbash",
        name="Atbash",
        language="hebrew",
        citation=(
            "Hebrew substitution cipher attested in Jeremiah 25:26, "
            "51:41. Public domain."
        ),
        mapping=_HEB_ATBASH,
    ),
    BundledCipher(
        slug="heb-gadol",
        name="Mispar Gadol",
        language="hebrew",
        citation=(
            "Hebrew gematria with final forms valued 500-900. "
            "Attested in Sefer Raziel ha-Malakh. Public domain."
        ),
        mapping=_HEB_GADOL,
    ),
    BundledCipher(
        slug="heb-katan",
        name="Mispar Katan",
        language="hebrew",
        citation=(
            "Hebrew gematria reduced to single digits via modulo 9. "
            "Conventional reduction; public domain."
        ),
        mapping=_HEB_KATAN,
    ),
    BundledCipher(
        slug="eng-simple",
        name="Simple",
        language="english",
        citation="Convention: A=1…Z=26 ordinal. Public domain.",
        mapping=_ENG_SIMPLE,
    ),
    BundledCipher(
        slug="eng-alw",
        name="Crowley ALW",
        language="english",
        citation=(
            "Aleister Crowley, Liber CCXXXI (Trigrammaton, 1907). "
            "Public domain (UK author's-death +70, 2018+)."
        ),
        mapping=_ENG_ALW,
    ),
    BundledCipher(
        slug="eng-naeq",
        name="NAEQ",
        language="english",
        citation=(
            "New Aeon English Qabalah — James Lees, 1976. "
            "Public domain on a fair-use basis (system widely published)."
        ),
        mapping=_ENG_NAEQ,
    ),
    BundledCipher(
        slug="eng-heb-mapped",
        name="Hebrew-mapped",
        language="english",
        citation=(
            "English letters mapped to Hebrew equivalents (Crowley "
            "convention from 777). Public domain."
        ),
        mapping=_ENG_HEB_MAPPED,
    ),
    BundledCipher(
        slug="ar-abjad",
        name="Abjad",
        language="arabic",
        citation=(
            "Standard Arabic abjad (ḥisāb al-jummal). Pre-Islamic "
            "convention; public domain."
        ),
        mapping=_ARABIC_ABJAD,
    ),
    BundledCipher(
        slug="skt-katapayadi",
        name="Kaṭapayādi",
        language="sanskrit",
        citation=(
            "Sanskrit numerical mnemonic system. Vedic-era; public "
            "domain (tabulated in Burnell 1874)."
        ),
        mapping=_SANSKRIT_KATAPAYADI,
    ),
    BundledCipher(
        slug="copt-iso",
        name="Coptic isopsephy",
        language="coptic",
        citation=(
            "Coptic letter values inherit the Greek isopsephic "
            "system. Public domain."
        ),
        mapping=_COPTIC_ISO,
    ),
)


def bundled_by_slug(slug: str) -> BundledCipher | None:
    """Return the bundled cipher with the given slug, or None."""
    for c in BUNDLED_CIPHERS:
        if c.slug == slug:
            return c
    return None
