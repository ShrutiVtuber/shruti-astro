# SPDX-License-Identifier: AGPL-3.0-only
"""Public computation endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from shruti_astro.core import panchanga as pa
from shruti_astro.core.ephemeris import (
    AYANAMSAS,
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
) -> dict:
    """
    The twenty-four unequal hours for the sunrise-to-sunrise cycle containing
    `when`, and which one is current.

    At polar latitudes this returns 422 with an explanation rather than
    inventing twelve equal hours of a day the Sun never made.
    """
    moment = _moment(when)
    try:
        sunrise, sunset, next_sunrise = sun_events(moment, lat, lon)
        hours = build_hours(sunrise, sunset, next_sunrise, sunrise.weekday())
    except (SunNeverRose, NoPlanetaryHours) as exc:
        raise HTTPException(422, str(exc))

    now = current_hour(hours, moment)
    return {
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
) -> dict:
    """
    The five limbs at one instant.

    Each limb reports how far through itself it is, because a limb is a span,
    not a label — naming only the one in force at noon is the error most
    pañcāṅga sites make.
    """
    if ayanamsa not in AYANAMSAS:
        raise HTTPException(400, f"unknown ayanamsa; choose from {sorted(AYANAMSAS)}")

    moment = _moment(when)
    L = longitudes(moment, ayanamsa)

    def limb(x) -> dict:
        return {"index": x.index, "name": x.name, "fraction": round(x.fraction, 6)}

    return {
        "at": moment.isoformat(),
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


@router.get("/ayanamsas")
async def list_ayanamsas() -> dict:
    """Practitioners genuinely disagree here; the choice is theirs, not ours."""
    return {"ayanamsas": sorted(AYANAMSAS)}
