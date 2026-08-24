# SPDX-License-Identifier: AGPL-3.0-only
"""
The windows of the day — reported, never prescribed.

Rāhu kāla, Yamagaṇḍa and Gulika kāla each occupy one eighth of the daylight,
and which eighth depends on the weekday. Abhijit is the eighth of fifteen
muhūrtas, straddling local noon.

These are widely observed and widely disagreed about. This module states when
they fall and says nothing about what to do — the software's job is the
arithmetic, not the ruling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# Which eighth of the daylight, 1-indexed, keyed by Python weekday (Mon=0..Sun=6).
RAHU_KALA = {0: 2, 1: 7, 2: 5, 3: 6, 4: 4, 5: 3, 6: 8}
YAMAGANDA = {0: 4, 1: 3, 2: 2, 3: 1, 4: 7, 5: 6, 6: 5}
GULIKA = {0: 6, 1: 5, 2: 4, 3: 3, 4: 2, 5: 1, 6: 7}

VARA = {
    0: ("Somavāra", "Moon"), 1: ("Maṅgalavāra", "Mars"), 2: ("Budhavāra", "Mercury"),
    3: ("Guruvāra", "Jupiter"), 4: ("Śukravāra", "Venus"), 5: ("Śanivāra", "Saturn"),
    6: ("Ravivāra", "Sun"),
}


@dataclass
class Window:
    name: str
    start: datetime
    end: datetime
    note: str = ""


def _eighth(sunrise: datetime, sunset: datetime, index: int) -> tuple[datetime, datetime]:
    part = (sunset - sunrise) / 8
    return sunrise + part * (index - 1), sunrise + part * index


def windows(sunrise: datetime, sunset: datetime, weekday: int) -> list[Window]:
    """
    The day's named windows.

    `weekday` is the weekday of the *sunrise that began this day* — the Hindu
    day runs sunrise to sunrise, so a moment before dawn still belongs to
    yesterday's vāra and takes yesterday's windows.
    """
    out: list[Window] = []

    for label, table in (
        ("Rāhu kāla", RAHU_KALA),
        ("Yamagaṇḍa", YAMAGANDA),
        ("Gulika kāla", GULIKA),
    ):
        start, end = _eighth(sunrise, sunset, table[weekday])
        out.append(Window(name=label, start=start, end=end,
                          note=f"eighth {table[weekday]} of 8 of the daylight"))

    # Abhijit: the eighth of fifteen muhūrtas, centred on local noon. Several
    # traditions do not observe it on Wednesday; that is recorded, not applied.
    muhurta = (sunset - sunrise) / 15
    out.append(Window(
        name="Abhijit muhūrta",
        start=sunrise + muhurta * 7,
        end=sunrise + muhurta * 8,
        note="muhūrta 8 of 15" + ("; not observed on Wednesday in some traditions"
                                  if weekday == 2 else ""),
    ))
    return out


# ── ayana and ṛtu ───────────────────────────────────────────────────────────

def ayana(sun_rashi: int) -> str:
    """
    Uttarāyaṇa while the Sun runs Makara through Mithuna; Dakṣiṇāyana otherwise.

    Sidereal rāśi, so this is the *traditional* ayana — it no longer coincides
    with the tropical solstices, and the drift is the precession itself.
    """
    return "Uttarāyaṇa" if sun_rashi in (9, 10, 11, 0, 1, 2) else "Dakṣiṇāyana"


# Six seasons, two lunar months each, indexed from Chaitra.
RTU = [
    "Vasanta", "Vasanta", "Grīṣma", "Grīṣma", "Varṣā", "Varṣā",
    "Śarad", "Śarad", "Hemanta", "Hemanta", "Śiśira", "Śiśira",
]


def rtu(lunar_month_index: int) -> str:
    """`lunar_month_index` is 0-based from Chaitra."""
    return RTU[lunar_month_index % 12]
