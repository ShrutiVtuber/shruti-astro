# SPDX-License-Identifier: AGPL-3.0-only
"""Public computation endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from shruti_astro.core import panchanga as pa
from shruti_astro.core.ephemeris import (
    AYANAMSAS,
    RISE_CONVENTIONS,
    SunNeverRose,
    longitudes,
    sun_events,
)
from shruti_astro.core.planetary_hours import (
    NoPlanetaryHours,
    build_hours,
    current_hour,
)

router = APIRouter()


def _moment(when: str | None) -> datetime:
    if not when:
        return datetime.now(timezone.utc)
    try:
        m = datetime.fromisoformat(when.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "when must be an ISO-8601 datetime")
    return m if m.tzinfo else m.replace(tzinfo=timezone.utc)


@router.get("/planetary-hours")
async def planetary_hours(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    when: str | None = Query(None, description="ISO-8601; defaults to now"),
    convention: str = Query(
        "visible_disc",
        description="visible_disc (Hellenistic/almanac) | hindu (centre of disc, no refraction)",
    ),
) -> dict:
    """
    The twenty-four unequal hours for the sunrise-to-sunrise cycle containing
    `when`, and which one is current.

    Defaults to `visible_disc` — the Greco-Egyptian basis for planetary hours,
    and what every Western almanac prints. Pass `hindu` only if you deliberately
    want the Indian sunrise definition; it will shift every hour boundary.

    At polar latitudes this returns 422 with an explanation rather than
    inventing twelve equal hours of a day the Sun never made.
    """
    if convention not in RISE_CONVENTIONS:
        raise HTTPException(400, f"unknown convention; choose from {sorted(RISE_CONVENTIONS)}")
    moment = _moment(when)
    try:
        sunrise, sunset, next_sunrise = sun_events(moment, lat, lon, convention)
        hours = build_hours(sunrise, sunset, next_sunrise, sunrise.weekday())
    except (SunNeverRose, NoPlanetaryHours) as exc:
        raise HTTPException(422, str(exc))

    now = current_hour(hours, moment)
    return {
        "convention": convention,
        "sunrise": sunrise.isoformat(),
        "sunset": sunset.isoformat(),
        "nextSunrise": next_sunrise.isoformat(),
        "dayRuler": hours[0].ruler,
        "current": None if now is None else {
            "index": now.index, "ruler": now.ruler, "isNight": now.is_night,
            "startsAt": now.starts_at.isoformat(), "endsAt": now.ends_at.isoformat(),
        },
        "hours": [
            {"index": h.index, "ruler": h.ruler, "isNight": h.is_night,
             "startsAt": h.starts_at.isoformat(), "endsAt": h.ends_at.isoformat()}
            for h in hours
        ],
    }


@router.get("/panchanga")
async def panchanga_endpoint(
    when: str | None = Query(None, description="ISO-8601; defaults to now"),
    ayanamsa: str = Query("lahiri"),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    at_sunrise: bool = Query(
        False, description="Evaluate at sunrise — how almanacs name the day. Needs lat/lon."
    ),
) -> dict:
    """
    The five limbs.

    Each limb reports how far through itself it is, because a limb is a span,
    not a label — naming only the one in force at the moment you asked is the
    error most pañcāṅga sites make.

    **To match a printed Indian almanac, pass `at_sunrise=true` with lat/lon.**
    Almanacs name the day by the tithi prevailing at *sunrise*, computed under
    the Hindu rise convention (centre of disc, no refraction). Asking at noon
    can legitimately return the next tithi and disagree with the almanac by a
    day — that is not a bug in either, it is a different question.
    """
    if ayanamsa not in AYANAMSAS:
        raise HTTPException(400, f"unknown ayanamsa; choose from {sorted(AYANAMSAS)}")

    moment = _moment(when)
    evaluated_at = "instant"
    sunrise_used = None

    if at_sunrise:
        if lat is None or lon is None:
            raise HTTPException(400, "at_sunrise requires lat and lon")
        try:
            # Hindu convention deliberately hardcoded here: this mode exists to
            # reproduce an almanac, and almanacs use that definition.
            sunrise, _, _ = sun_events(moment, lat, lon, "hindu")
        except SunNeverRose as exc:
            raise HTTPException(422, str(exc))
        moment, evaluated_at, sunrise_used = sunrise, "sunrise", sunrise.isoformat()

    L = longitudes(moment, ayanamsa)

    def limb(x) -> dict:
        return {"index": x.index, "name": x.name, "fraction": round(x.fraction, 6)}

    return {
        "at": moment.isoformat(),
        "evaluatedAt": evaluated_at,
        "sunrise": sunrise_used,
        "ayanamsa": {"name": L.ayanamsa_name, "degrees": round(L.ayanamsa, 6)},
        "tithi": limb(pa.tithi(L.sun_tropical, L.moon_tropical)),
        "nakshatra": limb(pa.nakshatra(L.moon_sidereal)),
        "yoga": limb(pa.yoga(L.sun_sidereal, L.moon_sidereal)),
        "karana": limb(pa.karana(L.sun_tropical, L.moon_tropical)),
        "longitudes": {
            "sunTropical": round(L.sun_tropical, 6),
            "moonTropical": round(L.moon_tropical, 6),
            "sunSidereal": round(L.sun_sidereal, 6),
            "moonSidereal": round(L.moon_sidereal, 6),
        },
    }


@router.get("/rise-conventions")
async def list_rise_conventions() -> dict:
    """Sunrise is not one definition. Both traditions are served, not merged."""
    return {
        "conventions": {
            "visible_disc": "upper limb of the apparent disc, with refraction — "
                            "Hellenistic planetary hours and Western almanacs",
            "hindu": "centre of the disc, no refraction — Indian pañcāṅgas and "
                     "the Vedic day boundary",
        }
    }


@router.get("/ayanamsas")
async def list_ayanamsas() -> dict:
    """Practitioners genuinely disagree here; the choice is theirs, not ours."""
    return {"ayanamsas": sorted(AYANAMSAS)}


@router.get("/house-systems")
async def list_house_systems() -> dict:
    from shruti_astro.core.ephemeris import HOUSE_SYSTEMS

    return {"houseSystems": sorted(HOUSE_SYSTEMS)}


@router.get("/chart")
async def chart(
    when: str = Query(..., description="Birth moment, ISO-8601. Include the offset."),
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    tradition: str = Query("hellenistic", description="hellenistic | vedic"),
    ayanamsa: str = Query("lahiri", description="Vedic only"),
    house_system: str = Query("whole_sign"),
    include_modern: bool = Query(False, description="Uranus, Neptune, Pluto"),
    true_node: bool = Query(False, description="True node instead of mean"),
) -> dict:
    """
    A full natal chart, in whichever tradition the visitor chooses.

    One computation underlies both. `tradition` selects the zodiac and the
    judgment layer laid over it:

      hellenistic — tropical; sect by the true degree rule, whole-sign places,
                    essential dignities, the seven Hermetic lots
      vedic       — sidereal; rāśi, nakṣatra with pāda and lord, navāṁśa (D9),
                    Rāhu and Ketu as full participants

    The positions are identical in both; only the frame and the reading differ.
    """
    from shruti_astro.core import hellenistic as he
    from shruti_astro.core import vedic as ve
    from shruti_astro.core.doctrine import DEFAULT, Doctrine, DoctrineError
    from shruti_astro.core.ephemeris import HOUSE_SYSTEMS, chart_positions

    if tradition not in ("hellenistic", "vedic"):
        raise HTTPException(400, "tradition must be 'hellenistic' or 'vedic'")
    if house_system not in HOUSE_SYSTEMS:
        raise HTTPException(400, f"unknown house system; choose from {sorted(HOUSE_SYSTEMS)}")
    if ayanamsa not in AYANAMSAS:
        raise HTTPException(400, f"unknown ayanamsa; choose from {sorted(AYANAMSAS)}")

    moment = _moment(when)
    sidereal = tradition == "vedic"

    try:
        pos = chart_positions(
            moment, lat, lon, sidereal=sidereal, ayanamsa=ayanamsa,
            house_system=house_system, include_modern=include_modern,
            true_node=true_node,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    by_name = {b.name: b.longitude for b in pos.bodies}

    out: dict = {
        "tradition": tradition,
        "zodiac": "sidereal" if sidereal else "tropical",
        "when": moment.isoformat(),
        "location": {"lat": lat, "lon": lon},
        "houseSystem": house_system,
        "ayanamsa": (
            {"name": ayanamsa, "degrees": round(pos.ayanamsa, 6)} if pos.ayanamsa else None
        ),
        "angles": {
            "ascendant": round(pos.ascendant, 6),
            "midheaven": round(pos.midheaven, 6),
            "descendant": round((pos.ascendant + 180) % 360, 6),
            "imumCoeli": round((pos.midheaven + 180) % 360, 6),
        },
        "cusps": [round(c, 6) for c in pos.cusps],
        "bodies": [],
    }

    if tradition == "hellenistic":
        s = he.sect(by_name["Sun"], pos.ascendant)
        out["sect"] = {
            "isDay": s.is_day, "luminary": s.luminary,
            "benefic": s.benefic, "malefic": s.malefic,
        }
        out["places"] = he.whole_sign_places(pos.ascendant)
        out["lots"] = {
            name: round(value, 6)
            for name, value in he.lots(pos.ascendant, by_name, s.is_day).items()
        }
        for b in pos.bodies:
            entry = {
                "name": b.name, "longitude": round(b.longitude, 6),
                "retrograde": b.retrograde, "speed": round(b.speed, 6),
            }
            # Nodes have no essential dignity in the tradition.
            if b.name not in ("Rahu", "Ketu"):
                entry["dignities"] = he.dignities(b.name, b.longitude, s.is_day, DEFAULT)
            out["bodies"].append(entry)
    else:
        asc_sign = int(pos.ascendant // 30)
        out["lagna"] = ve.rashi(pos.ascendant)
        out["nakshatraOfMoon"] = ve.nakshatra_of(by_name["Moon"])
        for b in pos.bodies:
            out["bodies"].append({
                "name": b.name, "longitude": round(b.longitude, 6),
                "retrograde": b.retrograde, "speed": round(b.speed, 6),
                "rashi": ve.rashi(b.longitude),
                "nakshatra": ve.nakshatra_of(b.longitude),
                "navamsa": ve.navamsa(b.longitude),
                # Bhāva counted from the lagna, whole-sign.
                "house": ((int(b.longitude // 30) - asc_sign) % 12) + 1,
            })

    return out
