# SPDX-License-Identifier: AGPL-3.0-only
"""Public computation endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
    The five limbs, each with the time it ends.

    A limb is a span, not a label: naming only the one in force at the moment
    asked is what makes a pañcāṅga useless for choosing a time, which is most of
    what a pañcāṅga is for.

    With lat/lon this also returns the almanac strip (sunrise, sunset, moonrise,
    moonset, ayana, ṛtu) and the day's named windows — **reported, not
    prescribed**.

    **`at_sunrise=true` reproduces a printed Indian almanac**, which names the
    day by the tithi prevailing at sunrise under the Hindu rise convention.

    Cannot-compute: where the Sun does not rise, the day has no beginning. The
    vāra and the windows are then undefined — but the four Moon-and-Sun limbs
    still hold, and are still returned.
    """
    from shruti_astro.core import muhurta as mu
    from shruti_astro.core import panchanga as pa
    from shruti_astro.core.ephemeris import (
        SunNeverRose, limb_end, moon_events, sun_events,
    )

    if ayanamsa not in AYANAMSAS:
        raise HTTPException(400, f"unknown ayanamsa; choose from {sorted(AYANAMSAS)}")

    moment = _moment(when)
    evaluated_at = "instant"
    sunrise = sunset = moonrise = moonset = None
    vara = None
    day_windows: list[dict] = []
    undefined: list[str] = []

    if lat is not None and lon is not None:
        try:
            sunrise, sunset, _ = sun_events(moment, lat, lon, "hindu")
            # The Hindu day runs sunrise to sunrise: before dawn still belongs
            # to yesterday's vāra, and takes yesterday's windows.
            if moment < sunrise:
                sunrise, sunset, _ = sun_events(
                    moment - timedelta(days=1), lat, lon, "hindu"
                )
            weekday = sunrise.weekday()
            name, ruler = mu.VARA[weekday]
            vara = {"name": name, "ruler": ruler,
                    "startsAt": sunrise.isoformat()}
            day_windows = [
                {"name": w.name, "start": w.start.isoformat(),
                 "end": w.end.isoformat(), "note": w.note}
                for w in mu.windows(sunrise, sunset, weekday)
            ]
            moonrise, moonset = moon_events(moment, lat, lon)
        except SunNeverRose as exc:
            undefined.append(f"vāra and the day's windows: {exc}")

    if at_sunrise:
        if sunrise is None:
            raise HTTPException(400, "at_sunrise requires lat and lon, and a Sun that rises")
        moment, evaluated_at = sunrise, "sunrise"

    L = longitudes(moment, ayanamsa)

    def limb(name: str, x) -> dict:
        ends = limb_end(name, moment, ayanamsa)
        return {
            "index": x.index, "name": x.name,
            "fraction": round(x.fraction, 6),
            "endsAt": ends.isoformat() if ends else None,
        }

    sun_rashi = int(L.sun_sidereal // 30)
    lunar_month_index = (sun_rashi + 1) % 12

    return {
        "at": moment.isoformat(),
        "evaluatedAt": evaluated_at,
        "sunrise": sunrise.isoformat() if sunrise else None,
        "ayanamsa": {"name": L.ayanamsa_name, "degrees": round(L.ayanamsa, 6),
                     "note": "a different ayanāṁśa can move a nakṣatra boundary"},
        "vara": vara,
        "tithi": limb("tithi", pa.tithi(L.sun_tropical, L.moon_tropical)),
        "nakshatra": limb("nakshatra", pa.nakshatra(L.moon_sidereal)),
        "yoga": limb("yoga", pa.yoga(L.sun_sidereal, L.moon_sidereal)),
        "karana": limb("karana", pa.karana(L.sun_tropical, L.moon_tropical)),
        "almanac": {
            "sunrise": sunrise.isoformat() if sunrise else None,
            "sunset": sunset.isoformat() if sunset else None,
            "moonrise": moonrise.isoformat() if moonrise else None,
            "moonset": moonset.isoformat() if moonset else None,
            "ayana": mu.ayana(sun_rashi),
            "rtu": mu.rtu(lunar_month_index),
        },
        # Reported, not prescribed. When each falls; nothing about what to do.
        "windows": day_windows,
        "undefined": undefined,
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
    dasha_levels: int = Query(2, ge=1, le=3, description="Vedic: mahā / antara / pratyantara"),
    dasha_year: str = Query("julian", description="Vedic: julian | sidereal | savana"),
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
    from shruti_astro.core import aspects as asp
    from shruti_astro.core import dasha as da
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

    speeds = {b.name: b.speed for b in pos.bodies}

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

        # Configuration is by SIGN in the tradition; the degree list is a
        # refinement for judging application, never a replacement.
        out["aspects"] = {
            "basis": "whole_sign",
            "configurations": [
                {"from": a.from_body, "to": a.to_body, "aspect": a.name,
                 "separationSigns": a.separation_signs}
                for a in asp.whole_sign_aspects(by_name)
            ],
            "byDegree": [
                {"from": a.from_body, "to": a.to_body, "aspect": a.name,
                 "orb": a.orb, "applying": a.applying}
                for a in asp.degree_aspects(by_name, speeds)
            ],
        }
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

        # Vimśottarī. The whole ladder hangs off the Moon's position within its
        # nakṣatra, so it is derived from the same longitude shown above.
        try:
            periods = da.vimshottari(
                moment, by_name["Moon"], cycles=1,
                max_level=dasha_levels, year_length=dasha_year,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc))

        start_lord, remaining = da.balance_at_birth(by_name["Moon"])
        out["dasha"] = {
            "system": "vimshottari",
            "yearLength": dasha_year,
            "startingLord": start_lord,
            "balanceAtBirth": {
                "lord": start_lord,
                "fractionRemaining": round(remaining, 6),
                "years": round(da.LORD_YEARS[start_lord] * remaining, 4),
            },
            "active": da.active_chain(periods, moment),
            "periods": [p.to_dict() for p in periods],
        }

        # Dṛṣṭi is asymmetric: `mutual` false means the aspect is not returned.
        out["aspects"] = {
            "basis": "graha_drishti",
            "drishti": [
                {"from": a.from_body, "to": a.to_body, "aspect": a.name,
                 "mutual": a.mutual}
                for a in asp.graha_drishti(by_name)
            ],
        }

    return out


# ── isopsephy / gematria ────────────────────────────────────────────────────

@router.get("/ciphers")
async def list_ciphers() -> dict:
    """
    The bundled catalogue — Greek, Hebrew, English, Coptic, Arabic, Sanskrit.

    Every entry cites a public-domain source. Nothing here is invented.
    """
    from shruti_astro.core.isopsephy import LANGUAGES, catalogue

    return {"languages": LANGUAGES, "ciphers": catalogue()}


@router.get("/isopsephy")
async def isopsephy_endpoint(
    text: str = Query(..., min_length=1, max_length=2000),
    cipher: str = Query("greek-iso"),
    strip_marks: bool = Query(True, description="Fold diacritics and Hebrew pointing"),
) -> dict:
    """
    Sum text under one cipher.

    Unmatched characters are returned rather than silently counted as zero — a
    letter outside the cipher is not worth nothing, and a total whose basis is
    invisible cannot be reproduced.
    """
    from shruti_astro.core.isopsephy import isopsephy as compute
    from shruti_astro.core.katapayadi import encode

    # Sanskrit is positional, not additive. Summing kaṭapayādi produces a
    # number that means nothing, so it never reaches the additive path.
    if cipher == "skt-katapayadi":
        return encode(text)

    try:
        return compute(text, cipher, strip_marks)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ── Hindu calendar ──────────────────────────────────────────────────────────

@router.get("/hindu-calendar")
async def hindu_calendar_endpoint(
    when: str | None = Query(None, description="ISO-8601; defaults to now"),
    reckoning: str = Query("amanta", description="amanta (southern) | purnimanta (northern)"),
    ayanamsa: str = Query("lahiri"),
) -> dict:
    """
    The lunar month, pakṣa and tithi.

    `reckoning` is a real choice, not a preference: a month may end at the new
    moon (amānta, southern) or the full moon (pūrṇimānta, northern). In the dark
    fortnight the two name *different months*, and both are correct where they
    are kept.
    """
    from shruti_astro.core.hindu_calendar import RECKONINGS, hindu_date

    if reckoning not in RECKONINGS:
        raise HTTPException(400, f"reckoning must be one of {list(RECKONINGS)}")
    if ayanamsa not in AYANAMSAS:
        raise HTTPException(400, f"unknown ayanamsa; choose from {sorted(AYANAMSAS)}")

    try:
        d = hindu_date(_moment(when), reckoning, ayanamsa)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    return {
        "reckoning": d.reckoning,
        "month": {"name": d.month, "index": d.month_index,
                  "adhika": d.is_adhika, "kshaya": d.is_kshaya},
        "paksha": d.paksha,
        "tithi": {"index": d.tithi_index, "name": d.tithi_name},
        "years": d.years,
        "lunation": {"start": d.month_start.isoformat(), "end": d.month_end.isoformat()},
    }


@router.get("/reckonings")
async def list_reckonings() -> dict:
    return {
        "reckonings": {
            "amanta": "month ends at the new moon — southern Indian practice",
            "purnimanta": "month ends at the full moon — northern Indian practice",
        }
    }
