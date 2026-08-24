# SPDX-License-Identifier: AGPL-3.0-only
"""Public computation endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Response

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
    """
    Parse a requested instant.

    **The floor is 1 CE, and that is a real limit rather than a choice.**
    Python's `datetime` cannot hold a year below 1 at all — `replace(year=-490)`
    raises — so a BCE date is not expressible anywhere the API takes a
    `datetime`, which is everywhere.

    One consequence is worth stating plainly because it looks like a bug: the
    Attic calendar's "before the Metonic cycle" refusal, which the design lists
    as a cannot-compute state, is UNREACHABLE through the API. Not because the
    check is missing — `_attic_year` raises `BeforeTheCycle` correctly, and it
    is tested directly — but because 432 BCE is on the far side of a floor that
    sits at 1 CE. You cannot ask the question that would trigger it.

    Reaching it needs the core to work in Julian Days rather than datetimes,
    since `swe.julday` takes negative years quite happily. That is a real
    change, not a patch, and it is in the backlog rather than half-done here.
    """
    if not when:
        return datetime.now(timezone.utc)

    if when.lstrip().startswith("-"):
        raise HTTPException(
            400,
            "dates before 1 CE cannot be expressed by this API: the calculation "
            "layer works in datetimes, which have no year below 1. The Attic "
            "calendar refuses years before 432 BCE for a different reason — the "
            "intercalations are not recoverable — but you cannot reach that "
            "refusal from here.",
        )

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
    solar_phase: str = Query("paulus", description="Hellenistic: paulus | lilly1647 | medievalUnattributed"),
    dasha_levels: int = Query(2, ge=1, le=3, description="Vedic: mahā / antara / pratyantara"),
    dasha_year: str = Query("julian", description="Vedic: julian | sidereal | savana"),
    diagram: bool = Query(True, description="include the rendered chart figure"),
    vedic_style: str = Query("north", description="Vedic figure: north | south"),
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
    from shruti_astro.core import solar_phase as sp
    from shruti_astro.core import wheel as wh
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
            if b.name != "Sun":
                # Cazimi / combust / under the beams, by the caller's doctrine —
                # the boundaries are contested and are not ours to standardise.
                ph = sp.solar_phase(b.longitude, by_name["Sun"], solar_phase)
                entry["solarPhase"] = {
                    "state": ph.state, "separation": ph.separation,
                    "doctrine": ph.doctrine, "boundaries": ph.boundaries,
                }
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
        if diagram:
            # Drawn from the same numbers as the tables — a wheel that
            # disagrees with its own table is a second, wrong source.
            out["diagram"] = {
                "kind": "wheel",
                "svg": wh.hellenistic_wheel(
                    pos.ascendant,
                    [{"name": b.name, "longitude": b.longitude,
                      "retrograde": b.retrograde} for b in pos.bodies],
                    out["aspects"]["configurations"],
                ),
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
        if diagram:
            if vedic_style not in ("north", "south"):
                raise HTTPException(400, "vedic_style must be north or south")
            # A square chart, not a relabelled wheel — they are different
            # figures, and a Vedic astrologer notices immediately.
            out["diagram"] = {
                "kind": f"{vedic_style}_indian_square",
                "svg": wh.vedic_square(
                    asc_sign,
                    [{"name": b.name, "longitude": b.longitude} for b in pos.bodies],
                    vedic_style,
                ),
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
    authority: str = Query("drik", description="drik | surya_siddhanta | both"),
) -> dict:
    """
    The lunar month, pakṣa and tithi.

    `reckoning` is a real choice, not a preference: a month may end at the new
    moon (amānta, southern) or the full moon (pūrṇimānta, northern). In the dark
    fortnight the two name *different months*, and both are correct where they
    are kept.
    """
    from shruti_astro.core.hindu_calendar import RECKONINGS, hindu_date
    from shruti_astro.core.surya_siddhanta import AUTHORITIES

    if authority not in (*AUTHORITIES, "both"):
        raise HTTPException(400, f"authority must be one of {[*AUTHORITIES, 'both']}")
    if reckoning not in RECKONINGS:
        raise HTTPException(400, f"reckoning must be one of {list(RECKONINGS)}")
    if ayanamsa not in AYANAMSAS:
        raise HTTPException(400, f"unknown ayanamsa; choose from {sorted(AYANAMSAS)}")

    try:
        d = hindu_date(_moment(when), reckoning, ayanamsa)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    def render(x) -> dict:
        return {
            "month": {"name": x.month, "index": x.month_index,
                      "adhika": x.is_adhika, "kshaya": x.is_kshaya},
            "paksha": x.paksha,
            "tithi": {"index": x.tithi_index, "name": x.tithi_name},
            "lunation": {"start": x.month_start.isoformat(),
                         "end": x.month_end.isoformat()},
        }

    out: dict = {
        "reckoning": d.reckoning,
        "authority": authority,
        "years": d.years,
        **render(d),
    }

    if authority in ("surya_siddhanta", "both"):
        from shruti_astro.core.hindu_calendar import hindu_date_ss

        ss = hindu_date_ss(_moment(when), reckoning)
        if authority == "surya_siddhanta":
            out.update(render(ss))
        else:
            # Both asked for. Present them side by side and say plainly whether
            # they agree — a disagreement is a real state, not an error.
            agree = (d.month == ss.month and d.paksha == ss.paksha
                     and d.tithi_index == ss.tithi_index)
            out["byAuthority"] = {
                "drik": {**render(d), **AUTHORITIES["drik"]},
                "surya_siddhanta": {**render(ss), **AUTHORITIES["surya_siddhanta"]},
            }
            out["authoritiesAgree"] = agree
            if not agree:
                out["disagreementNote"] = (
                    "The two authorities name this day differently. Both are "
                    "given. Which one governs is decided by the people you keep "
                    "the festival with, not by this software."
                )

    return out


@router.get("/doctrine")
async def list_doctrine() -> dict:
    """
    The contested points, and the options for each.

    Where the tradition genuinely holds two opinions the practitioner chooses;
    where it holds one, it is simply implemented. Nothing here is ranked.
    """
    from shruti_astro.core.doctrine import (
        EXALTATION_MODE, PREDOMINATOR, SATURN_EXALTATION_DEGREES,
        SOLAR_PHASE, VENUS_EXALTATION_DEGREES, VOID_OF_COURSE,
    )
    from shruti_astro.core.solar_phase import DESCRIPTIONS

    return {
        "solarPhase": {"options": list(SOLAR_PHASE), "default": "paulus",
                       "descriptions": DESCRIPTIONS},
        "voidOfCourse": {
            "options": list(VOID_OF_COURSE), "default": "thirtyDegrees",
            "descriptions": {
                "thirtyDegrees": "kenodromia — no exact configuration within the "
                                 "Moon's next thirty degrees, sign boundaries crossed",
                "signExit": "no exact configuration before the Moon leaves her sign",
            },
        },
        "predominator": {"options": list(PREDOMINATOR), "default": "valensWholeSign"},
        "exaltationDegrees": {"options": list(EXALTATION_MODE), "default": "signLevel"},
        "saturnExaltationDegree": {"options": list(SATURN_EXALTATION_DEGREES),
                                   "default": 21,
                                   "note": "19 is an OCR artefact and is not storable"},
        "venusExaltationDegree": {"options": list(VENUS_EXALTATION_DEGREES), "default": 27},
        "maltreatmentContestedSextile": {"options": [True, False], "default": True},
    }


@router.get("/void-of-course")
async def void_of_course_endpoint(
    when: str | None = Query(None),
    rule: str = Query("thirtyDegrees", description="thirtyDegrees | signExit"),
) -> dict:
    """
    Whether the Moon is void, under the chosen rule.

    The two rules disagree often and in both directions — measured across a
    sample, on roughly a third of moments. Neither is a refinement of the other.
    """
    from shruti_astro.core.void_of_course import RULES, is_void_of_course

    if rule not in RULES:
        raise HTTPException(400, f"rule must be one of {list(RULES)}")
    return is_void_of_course(_moment(when), rule)


@router.get("/sigil")
async def sigil_endpoint(
    statement: str = Query(..., min_length=1, max_length=500),
    keep_vowels: bool = Query(False),
    enclosure: str = Query("circle", description="none | circle | vesica"),
    line_weight: str = Query("hairline", description="hairline | broad | engraved"),
    svg: bool = Query(True, description="include the rendered SVG"),
) -> dict:
    """
    A sigil by letter elimination, with every step of the reduction shown.

    The figure is **deterministic** — the same statement always draws the same
    sigil — and the statement is **never written into the image**. The method
    exists to make the intent unreadable; a tool that embeds it in metadata has
    undone the work.

    Cannot-compute: the reduction can consume the sentence entirely. That is
    reported with what to do about it, not drawn as an empty circle.
    """
    from shruti_astro.core.sigil import build, to_svg

    try:
        s = build(statement, keep_vowels, enclosure, line_weight)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    out = {
        "steps": [{"label": st.label, "value": st.value, "note": st.note}
                  for st in s.steps],
        "letters": s.letters,
        "pointCount": len(s.points),
        "path": s.path,
        "options": s.options,
        "exhausted": s.exhausted,
        "exhaustedReason": s.exhausted_reason,
    }
    if svg and not s.exhausted:
        out["svg"] = to_svg(s)
    return out


@router.get("/attic-calendar")
async def attic_calendar_endpoint(
    when: str | None = Query(None, description="ISO-8601 date; defaults to today"),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    reckoning: str = Query(
        "conjunction",
        description="conjunction | visibility — how the month is opened",
    ),
) -> dict:
    """
    The Attic calendar of Athens.

    The month opens at the noumenia and runs full (30) or hollow (29) as the
    next conjunction falls. **The last third is counted backwards** — δεκάτη
    φθίνοντος is the tenth *from the end* — and the final day is ἕνη καὶ νέα,
    "old and new", belonging to both months at once.

    **The month opens at a place.** `reckoning=conjunction` opens it the day
    after the conjunction: deterministic, defined at every latitude, and what
    most modern practice uses. `reckoning=visibility` opens it the evening the
    crescent can first be seen from where you are, which is what Athens did.
    They disagree in six months of twelve, and Athens and Sydney disagree in
    seven. Above about 55° the crescent cannot be caught reliably at all; there
    the year is given by conjunction and `reckoning.note` says so.

    Cannot-compute: before 432 BCE the Metonic cycle was not in use and Athens'
    intercalations were magistrates' decisions, argued about at the time and not
    recoverable. Those years are refused rather than invented, and **no archon
    year is ever fabricated**.
    """
    from datetime import date as date_cls

    from shruti_astro.core.attic import BeforeTheCycle, attic_day

    d = _moment(when).date() if when else date_cls.today()
    try:
        a = attic_day(d, lat, lon, reckoning)
    except BeforeTheCycle as exc:
        raise HTTPException(422, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    return {
        "gregorian": a.gregorian.isoformat(),
        "month": {"name": a.month, "greek": a.month_greek, "index": a.month_index,
                  "intercalary": a.is_intercalary,
                  "length": a.month_length, "full": a.is_full},
        "day": {"number": a.day, "greek": a.day_name_greek,
                "transliteration": a.day_name_translit,
                "decad": a.decad, "remaining": a.days_remaining},
        "moonAgeDays": a.moon_age_days,
        "nextNoumenia": a.next_noumenia.isoformat(),
        "observer": {
            "lat": a.latitude, "lon": a.longitude,
            "defaulted": a.location_defaulted,
            "note": ("no location was given, so this is Athens — under "
                     "visibility reckoning half the months of a year open on a "
                     "different day elsewhere")
                    if a.location_defaulted else None,
        },
        "reckoning": {"used": a.reckoning, "note": a.noumenia_note},
        "year": {"months": a.months_in_year, "intercalary": a.year_is_intercalary},
        "archonYear": None,
        "archonNote": "Archon years are not derivable from the astronomy and are never invented here.",
    }


@router.get("/hindu-year")
async def hindu_year_endpoint(
    year: int = Query(..., ge=1, le=9999),
    reckoning: str = Query("amanta"),
    ayanamsa: str = Query("lahiri"),
    authority: str = Query("drik", description="drik | surya_siddhanta"),
) -> dict:
    """
    The year as a table of lunations.

    Thirteen months in an intercalary year, not twelve — the table is walked new
    moon to new moon rather than assumed. An **adhika māsa** is marked and
    flagged `carriesFestivals: false`: observances wait for the *nija* month
    that follows. Marking the repeat but letting festivals fall inside it puts
    every observance a month early, which is worse than not marking it.
    """
    from shruti_astro.core.hindu_calendar import RECKONINGS, hindu_year
    from shruti_astro.core.surya_siddhanta import AUTHORITIES

    if reckoning not in RECKONINGS:
        raise HTTPException(400, f"reckoning must be one of {list(RECKONINGS)}")
    if authority not in AUTHORITIES:
        raise HTTPException(400, f"authority must be one of {list(AUTHORITIES)}")
    if ayanamsa not in AYANAMSAS:
        raise HTTPException(400, f"unknown ayanamsa; choose from {sorted(AYANAMSAS)}")

    try:
        return hindu_year(year, reckoning, ayanamsa, authority)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/authorities")
async def list_authorities() -> dict:
    """
    The two computational authorities, described and **unranked**.

    Dṛk gaṇita agrees with observation. Sūrya Siddhānta agrees with the
    tradition's own tables. Where they disagree about a festival date, both are
    shown — the software does not get to decide which almanac a household keeps.
    """
    from shruti_astro.core.surya_siddhanta import AUTHORITIES

    return {"authorities": AUTHORITIES}


@router.get("/reckonings")
async def list_reckonings() -> dict:
    return {
        "reckonings": {
            "amanta": "month ends at the new moon — southern Indian practice",
            "purnimanta": "month ends at the full moon — northern Indian practice",
        }
    }


# ── stations ────────────────────────────────────────────────────────────────

@router.get("/stations")
async def stations_endpoint(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    start: str | None = Query(None, description="ISO date; defaults to today"),
    days: int = Query(1, ge=1, le=31),
    body: str = Query("sun", description="sun | moon"),
    preset: str = Query("none", description="hellenic | thelemic | none"),
) -> dict:
    """
    The four daily stations, for up to a month.

    Solar: sunrise · noon · sunset · midnight. Lunar: moonrise · culmination ·
    moonset · nadir.

    **Noon and midnight are meridian transits, not clock times.** They drift up
    to a quarter of an hour either side of 12:00 across the year — the equation
    of time — and further still where a place sits away from its zone meridian.
    A rite kept by the clock is kept at the wrong moment.

    A station that does not occur reports `occurred: false` with a reason. The
    Moon skips a rise or a set regularly; that is the sky, not missing data.
    """
    from datetime import date as date_cls

    from shruti_astro.core.stations import MAX_DAYS, PRESETS, stations_for_range

    if body not in ("sun", "moon"):
        raise HTTPException(400, "body must be 'sun' or 'moon'")
    if preset not in PRESETS:
        raise HTTPException(400, f"unknown preset; choose from {sorted(PRESETS)}")

    begin = _moment(start).date() if start else date_cls.today()
    try:
        rows = stations_for_range(begin, days, lat, lon, body, preset)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    return {
        "body": body,
        "preset": preset,
        "location": {"lat": lat, "lon": lon},
        "start": begin.isoformat(),
        "days": days,
        "maxDays": MAX_DAYS,
        "table": [
            {
                "date": d.date.isoformat(),
                "stations": [
                    {"name": s.name, "at": s.at.isoformat() if s.at else None,
                     "occurred": s.occurred, "absentReason": s.absent_reason,
                     "dedication": s.dedication}
                    for s in d.stations
                ],
                # Moon only. The lunar tracker is designed around a phase
                # column beside the times — a moonrise means something
                # different at the full than at the dark.
                **({"phase": d.phase,
                    "moonAgeDays": round(d.moon_age_days, 2)
                    if d.moon_age_days is not None else None,
                    "illumination": round(d.illumination, 3)
                    if d.illumination is not None else None}
                   if d.body == "moon" else {}),
            }
            for d in rows
        ],
    }


@router.get("/stations/next")
async def next_station_endpoint(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    body: str = Query("sun"),
    preset: str = Query("none"),
    when: str | None = Query(None),
) -> dict:
    """
    The next station after now — what someone opening the page actually wants
    before they want a table.
    """
    from shruti_astro.core.stations import next_station

    if body not in ("sun", "moon"):
        raise HTTPException(400, "body must be 'sun' or 'moon'")

    moment = _moment(when)
    found = next_station(moment, lat, lon, body, preset)
    if found is None:
        raise HTTPException(
            422, "no station of that body occurs within the next three days here"
        )
    station, day = found
    return {
        "body": body,
        "name": station.name,
        "at": station.at.isoformat(),
        "secondsAway": int((station.at - moment).total_seconds()),
        "dedication": station.dedication,
        "onDate": day.date.isoformat(),
    }


@router.get("/stations/ical")
async def stations_ical(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    start: str | None = Query(None),
    days: int = Query(31, ge=1, le=31),
    body: str = Query("sun"),
    preset: str = Query("none"),
    alarm: int | None = Query(10, ge=0, le=120, description="minutes before; 0 disables"),
) -> Response:
    """
    The same stations as an iCalendar feed.

    **Subscribe to this URL rather than downloading it.** A download is a
    snapshot that goes stale and never gains next month's times; a subscription
    is refetched and stays right. The subscription is what actually produces the
    notification someone is trying to set.

    Event UIDs are stable for a given station, instant and place, so a refetch
    updates events instead of accumulating duplicates.
    """
    from datetime import date as date_cls

    from shruti_astro.core.ical import to_ical
    from shruti_astro.core.stations import PRESETS, stations_for_range

    if body not in ("sun", "moon"):
        raise HTTPException(400, "body must be 'sun' or 'moon'")
    if preset not in PRESETS:
        raise HTTPException(400, f"unknown preset; choose from {sorted(PRESETS)}")

    begin = _moment(start).date() if start else date_cls.today()
    try:
        rows = stations_for_range(begin, days, lat, lon, body, preset)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    ics = to_ical(rows, lat, lon, alarm_minutes_before=(alarm or None))
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'inline; filename="{body}-stations.ics"',
            "Cache-Control": "public, max-age=3600",
        },
    )


# ── day at a glance ─────────────────────────────────────────────────────────

@router.get("/today")
async def today(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    when: str | None = Query(None, description="ISO-8601; defaults to now"),
    ayanamsa: str = Query("lahiri"),
    preset: str = Query("none", description="hellenic | thelemic | none"),
    natal: str | None = Query(
        None,
        description="Birth moment as ISO-8601 with offset. Adds transits.",
    ),
    natal_lat: float | None = Query(None, ge=-90, le=90),
    natal_lon: float | None = Query(None, ge=-180, le=180),
) -> dict:
    """
    What the sky is doing right now, here.

    Everything on this page works from a location alone. `natal` is optional and
    adds transits — the page is meant to be useful before anyone signs up,
    because a page that is only a teaser for signing up gets no signups.

    Each block degrades on its own. A polar latitude loses stations and
    planetary hours but keeps the luminaries, the sky and the reckonings; a
    nativity without a birth time keeps the planetary transits and marks the
    angular ones undefined. **No block failing takes another down.**
    """
    from datetime import timezone as _tz

    from shruti_astro.core import hellenistic as he
    from shruti_astro.core import vedic as ve
    from shruti_astro.core.attic import BeforeTheCycle, attic_day
    from shruti_astro.core.ephemeris import SunNeverRose, chart_positions, sun_events
    from shruti_astro.core.hindu_calendar import hindu_date
    from shruti_astro.core.planetary_hours import build_hours, current_hour
    from shruti_astro.core.stations import PRESETS, next_station, stations_for_day

    if ayanamsa not in AYANAMSAS:
        raise HTTPException(400, f"unknown ayanamsa; choose from {sorted(AYANAMSAS)}")
    if preset not in PRESETS:
        raise HTTPException(400, f"unknown preset; choose from {sorted(PRESETS)}")

    moment = _moment(when)
    undefined: list[str] = []

    def _thelemic_block(m) -> dict:
        """
        The Thelemic date — one of the four reckonings /today is designed to
        carry. It is written as the luminaries rather than as a number, and its
        year turns at the March equinox rather than at midnight on 1 January.
        """
        from shruti_astro.core.thelemic import thelemic_date

        t = thelemic_date(m)
        return {
            "sun": {"sign": t.sun_sign, "degree": t.sun_degree},
            "moon": {"sign": t.moon_sign, "degree": t.moon_degree},
            "year": t.year, "cycle": t.cycle, "yearInCycle": t.year_in_cycle,
            "anno": t.anno, "formatted": t.formatted,
        }

    # ── the luminaries ──────────────────────────────────────────────────────
    pos = chart_positions(moment, lat, lon, sidereal=False)
    by_name = {b.name: b for b in pos.bodies}
    sid = chart_positions(moment, lat, lon, sidereal=True, ayanamsa=ayanamsa)
    sid_by = {b.name: b.longitude for b in sid.bodies}

    def luminary(name: str) -> dict:
        b = by_name[name]
        return {
            "tropical": {"sign": he.SIGNS[he.sign_of(b.longitude)],
                         "degree": round(he.degree_in_sign(b.longitude), 4),
                         "longitude": round(b.longitude, 6)},
            "sidereal": {"rashi": ve.rashi(sid_by[name])["name"],
                         "degree": round(sid_by[name] % 30, 4),
                         "nakshatra": ve.nakshatra_of(sid_by[name])["name"]},
            "speedPerDay": round(b.speed, 4),
        }

    # ── stations ────────────────────────────────────────────────────────────
    stations: dict = {}
    for body in ("sun", "moon"):
        try:
            day = stations_for_day(moment.date(), lat, lon, body, preset)
            found = next_station(moment, lat, lon, body, preset)
            stations[body] = {
                "today": [
                    {"name": s.name, "at": s.at.isoformat() if s.at else None,
                     "occurred": s.occurred, "absentReason": s.absent_reason,
                     "dedication": s.dedication}
                    for s in day.stations
                ],
                "next": None if found is None else {
                    "name": found[0].name, "at": found[0].at.isoformat(),
                    "secondsAway": int((found[0].at - moment).total_seconds()),
                    "dedication": found[0].dedication,
                },
            }
        except Exception:                          # noqa: BLE001 — degrade alone
            stations[body] = {"today": [], "next": None}
            undefined.append(f"{body} stations could not be computed here")

    # ── planetary hours ─────────────────────────────────────────────────────
    hours: dict | None = None
    try:
        sunrise, sunset, next_sunrise = sun_events(moment, lat, lon)
        built = build_hours(sunrise, sunset, next_sunrise, sunrise.weekday())
        now_hour = current_hour(built, moment)
        idx = built.index(now_hour) if now_hour else None
        upcoming = built[idx + 1] if idx is not None and idx + 1 < len(built) else None
        hours = {
            "current": None if now_hour is None else {
                "index": now_hour.index, "ruler": now_hour.ruler,
                "isNight": now_hour.is_night,
                "startsAt": now_hour.starts_at.isoformat(),
                "endsAt": now_hour.ends_at.isoformat(),
            },
            # The next hour is the point — people plan against the coming hour,
            # not the present one.
            "next": None if upcoming is None else {
                "index": upcoming.index, "ruler": upcoming.ruler,
                "isNight": upcoming.is_night,
                "startsAt": upcoming.starts_at.isoformat(),
                "endsAt": upcoming.ends_at.isoformat(),
            },
        }
    except SunNeverRose as exc:
        undefined.append(f"planetary hours: {exc}")

    # ── reckonings ──────────────────────────────────────────────────────────
    reckonings: dict = {"gregorian": moment.date().isoformat()}
    try:
        hd = hindu_date(moment, "amanta", ayanamsa)
        reckonings["hindu"] = {
            "month": hd.month, "paksha": hd.paksha, "tithi": hd.tithi_name,
            "vikrama": hd.years["vikrama"], "shaka": hd.years["shaka"],
        }
    except Exception:                              # noqa: BLE001
        undefined.append("the Hindu date could not be computed")
    try:
        a = attic_day(moment.date(), lat, lon)
        reckonings["attic"] = {
            "month": a.month, "greek": a.month_greek,
            "day": a.day_name_greek, "moonAgeDays": a.moon_age_days,
        }
    except (BeforeTheCycle, ValueError) as exc:
        undefined.append(f"the Attic date: {exc}")
    try:
        reckonings["thelemic"] = _thelemic_block(moment)
    except Exception:                              # noqa: BLE001
        undefined.append("the Thelemic date could not be computed")

    # ── transits, only with a nativity ──────────────────────────────────────
    transits: dict | None = None
    if natal:
        if natal_lat is None or natal_lon is None:
            raise HTTPException(400, "natal requires natal_lat and natal_lon")
        birth = _moment(natal)
        n = chart_positions(birth, natal_lat, natal_lon, sidereal=False)
        natal_by = {b.name: b.longitude for b in n.bodies}

        from shruti_astro.core import aspects as asp

        combined = {f"transit {k}": v.longitude for k, v in by_name.items()}
        combined.update({f"natal {k}": v for k, v in natal_by.items()})
        crossing = [
            {"from": a.from_body, "to": a.to_body, "aspect": a.name,
             "separationSigns": a.separation_signs}
            for a in asp.whole_sign_aspects(combined)
            if a.from_body.startswith("transit ") != a.to_body.startswith("transit ")
        ]
        transits = {
            "natalAngles": {
                "ascendant": round(n.ascendant, 6),
                "midheaven": round(n.midheaven, 6),
            },
            "configurations": crossing,
            "note": (
                "Angular transits depend on the birth time. If it is uncertain, "
                "treat the ascendant, midheaven and house transits as undefined "
                "— the ascendant moves a degree every four minutes."
            ),
        }

    return {
        "at": moment.isoformat(),
        "location": {"lat": lat, "lon": lon},
        "sun": luminary("Sun"),
        "moon": luminary("Moon"),
        "stations": stations,
        "planetaryHours": hours,
        "reckonings": reckonings,
        "sky": {
            "ascendant": round(pos.ascendant, 6),
            "midheaven": round(pos.midheaven, 6),
            "bodies": [
                {"name": b.name, "longitude": round(b.longitude, 6),
                 "sign": he.SIGNS[he.sign_of(b.longitude)],
                 "retrograde": b.retrograde}
                for b in pos.bodies
            ],
        },
        "transits": transits,
        # Present so a degraded block is visible rather than silently missing.
        "undefined": undefined,
    }


# ── festivals ───────────────────────────────────────────────────────────────

@router.get("/festivals")
async def festivals(
    tradition: str = Query("attic", description="attic | hindu"),
    year: int = Query(..., ge=1, le=9999),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    reckoning: str | None = Query(
        None,
        description="Attic only: conjunction | visibility — how the month opens",
    ),
    school: str | None = Query(
        None,
        description="Pick one side of a contested reckoning — e.g. smarta, "
                    "vaishnava, nishitha. Omit to receive every variant.",
    ),
) -> dict:
    """
    A year of festivals, with the undatable ones reported rather than hidden.

    **Verification status travels with the response.** The Attic corpus has been
    audited adversarially; the Hindu one has not yet, and says so in
    `verificationNote`. A consumer is entitled to know which it is reading.

    **Give a location.** A tithi is current at an instant, and which civil day
    owns it depends on when the Sun rises where you are. For 2026, five of seven
    major Hindu festivals fall on a different day in Sydney than in Ujjain.
    Without lat/lon this answers for Ujjain and says so — a default, not an
    answer about you.

    **`school` picks a side where traditions disagree.** Omit it and every
    variant is returned, labelled. Smārta and Vaiṣṇava keep a daśamī-viddha
    ekādaśī on different days and pañcāṅgas print both; choosing one silently
    would make that ruling for the practitioner.

    `undated` is not an error list. Several Attic festivals are known to have
    happened and cannot be dated — the entry carries the reconstructions and
    who proposed them. Dropping them would leave the corpus looking smaller and
    more certain than it is.
    """
    from shruti_astro.core.festival_registry import CORPORA, year as resolve_year

    if tradition not in CORPORA:
        raise HTTPException(400, f"tradition must be one of {sorted(CORPORA)}")
    try:
        kw = {"reckoning": reckoning} if reckoning else {}
        return resolve_year(tradition, year, lat=lat, lon=lon, school=school, **kw)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/festivals/traditions")
async def festival_traditions() -> dict:
    from shruti_astro.core.festival_registry import CORPORA, load

    return {
        "traditions": {
            name: {
                "entries": len(load(name).entries),
                "verified": spec["verified"],
                "note": spec["note"],
            }
            for name, spec in CORPORA.items()
        }
    }
