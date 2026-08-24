

def test_bodies_report_a_real_speed():
    """
    Swiss Ephemeris fills the speed slot only when FLG_SPEED is set. Without it
    every body reads 0.0 °/day, and since `retrograde` is `speed < 0`, nothing
    is ever retrograde — a silent, total failure of a thing astrology cares
    about a great deal.
    """
    from datetime import datetime, timezone

    from shruti_astro.core.ephemeris import chart_positions

    pos = chart_positions(datetime(2026, 3, 1, 12, tzinfo=timezone.utc), 37.98, 23.73)
    by = {b.name: b for b in pos.bodies}
    assert 0.9 < by["Sun"].speed < 1.1, "the Sun moves about a degree a day"
    assert 11.0 < by["Moon"].speed < 15.5, "the Moon moves about 13 degrees a day"


def test_retrograde_is_detected():
    """Mercury is retrograde on 1 March 2026; the daemon reported it direct."""
    from datetime import datetime, timezone

    from shruti_astro.core.ephemeris import chart_positions

    pos = chart_positions(datetime(2026, 3, 1, 12, tzinfo=timezone.utc), 37.98, 23.73)
    mercury = next(b for b in pos.bodies if b.name == "Mercury")
    assert mercury.speed < 0 and mercury.retrograde
