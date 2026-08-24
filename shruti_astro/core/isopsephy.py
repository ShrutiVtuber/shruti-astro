# SPDX-License-Identifier: AGPL-3.0-only
"""
Summing text under a cipher.

Two rules the tradition cares about and most calculators quietly break:

  - **Show what was counted and what was not.** A letter with no value in the
    chosen cipher is not worth zero; it is *outside the cipher*. Silently
    treating it as zero is how a total becomes unreproducible. Every unmatched
    character is returned so the reader can see the total's basis.
  - **Never normalise away the script.** Final sigma is σ's value but a distinct
    letter; Hebrew finals likewise. Stripping diacritics or case-folding across
    scripts is a decision the caller makes, not one made for them.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from shruti_astro.core.linguistic.ciphers import BUNDLED_CIPHERS, bundled_by_slug

LANGUAGES = sorted({c.language for c in BUNDLED_CIPHERS})


@dataclass
class Reduction:
    """Theosophic reduction: sum the digits until one remains."""

    steps: list[int]
    final: int


def reduce_digits(total: int) -> Reduction:
    steps: list[int] = []
    n = abs(total)
    while n > 9:
        n = sum(int(d) for d in str(n))
        steps.append(n)
    return Reduction(steps=steps, final=n)


def _fold(text: str, strip_marks: bool) -> str:
    text = text.lower()
    if not strip_marks:
        return text
    # NFD then drop combining marks — turns πολυτονικά into monotonic forms and
    # Hebrew pointing into bare consonants, which is what the ciphers key on.
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if not unicodedata.combining(ch)
    )


def isopsephy(text: str, cipher_slug: str, strip_marks: bool = True) -> dict:
    cipher = bundled_by_slug(cipher_slug)
    if cipher is None:
        raise ValueError(f"unknown cipher: {cipher_slug}")

    folded = _fold(text, strip_marks)

    total = 0
    counted: list[dict] = []
    unmatched: list[str] = []
    for ch in folded:
        if ch in cipher.mapping:
            value = cipher.mapping[ch]
            total += value
            counted.append({"char": ch, "value": value})
        elif ch.isspace() or unicodedata.category(ch).startswith("P"):
            continue          # spaces and punctuation are not "unmatched"
        else:
            unmatched.append(ch)

    reduction = reduce_digits(total)
    return {
        "text": text,
        "cipher": {
            "slug": cipher.slug, "name": cipher.name,
            "language": cipher.language, "citation": cipher.citation,
        },
        "total": total,
        "reduction": {"steps": reduction.steps, "final": reduction.final},
        "letters": counted,
        # Present so the total's basis is visible, never silently dropped.
        "unmatched": sorted(set(unmatched)),
        "stripMarks": strip_marks,
    }


def catalogue() -> list[dict]:
    return [
        {"slug": c.slug, "name": c.name, "language": c.language,
         "citation": c.citation, "letters": len(c.mapping)}
        for c in sorted(BUNDLED_CIPHERS, key=lambda c: (c.language, c.name))
    ]
