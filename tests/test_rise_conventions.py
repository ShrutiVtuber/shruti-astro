# SPDX-License-Identifier: AGPL-3.0-only
"""
Both traditions, side by side.

Sophia practises Hellenistic *and* Vedic, so sunrise is not one definition here
and these tests exist to stop anyone "simplifying" it back to one later.
"""

from datetime import datetime, timezone

import pytest

from shruti_astro.core.ephemeris import RISE_CONVENTIONS, sun_events

ATHENS = (37.9838, 23.7275)
DELHI = (28.6139, 77.2090)
WHEN = datetime(2026, 8, 24, 9, 0, tzinfo=timezone.utc)


def test_both_conventions_are_offered():
    assert set(RISE_CONVENTIONS) == {"visible_disc", "hindu"}


@pytest.mark.parametrize("place", [ATHENS, DELHI])
def test_conventions_disagree_by_minutes_not_seconds(place):
    """
    Hindu rising uses the centre of the disc with no refraction, so it is
    strictly LATER than the visible upper limb. The gap is a few minutes —
    enough to move a tithi-at-sunrise across a boundary, which is precisely
    why both are offered rather than one being picked.
    """
    lat, lon = place
    western, _, _ = sun_events(WHEN, lat, lon, "visible_disc")
    hindu, _, _ = sun_events(WHEN, lat, lon, "hindu")

    delta = (hindu - western).total_seconds()
    assert delta > 0, "hindu sunrise must be later — centre of disc, no refraction"
    assert 60 < delta < 900, f"expected a few minutes, got {delta}s"


def test_default_is_the_hellenistic_convention():
    """Planetary hours are Greco-Egyptian; the default must not drift."""
    lat, lon = ATHENS
    assert sun_events(WHEN, lat, lon) == sun_events(WHEN, lat, lon, "visible_disc")


def test_unknown_convention_is_refused():
    lat, lon = ATHENS
    with pytest.raises(ValueError):
        sun_events(WHEN, lat, lon, "whatever_looks_right")
