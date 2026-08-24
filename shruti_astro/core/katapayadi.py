# SPDX-License-Identifier: AGPL-3.0-only
"""
Kaṭapayādi — a place-value encoding, not a sum.

Sanskrit has no additive gematria of the Greek kind, and treating it as though
it does produces a number that means nothing. Four consonant series run against
the digits, and:

  - **only the last consonant of a cluster counts** — in क्ष (kṣa) the k is
    silent for this purpose and the ṣ carries the value;
  - **standalone vowels are 0**, while vowel signs attached to a consonant carry
    no digit of their own;
  - **the digits are read right to left** — *aṅkānāṁ vāmato gatiḥ*, "the motion
    of digits is leftward".

So भारत is bha·ra·ta → 4, 2, 6 → **624**, not 4+2+6.

There is deliberately **no total**. If an additive Devanagari scheme is ever
wanted it goes alongside this one as a separate option, never replacing it.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

VIRAMA = "्"

# The four series. ka·ṭa·pa·ya all mean 1 — the mnemonic the system is named for.
_SERIES: dict[str, int] = {}
for _row, _values in (
    ("क ख ग घ ङ च छ ज झ ञ", [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]),   # ka-varga
    ("ट ठ ड ढ ण त थ द ध न", [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]),   # ṭa/ta-varga
    ("प फ ब भ म",           [1, 2, 3, 4, 5]),                   # pa-varga
    ("य र ल व श ष स ह",     [1, 2, 3, 4, 5, 6, 7, 8]),          # ya-varga
):
    for _ch, _v in zip(_row.split(), _values):
        _SERIES[_ch] = _v

# Independent vowels are 0. Vowel *signs* (mātrās) carry nothing.
_VOWELS = set("अआइईउऊऋॠऌॡएऐओऔ")
_MATRAS = set("ािीुूृॄेैोौॅॉ")


@dataclass
class Syllable:
    text: str
    digit: int | None
    reason: str


def encode(text: str) -> dict:
    """
    Digits in written order, plus the number they make when read right to left.
    """
    chars = unicodedata.normalize("NFC", text)
    syllables: list[Syllable] = []
    unreckonable: list[str] = []

    i = 0
    while i < len(chars):
        ch = chars[i]

        if ch in _SERIES:
            # Consume a cluster: consonant (virama consonant)*. Only the final
            # consonant of the run carries the digit.
            cluster = ch
            last = ch
            j = i + 1
            while j + 1 < len(chars) and chars[j] == VIRAMA and chars[j + 1] in _SERIES:
                cluster += chars[j] + chars[j + 1]
                last = chars[j + 1]
                j += 2
            # A trailing mātrā belongs to the syllable but adds nothing.
            if j < len(chars) and chars[j] in _MATRAS:
                cluster += chars[j]
                j += 1
            reason = ("last consonant of the cluster" if last != ch else "consonant")
            syllables.append(Syllable(cluster, _SERIES[last], reason))
            i = j
            continue

        if ch in _VOWELS:
            syllables.append(Syllable(ch, 0, "independent vowel"))
            i += 1
            continue

        if ch in _MATRAS or ch in ("ं", "ः", "ँ"):
            # Stray mātrā or anusvāra/visarga — part of a syllable, no digit.
            i += 1
            continue

        if ch.isspace() or unicodedata.category(ch).startswith("P"):
            i += 1
            continue

        unreckonable.append(ch)
        i += 1

    digits = [s.digit for s in syllables if s.digit is not None]
    # aṅkānāṁ vāmato gatiḥ — the digits are read from the right.
    number = int("".join(str(d) for d in reversed(digits))) if digits else None

    return {
        "text": text,
        "system": "kaṭapayādi",
        "rule": "अङ्कानां वामतो गतिः",
        "ruleGloss": "the motion of digits is leftward — read the digits right to left",
        "syllables": [
            {"text": s.text, "digit": s.digit, "reason": s.reason} for s in syllables
        ],
        "digitsInWrittenOrder": digits,
        "number": number,
        # Stated explicitly so nobody adds one later.
        "total": None,
        "totalNote": "kaṭapayādi is positional, not additive — it yields a number, not a sum",
        "unreckonable": sorted(set(unreckonable)),
    }
