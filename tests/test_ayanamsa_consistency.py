# SPDX-License-Identifier: AGPL-3.0-only
"""
The reported ayanāṁśa must reconcile with the reported positions.

This is the credibility test. Anyone can subtract one number from another, and
if tropical − ayanāṁśa does not equal the sidereal longitude we printed, the
tool looks wrong even when the positions are right.

`swe.get_ayanamsa_ut` is the trap: it ignores the calculation flags and lands
~14 arcseconds away from what the sidereal positions actually use.
"""

from datetime import datetime, timezone

from shruti_astro.core.ephemeris import chart_positions, longitudes

MOMENT = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc)
ATHENS = (37.9838, 23.7275)


def test_panchanga_longitudes_reconcile():
    L = longitudes(MOMENT, "lahiri")
    assert abs(((L.sun_tropical - L.ayanamsa) % 360) - L.sun_sidereal) < 1e-6
    assert abs(((L.moon_tropical - L.ayanamsa) % 360) - L.moon_sidereal) < 1e-6


def test_chart_longitudes_reconcile():
    lat, lon = ATHENS
    trop = chart_positions(MOMENT, lat, lon, sidereal=False)
    sid = chart_positions(MOMENT, lat, lon, sidereal=True, ayanamsa="lahiri")

    t = {b.name: b.longitude for b in trop.bodies}
    s = {b.name: b.longitude for b in sid.bodies}

    for name in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        expected = (t[name] - sid.ayanamsa) % 360
        assert abs(expected - s[name]) < 1e-6, (
            f"{name}: tropical {t[name]} − ayanāṁśa {sid.ayanamsa} = {expected}, "
            f"but sidereal reported {s[name]}"
        )


def test_ayanamsa_is_the_flag_aware_value():
    # Lahiri at J2000 under the flags actually used is 23.8532°, not the
    # 23.8571° that the flag-blind call returns.
    L = longitudes(MOMENT, "lahiri")
    assert abs(L.ayanamsa - 23.853222) < 1e-4


def test_nodes_stay_exactly_opposed():
    lat, lon = ATHENS
    pos = chart_positions(MOMENT, lat, lon, sidereal=True)
    b = {x.name: x.longitude for x in pos.bodies}
    assert abs(((b["Ketu"] - b["Rahu"]) % 360) - 180.0) < 1e-9
