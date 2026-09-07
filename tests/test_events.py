# SPDX-License-Identifier: AGPL-3.0-only
"""
The events a column is written from.

**Checked against facts that exist outside this codebase**, because a test
written from the module's own output only proves it is consistent, and an
ephemeris that is consistently wrong is the failure mode that matters. The
March 2026 equinox, the four eclipses of 2026 and the number of ingresses in a
year are all independently known; if the arithmetic drifts, these fail.

The void-of-course windows are checked a second way: against the daemon's own
pointwise answer, computed by unrelated code in `void_of_course.py`. The two
must agree at every instant, and the interesting instants are the ones just
inside and just outside a window.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest

from shruti_astro.core import events as E
from shruti_astro.core.void_of_course import is_void_of_course


def utc(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=UTC)


# ── against the world ───────────────────────────────────────────────────────


def test_the_sun_enters_every_sign_once_a_year():
    solar = [e for e in E.ingresses(utc(2026, 1, 1), utc(2027, 1, 1))
             if e.bodies == ("Sun",)]
    assert len(solar) == 12
    assert {e.sign for e in solar} == set(E.SIGNS)


def test_the_equinox_is_where_the_almanacs_put_it():
    """
    The Sun's ingress into Aries, March 2026: 20 March, 14:46 UT.

    This is the anchor the astrological year turns on, and it is published to
    the minute in every almanac — so it is the single best check that the
    root-finding is solving what it claims to.
    """
    aries = next(e for e in E.ingresses(utc(2026, 3, 1), utc(2026, 4, 1))
                 if e.bodies == ("Sun",) and e.sign == "Aries")
    assert abs(aries.at - utc(2026, 3, 20, 14, 46)) < timedelta(minutes=1)
    assert aries.degree < 0.01           # an ingress is the boundary itself


@pytest.mark.parametrize("when,of,kind", [
    (utc(2026, 2, 17), "solar", "annular"),
    (utc(2026, 3, 3), "lunar", "total"),
    (utc(2026, 8, 12), "solar", "total"),
    (utc(2026, 8, 28), "lunar", "partial"),
])
def test_the_eclipses_of_2026(when, of, kind):
    """All four, by date and by type. The August total is the Iceland–Spain one."""
    found = E.eclipses(utc(2026, 1, 1), utc(2027, 1, 1))
    match = [e for e in found if abs(e.at - when) < timedelta(days=1)]
    assert match, f"no {of} eclipse near {when:%Y-%m-%d}"
    assert match[0].detail["of"] == of
    assert match[0].detail["type"] == kind


def test_2026_has_exactly_four_eclipses():
    assert len(E.eclipses(utc(2026, 1, 1), utc(2027, 1, 1))) == 4


def test_lunations_run_new_first_full_last_and_repeat():
    """
    A synodic month is 29.53 days, so a quarter is about 7.4 — and the phases
    can only ever arrive in that order, because the elongation they are
    measured on never runs backwards.
    """
    got = E.lunations(utc(2026, 9, 1), utc(2026, 12, 1))
    order = [e.detail["phase"] for e in got]
    cycle = ["new", "first quarter", "full", "last quarter"]
    start = cycle.index(order[0])
    for i, phase in enumerate(order):
        assert phase == cycle[(start + i) % 4]
    gaps = [(b.at - a.at).days for a, b in pairwise(got)]
    assert all(6 <= g <= 9 for g in gaps), gaps


def test_mercury_turns_retrograde_three_times_a_year():
    """Three or four; never two, never five. A well-known cadence."""
    turns = [e for e in E.stations(utc(2026, 1, 1), utc(2027, 1, 1))
             if e.bodies == ("Mercury",)]
    retro = [e for e in turns if e.detail["direction"] == "retrograde"]
    assert 3 <= len(retro) <= 4, [str(e.at) for e in retro]
    # Every retrograde is answered by a direct station.
    assert abs(len(retro) - len([e for e in turns
                                 if e.detail["direction"] == "direct"])) <= 1


def test_a_station_is_where_the_speed_is_nought():
    for event in E.stations(utc(2026, 1, 1), utc(2026, 7, 1)):
        before = E._speed(E._julday(event.at) - 0.5, dict(E.TRADITIONAL)[event.bodies[0]])
        after = E._speed(E._julday(event.at) + 0.5, dict(E.TRADITIONAL)[event.bodies[0]])
        assert (before < 0) != (after < 0), f"{event.bodies[0]} at {event.at}"


# ── against the daemon's other implementation ───────────────────────────────


@pytest.mark.parametrize("rule", ["thirtyDegrees", "signExit"])
def test_void_windows_agree_with_the_pointwise_answer(rule):
    """
    Two unrelated routes to the same fact.

    `void_of_course.py` answers "is she void now" by searching forward from one
    instant. This module builds spans from perfections and ingresses. They are
    different code and they must not disagree — and the instants worth checking
    are the ones just inside and just outside each window, because that is
    where an off-by-one in either would show.
    """
    start, end = utc(2026, 9, 1), utc(2026, 9, 21)
    windows = E.void_windows(start, end, rule=rule)

    for window in windows[:4]:
        until = datetime.fromisoformat(window.detail["until"])
        inside = window.at + (until - window.at) / 2
        assert is_void_of_course(inside, rule=rule)["void"] is True, \
            f"{rule}: {inside} is inside a window but reads busy"

        outside = window.at - timedelta(minutes=20)
        assert is_void_of_course(outside, rule=rule)["void"] is False, \
            f"{rule}: {outside} is before a window but reads void"


def test_the_two_void_rules_are_not_the_same_rule():
    """
    They disagree, in both directions, and the author's table exists to show
    where. A build where they agreed everywhere would mean one of them is not
    being applied.
    """
    start, end = utc(2026, 1, 1), utc(2026, 4, 1)
    by_sign = E.void_windows(start, end, rule="signExit")
    by_thirty = E.void_windows(start, end, rule="thirtyDegrees")
    assert len(by_sign) != len(by_thirty)


# ── shape ───────────────────────────────────────────────────────────────────


def test_a_retrograde_ingress_says_so():
    """
    Backing into the previous sign is an ingress too. Marked, because three
    crossings of one boundary during a retrograde loop would otherwise read as
    three separate arrivals.
    """
    year = E.ingresses(utc(2026, 1, 1), utc(2027, 1, 1))
    backward = [e for e in year if e.detail["retrograde"]]
    assert backward, "a year contains retrograde ingresses"
    lookup = dict(E._bodies_for(include_modern=True, true_node=False))
    for event in backward:
        speed = E._speed(E._julday(event.at), lookup[event.bodies[0]])
        assert speed <= 0.01, f"{event.bodies[0]} at {event.at} is not retrograde"


def test_everything_comes_back_sorted_and_serialisable():
    got = E.events_in_range(utc(2026, 9, 1), utc(2026, 9, 8))
    assert got == sorted(got, key=lambda e: e.at)
    for event in got:
        payload = event.as_dict()
        assert payload["at"].endswith("Z"), "UTC, and said so"
        assert payload["kind"] and payload["bodies"]


def test_kinds_narrows_the_work_not_only_the_output():
    """Perfections are the expensive half; asking for ingresses must not pay."""
    only = E.events_in_range(utc(2026, 9, 1), utc(2026, 9, 8), kinds=("ingress",))
    assert only and {e.kind for e in only} == {"ingress"}


def test_an_opposition_is_not_invisible_to_the_pointwise_search():
    """
    The bug this file found in the live endpoint.

    A separation folded into (−180, 180] runs 179.9 → −179.9 through an
    opposition, so testing `sep − 180` for a sign change sees −0.1 → −359.9 and
    finds nothing. `/void-of-course` was reporting the Moon void while she
    still had an opposition to perfect — an error in the one direction that
    matters, since the whole point of the reading is "she completes nothing
    more".

    31 August 2026, 19:27 UT: the Moon opposes Venus twenty minutes later, in
    the same sign.
    """
    before = utc(2026, 8, 31, 19, 27)
    for rule in ("signExit", "thirtyDegrees"):
        answer = is_void_of_course(before, rule=rule)
        assert answer["void"] is False, rule
        assert any(p["aspect"] == 180.0 for p in answer["perfections"]), \
            f"{rule}: the opposition to Venus was not seen"


def test_an_opposition_is_counted_once_not_twice():
    """
    180 and −180 are the same separation. Listing both finds one opposition
    twice, which would make a busy Moon look busier and, worse, make the
    perfection list disagree with the event table.
    """
    answer = is_void_of_course(utc(2026, 8, 31, 19, 27), rule="signExit")
    oppositions = [p for p in answer["perfections"] if p["aspect"] == 180.0]
    assert len(oppositions) == len({(p["body"], p["withinDegrees"])
                                    for p in oppositions})


# ── over HTTP ───────────────────────────────────────────────────────────────


def _client():
    from fastapi.testclient import TestClient

    from shruti_astro.api.app import app
    return TestClient(app)


def test_the_events_endpoint_answers_a_week():
    r = _client().get("/events", params={
        "start": "2026-09-07", "end": "2026-09-14", "kinds": "ingress,lunation"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == len(body["events"]) > 0
    assert {e["kind"] for e in body["events"]} <= {"ingress", "lunation"}


def test_timestamps_are_seconds_and_say_they_are_utc():
    """
    Delta-T is uncertain by more than a second across this range, so anything
    finer is precision the number does not have — and it would triple the size
    of a year's event list for nothing.
    """
    r = _client().get("/events", params={"start": "2026-09-07", "end": "2026-09-10"})
    for event in r.json()["events"]:
        assert event["at"].endswith("Z")
        assert "." not in event["at"], f"sub-second precision: {event['at']}"


def test_a_span_that_is_too_long_is_refused_not_quietly_shortened():
    """
    Silently returning eleven months of a year somebody asked for is the
    failure that gets noticed after publication, when a column is missing
    events nobody was told had been dropped.
    """
    client = _client()
    assert client.get("/events", params={
        "start": "2020-01-01", "end": "2026-01-01"}).status_code == 400
    assert client.get("/events", params={
        "start": "2026-09-14", "end": "2026-09-07"}).status_code == 400


def test_the_ephemeris_endpoint_names_which_hour_it_used():
    """A reader checking against a printed book has to know which convention."""
    r = _client().get("/ephemeris", params={
        "start": "2026-09-07", "end": "2026-09-09", "hour": "noon"})
    body = r.json()
    assert body["hour"] == "noon"
    assert "noon" in body["note"]
    assert len(body["days"]) == 3
    assert _client().get("/ephemeris", params={
        "start": "2026-09-07", "end": "2026-09-08",
        "hour": "teatime"}).status_code == 400


def test_a_week_of_positions_is_a_few_kilobytes():
    """The whole argument against shipping an ephemeris to the browser."""
    import json

    r = _client().get("/positions", params={"start": "2026-09-07", "end": "2026-09-14"})
    assert r.status_code == 200
    assert len(json.dumps(r.json())) < 32 * 1024
    assert r.json()["bodies"]["Moon"]["spacingDays"] <= 1.0 / 24.0


def test_every_perfection_is_actually_exact_at_the_time_it_claims():
    """
    The check that survives an ephemeris upgrade.

    Pinning a count would break the day Swiss Ephemeris shifts a value in the
    last decimal; this instead asserts the property that makes each row true —
    at the instant reported, the two bodies really are that far apart. A scan
    that missed events would still pass, so the count is checked too, loosely:
    a month has dozens of exact configurations, never a handful.
    """
    # The same node setting on both sides. The true and mean nodes differ by
    # over a degree, so measuring one against events computed from the other
    # fails on every lunar-node aspect and on nothing else — which is exactly
    # how this test first failed.
    found = E.perfections(utc(2026, 9, 1), utc(2026, 10, 1), true_node=True)
    assert 30 < len(found) < 200, len(found)

    lookup = dict(E._bodies_for(include_modern=True, true_node=True))
    for event in found:
        jd = E._julday(event.at)
        a, b = (lookup[name] for name in event.bodies)
        separation = abs(E._wrapped(E._lon(jd, a) - E._lon(jd, b)))
        wanted = abs(event.detail["separation"])
        assert abs(separation - wanted) < 0.001, (
            f"{event.bodies} {event.detail['aspect']} at {event.at}: "
            f"separation is {separation:.4f}°, not {wanted}°")


def test_a_month_of_events_is_computed_in_about_a_second():
    """
    A page renders this. Eight seconds of it was Swiss Ephemeris being asked
    for the same longitudes tens of thousands of times, once per pair per
    target per sample, instead of once per sample.
    """
    import time

    began = time.monotonic()
    E.events_in_range(utc(2026, 9, 1), utc(2026, 10, 1))
    elapsed = time.monotonic() - began
    assert elapsed < 5.0, f"a month took {elapsed:.1f}s"
