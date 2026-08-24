# SPDX-License-Identifier: AGPL-3.0-only
"""
Resolving festival anchors to actual days.

A festival in a portable pack is stored as an **anchor**, not a date — "Kārtika
Kṛṣṇa 15" rather than "12 November 2026" — because the date is a function of the
year and the anchor is not. This module turns one into the other.

The rule that decides which civil day owns an observance is not obvious and is
where most implementations go wrong: **a tithi belongs to the sunrise it is
current at.** Tithis are not 24 hours long, so one can begin and end between two
sunrises and own no day at all (*kṣaya*), or span two sunrises and be counted
twice (*vṛddhi*). Both are reported rather than smoothed away.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone

from shruti_astro.core.hindu_calendar import MONTHS, hindu_date
from shruti_astro.core.panchanga import tithi as tithi_of
from shruti_astro.core.ephemeris import SunNeverRose, longitudes, sun_events

# Ujjain — the classical prime meridian of Indian astronomy, and the default
# when a pack does not name a place. Stated rather than assumed.
UJJAIN = (23.1765, 75.7885)

# **Which moment of the day owns an observance is not one rule.**
#
# Most festivals go to the tithi current at sunrise. But Dīpāvalī is kept on the
# amāvāsyā prevailing at *pradoṣa*, the evening twilight; Mahā Śivarātri and
# Janmāṣṭamī on the tithi at *niśītha*, true midnight; Vijayadaśamī and śrāddha
# rites at *aparāhṇa*, the afternoon. Applying the sunrise rule to all of them
# puts Dīpāvalī and Śivarātri each a day late, which is exactly what a wrong
# almanac does.
#
# Fractions are of the daylight span (sunrise → sunset) unless noted.
DAY_RULES = {
    "sunrise": None,                    # the tithi at sunrise — the default
    "arunodaya": -0.08,                 # before dawn, roughly four ghaṭikās
    "pratahkala": 0.1,                  # early morning
    "purvahna": 0.25,                   # forenoon, the second of five parts
    "madhyahna": 0.5,                   # midday
    "aparahna": 0.75,                   # afternoon, the fourth of five parts
    "pradosha": 1.0,                    # sunset, running into the evening
    "nishitha": "midnight",             # true midnight, between the sunrises
}

# candrodaya — moonrise — is deliberately NOT here. It is not a fraction of the
# daylight span like the others: it needs a moonrise computation, and moonrise
# moves enough with longitude that the same festival genuinely falls on
# different civil days in different cities. That is a true fact rather than a
# defect, but expressing it means returning two answers with the place attached,
# and a single dayRule value cannot say that. Entries that need it carry
# dayRuleUnmodelled: "candrodaya" until there is a surface that can show it.


# A recurring anchor names no month: it happens every lunation. Ekādaśī twice a
# month, Pradoṣa twice, Saṅkaṣṭī Caturthī once. These matter more for daily
# practice than the annual festivals do, and there are more of them in a year
# than of everything else combined.
RECURRING = "*"

# A few observances exist ONLY in an intercalary month. Padminī and Paramā
# Ekādaśī are the pair: an adhika māsa has its own two Ekādaśīs, and they occur
# in no ordinary year at all. This is the exact opposite of the rule that
# festivals wait for the nija month — these belong to the repeat itself.
ADHIKA_ONLY = "adhika"


@dataclass
class Resolved:
    key: str
    name: str
    date: date_cls | None
    anchor: dict
    note: str = ""
    skipped: bool = False
    skipped_reason: str = ""
    doubled: bool = False
    end: date_cls | None = None
    span_days: int | None = None
    span_note: str = ""


def _reckoning_moment(day: date_cls, lat: float, lon: float, rule: str) -> datetime | None:
    """The instant of `day` at which the observance's tithi is judged."""
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)
    try:
        sunrise, sunset, next_sunrise = sun_events(noon, lat, lon, "hindu")
    except SunNeverRose:
        return None

    spec = DAY_RULES.get(rule)
    if spec is None:
        return sunrise
    if spec == "midnight":
        return sunrise + (next_sunrise - sunrise) / 2
    return sunrise + (sunset - sunrise) * spec


def _is_bhadra(moment: datetime) -> bool:
    """
    Whether the moment falls in **bhadrā** — the viṣṭi karaṇa.

    Bhadrā is the seventh of the movable karaṇas, and several observances are
    explicitly forbidden during it: Holikā Dahan must not be lit in bhadrā, and
    the Rakṣā Bandhan thread must not be tied in it. Both are then deferred past
    it, which routinely moves them to the following civil day.

    This is computable rather than a convention, because viṣṭi is one of the
    five limbs the pañcāṅga already yields.
    """
    from shruti_astro.core.panchanga import karana as karana_of

    L = longitudes(moment)
    return karana_of(L.sun_tropical, L.moon_tropical).name == "Viṣṭi"


def _tithi_at(day: date_cls, lat: float, lon: float,
              rule: str = "sunrise") -> tuple[int, str] | None:
    """(tithi index 1..30, pakṣa) at the moment this observance is judged by."""
    moment = _reckoning_moment(day, lat, lon, rule)
    if moment is None:
        return None
    L = longitudes(moment)
    t = tithi_of(L.sun_tropical, L.moon_tropical)
    return t.index, ("Śukla" if t.index <= 15 else "Kṛṣṇa")


def _ksaya_day(
    gregorian_year: int, target: int, lat: float, lon: float,
    month: str | None = None, reckoning: str = "amanta",
) -> date_cls | None:
    """
    The day a **kṣaya tithi** was current, when no day owns it at sunrise.

    A kṣaya tithi begins after one sunrise and ends before the next, so no
    civil day carries it at any reckoning moment and the ordinary search finds
    nothing. The observance does not stop happening: it is kept on the day the
    tithi was current. Without this, nineteen entries drop out of the calendar
    in the years their tithi is short — Śāradīya Navarātri vanishes outright in
    2027, which is not a defensible thing for a festival calendar to do.
    """
    d = date_cls(gregorian_year, 1, 1)
    end = date_cls(gregorian_year, 12, 31)
    while d <= end:
        a = _tithi_at(d, lat, lon, "sunrise")
        b = _tithi_at(d + timedelta(days=1), lat, lon, "sunrise")
        if a and b:
            # The tithi began after this sunrise and ended before the next.
            step = (b[0] - a[0]) % 30
            offset = (target - a[0]) % 30
            if 0 < offset < step:
                if month is None:
                    return d
                # The month is judged at BOTH ends of the day, not just at
                # sunrise. A kṣaya śukla pratipadā still shows the previous
                # month's amāvāsyā at sunrise, so a sunrise-only check rejects
                # the very day it is looking for — which is why every
                # pratipadā entry stayed lost.
                for edge in (d, d + timedelta(days=1)):
                    moment = _reckoning_moment(edge, lat, lon, "sunrise")
                    if moment is None:
                        continue
                    hd = hindu_date(moment, reckoning)
                    if hd.month == month and not hd.is_adhika:
                        return d
        d += timedelta(days=1)
    return None


def span_end(
    start: date_cls, tithis: int, lat: float, lon: float, rule: str = "sunrise",
) -> tuple[date_cls, int, str]:
    """
    Where a run of `tithis` tithis beginning on `start` actually ends.

    **A nine-day festival is not nine days.** Navarātri is nine *tithis*, and
    the corpus notes have said so all along: a kṣaya tithi — one that begins
    and ends between two sunrises, so no civil day owns it — compresses the run
    to eight, and a vṛddhi tithi, which owns two sunrises, stretches it to ten.
    Printing the declared count as though it were a span of days is wrong in
    any year the moon does not cooperate, which is most of them.

    Returns the last civil day, the number of civil days, and a note where the
    two counts disagree.
    """
    if tithis <= 1:
        return start, 1, ""

    first = _tithi_at(start, lat, lon, rule)
    if first is None:
        return start, tithis, ""

    prev = first[0]
    advanced = 0
    end = start
    d = start
    # A run cannot outlast its tithis by more than the vṛddhi allowance.
    for _ in range(tithis + 4):
        d += timedelta(days=1)
        cur = _tithi_at(d, lat, lon, rule)
        if cur is None:
            break
        step = (cur[0] - prev) % 30
        advanced += step
        prev = cur[0]
        if advanced > tithis - 1:
            break
        end = d

    days = (end - start).days + 1
    note = ""
    if days != tithis:
        which = "a kṣaya tithi shortens" if days < tithis else "a vṛddhi tithi stretches"
        note = (f"{tithis} tithis, but {which} the run to {days} civil days "
                f"this year")
    return end, days, note


def resolve_lunar(
    anchor: dict, gregorian_year: int, lat: float = UJJAIN[0], lon: float = UJJAIN[1]
) -> Resolved:
    """
    A Hindu lunar anchor → the civil day that owns it.

    `anchor` carries month, paksha, tithi, and optionally reckoning. Scans the
    year for the day whose *sunrise* falls in the named month, pakṣa and tithi.
    """
    month = anchor["month"]
    want_tithi = int(anchor["tithi"])
    reckoning = anchor.get("reckoning", "amanta")
    rule = anchor.get("dayRule", "sunrise")

    if month not in MONTHS:
        raise ValueError(f"unknown lunar month: {month}")
    if rule not in DAY_RULES:
        raise ValueError(f"unknown day rule: {rule}; choose from {sorted(DAY_RULES)}")

    # Normalise the pakṣa to ASCII before testing it. Comparing an incoming
    # "shukla" against the transliterated "Śukla" silently sends every bright
    # fortnight anchor to the wrong tithi — it did, until this was fixed.
    paksha = anchor["paksha"].strip().lower()
    if paksha.startswith(("s", "ś", "\u015b")):
        bright = True
    elif paksha.startswith("k"):
        bright = False
    else:
        raise ValueError(f"paksha must be shukla or krishna, got {anchor['paksha']!r}")

    # Absolute tithi index: Śukla 1..15, Kṛṣṇa 16..30.
    target = want_tithi if bright else want_tithi + 15

    avoid_bhadra = bool(anchor.get("avoidBhadra"))

    # Daśamī-viddha: an ekādaśī "pierced" by the tenth. Where the tithi spans
    # two sunrises, Smārtas fast on the first day and Vaiṣṇavas on the second,
    # and pañcāṅgas print both as separate dated calendars. This models the
    # doubled case, which is where the two traditions actually diverge; it does
    # not attempt the fuller nirṇaya, and says so rather than implying it does.
    avoid_dashami_viddha = bool(anchor.get("avoidDashamiViddha"))

    hits: list[date_cls] = []
    d = date_cls(gregorian_year, 1, 1)
    end = date_cls(gregorian_year, 12, 31)
    while d <= end:
        got = _tithi_at(d, lat, lon, rule)
        if got is not None and got[0] == target:
            # The month must be judged at the SAME moment as the tithi. Reading
            # the tithi at pradoṣa and the month at noon can straddle a new moon
            # and put a festival a whole lunation out — it did.
            moment = _reckoning_moment(d, lat, lon, rule)
            hd = hindu_date(moment, reckoning)
            # Observances never fall in an intercalary month — they wait for
            # the nija month that follows.
            if hd.month == month and not hd.is_adhika:
                hits.append(d)
        d += timedelta(days=1)

    if avoid_dashami_viddha and len(hits) > 1:
        # Two sunrises carried the tithi, so the first is touched by the tenth.
        # The Vaiṣṇava observance takes the second.
        hits = hits[1:]

    # Bhadrā does not cancel the rite, it postpones it. Where bhadrā covers the
    # moment the observance would be kept, it waits until bhadrā ends — which
    # falls in the following night and so lands on the next civil day. Skipping
    # the day outright (the first thing tried) loses the festival entirely,
    # because the tithi has usually ended by the next day's reckoning moment.
    deferred_from = None
    if avoid_bhadra and hits:
        first = hits[0]
        moment = _reckoning_moment(first, lat, lon, rule)
        if moment is not None and _is_bhadra(moment):
            deferred_from = first
            hits = [first + timedelta(days=1)] + hits[1:]

    if not hits:
        # A refined rule can find no day at all: the tithi begins and ends
        # between two consecutive madhyāhna or pradoṣa moments, so no day
        # carries it AT THAT MOMENT even though every day carries it at some
        # moment. Measured over 2026–30, this makes Rāma Navamī vanish in 2029
        # and Dhanteras in 2028 and 2029.
        #
        # The observance still happens. Falling back to sunrise and saying so is
        # right: a festival missing from the calendar is a worse error than one
        # placed by the base rule, and silently dropping it hides the fact that
        # the refinement did not apply.
        if rule != "sunrise":
            fallback = resolve_lunar(
                {**anchor, "dayRule": "sunrise"}, gregorian_year, lat, lon
            )
            if fallback.date is not None:
                fallback.note = (
                    f"the {rule} rule found no day this year — the tithi began "
                    f"and ended between two {rule} moments — so this falls back "
                    f"to the tithi at sunrise"
                )
                fallback.anchor = anchor
                return fallback

        # Nothing owns the tithi at sunrise either, so it is genuinely kṣaya:
        # it began and ended between two sunrises. The rite is still kept, on
        # the day the tithi was current.
        short = _ksaya_day(gregorian_year, target, lat, lon, month, reckoning)
        if short is not None:
            return Resolved(
                key=anchor.get("key", ""), name=anchor.get("name", ""),
                date=short, anchor=anchor,
                note=(f"{anchor['paksha']} {want_tithi} is kṣaya this year — it "
                      f"began and ended between two sunrises, so no day owns it "
                      f"at sunrise. Kept on the day it was current."),
            )

        return Resolved(
            key=anchor.get("key", ""), name=anchor.get("name", ""), date=None,
            anchor=anchor, skipped=True,
            skipped_reason=(
                f"no day in {gregorian_year} carried {anchor['paksha']} {want_tithi} "
                f"of {month} at any reckoning moment, and the tithi was not "
                f"current on any day of the month either"
            ),
        )

    note = f"judged at {rule}"
    if avoid_dashami_viddha:
        note += "; daśamī-viddha deferred, as the Vaiṣṇava reckoning keeps it"
    if deferred_from is not None:
        note += (f"; deferred from {deferred_from.isoformat()} because bhadrā "
                 f"(viṣṭi karaṇa) covered that moment")
    elif len(hits) > 1:
        note += ("; the tithi spanned two reckoning moments and is counted "
                 "twice (vṛddhi)")

    return Resolved(
        key=anchor.get("key", ""), name=anchor.get("name", ""),
        date=hits[0], anchor=anchor,
        doubled=len(hits) > 1 and deferred_from is None,
        note=note,
    )


def resolve_crescent_monthly(
    anchor: dict, gregorian_year: int, lat: float | None = None,
    lon: float | None = None, reckoning: str = "conjunction",
) -> list[Resolved]:
    """
    An Attic observance kept every month — the noumenia, the days sacred to
    Hermes, Artemis, Apollo, Poseidon, and Hekate's Deipnon.

    These matter far more for daily practice than the annual festivals, and most
    festival lists omit them entirely.

    Two Attic peculiarities are handled here:

    **`dayFromEnd`** counts backwards, because the last third of an Attic month
    does. The Deipnon is the *last* day — ἕνη καὶ νέα — which is day 30 of a full
    month and day 29 of a hollow one. Anchoring it to "30" would silently skip
    every hollow month, which is about half of them.

    **Hollow months are contested.** Pritchett and Meritt disagree about which
    day a hollow month omits. Where the entry says so, the note carries it
    forward rather than the code picking a side.
    """
    from shruti_astro.core.attic import attic_day

    from_end = anchor.get("dayFromEnd")
    fixed_day = anchor.get("day")
    if from_end is None and fixed_day is None:
        raise ValueError("a monthly crescent anchor needs day or dayFromEnd")

    contested = anchor.get("hollowMonthRuleContested")
    out: list[Resolved] = []
    seen_months: set[tuple[str, int]] = set()

    d = date_cls(gregorian_year, 1, 1)
    end = date_cls(gregorian_year, 12, 31)
    while d <= end:
        a = attic_day(d, lat, lon, reckoning)
        want = (a.month_length - from_end + 1) if from_end is not None else fixed_day
        if a.day == want:
            marker = (a.month, a.day)
            if marker not in seen_months:
                seen_months.add(marker)
                note = f"{a.month_greek} {a.day_name_greek}"
                if from_end is not None and not a.is_full:
                    note += f" (hollow month: day {a.month_length}, not {fixed_day or 30})"
                    if contested:
                        note += f"; contested — {contested}"
                out.append(Resolved(key=anchor.get("key", ""),
                                    name=anchor.get("name", ""),
                                    date=d, anchor=anchor, note=note))
        d += timedelta(days=1)
    return out


def resolve_crescent(
    anchor: dict, gregorian_year: int, lat: float | None = None,
    lon: float | None = None, reckoning: str = "conjunction",
) -> Resolved:
    """
    An Attic anchor → the civil day.

    Months open at the noumenia, so this walks the Attic year rather than
    counting from a fixed point.
    """
    from shruti_astro.core.attic import attic_day

    month = anchor["month"]

    # A day the sources do not give. Returning the candidates rather than a
    # guess is the whole point — several of these festivals are known to have
    # happened and simply cannot be dated, and a confident wrong date is worse
    # than an honest absent one.
    if "day" not in anchor:
        candidates = anchor.get("dayCandidates") or []
        reconstructions = anchor.get("dayReconstructions") or []
        detail = anchor.get("dayBasis") or "no day is given by any source"
        if reconstructions:
            named = "; ".join(
                f"{r.get('author', 'unattributed')}: "
                f"{'–'.join(str(x) for x in r.get('days', []))}"
                for r in reconstructions
            )
            detail += f". Reconstructions differ — {named}"
        elif candidates:
            detail += f". Candidate days: {', '.join(str(c) for c in candidates)}"
        return Resolved(
            key=anchor.get("key", ""), name=anchor.get("name", ""), date=None,
            anchor=anchor, skipped=True,
            skipped_reason=f"{month}, day unknown — {detail}",
        )

    want_day = int(anchor["day"])

    d = date_cls(gregorian_year, 1, 1)
    end = date_cls(gregorian_year, 12, 31)
    while d <= end:
        a = attic_day(d, lat, lon, reckoning)
        if a.month == month and a.day == want_day:
            return Resolved(key=anchor.get("key", ""), name=anchor.get("name", ""),
                            date=d, anchor=anchor)
        d += timedelta(days=1)

    # Say WHICH reason, rather than offering two and letting the reader pick.
    # A hollow month has 29 days, so it can only explain a missing day 30 —
    # offering it for day 26 is an explanation that cannot be true.
    if want_day == 30:
        why = (f"{month} ran hollow in {gregorian_year} and has no day 30, "
               f"or fell outside the Gregorian year")
    else:
        why = (f"{month} {want_day} fell outside the Gregorian year "
               f"{gregorian_year} — Attic months straddle the civil year, so a "
               f"month near either end lands partly in the neighbouring one")
    return Resolved(
        key=anchor.get("key", ""), name=anchor.get("name", ""), date=None,
        anchor=anchor, skipped=True, skipped_reason=why,
    )


def resolve_recurring(
    anchor: dict, gregorian_year: int, lat: float = UJJAIN[0], lon: float = UJJAIN[1]
) -> list[Resolved]:
    """
    Every occurrence in the year of an observance that recurs each lunation.

    `month` is "*". Unlike an annual anchor this returns a **list** — Ekādaśī
    falls about twenty-four times a year, and collapsing that to one date would
    be a different and wrong answer rather than a partial one.

    Adhika months are included: a recurring observance is not a festival waiting
    for the nija month, it simply happens again.
    """
    paksha_raw = anchor["paksha"].strip().lower()
    if paksha_raw.startswith(("s", "ś", "\u015b")):
        bright = True
    elif paksha_raw.startswith("k"):
        bright = False
    else:
        raise ValueError(f"paksha must be shukla or krishna, got {anchor['paksha']!r}")

    want_tithi = int(anchor["tithi"])
    rule = anchor.get("dayRule", "sunrise")
    if rule not in DAY_RULES:
        raise ValueError(f"unknown day rule: {rule}; choose from {sorted(DAY_RULES)}")

    target = want_tithi if bright else want_tithi + 15

    adhika_only = anchor.get("month") == ADHIKA_ONLY

    out: list[Resolved] = []
    d = date_cls(gregorian_year, 1, 1)
    end = date_cls(gregorian_year, 12, 31)
    while d <= end:
        got = _tithi_at(d, lat, lon, rule)
        if got is not None and got[0] == target:
            moment = _reckoning_moment(d, lat, lon, rule)
            hd = hindu_date(moment, anchor.get("reckoning", "amanta"))
            if not adhika_only or hd.is_adhika:
                out.append(Resolved(
                    key=anchor.get("key", ""), name=anchor.get("name", ""),
                    date=d, anchor=anchor,
                    note=(f"{'Adhika ' if hd.is_adhika else ''}{hd.month} "
                          f"{hd.paksha}, judged at {rule}"),
                ))
        d += timedelta(days=1)

    # Two consecutive occurrences mean the tithi spanned two reckoning moments
    # — vṛddhi. Both are marked rather than one being dropped, because the
    # choice between them is a real doctrinal one: on a doubled Ekādaśī the
    # Smārta and Vaiṣṇava traditions fast on different days. Picking one here
    # would be making that ruling on the practitioner's behalf.
    for earlier, later in zip(out, out[1:]):
        if (later.date - earlier.date).days == 1:
            earlier.doubled = later.doubled = True
            for r in (earlier, later):
                r.note += ("; vṛddhi — the tithi spans two days and the "
                           "traditions differ on which is kept")

    # The Vaiṣṇava reckoning takes the second of a doubled pair: the first is
    # touched by the tenth. Smārtas keep the first, and pañcāṅgas print both as
    # separate dated calendars.
    #
    # This must be applied HERE and not only in resolve_lunar. Every ekādaśī
    # entry anchors with month "*", so it routes through this function — the
    # flag was read only in the annual path at first, which made the Vaiṣṇava
    # variant return dates identical to the Smārta one. A choice that is not a
    # choice is worse than not offering one.
    if anchor.get("avoidDashamiViddha"):
        drop = set()
        for i, (earlier, later) in enumerate(zip(out, out[1:])):
            if earlier.doubled and later.doubled and \
                    (later.date - earlier.date).days == 1:
                drop.add(i)
        if drop:
            out = [r for i, r in enumerate(out) if i not in drop]
            for r in out:
                if r.doubled:
                    r.note += ("; the Vaiṣṇava reckoning keeps the second day, "
                               "the first being daśamī-viddha")
    return out


def _sun_ingress(gregorian_year: int, degrees: float, ayanamsa: str = "lahiri",
                 after: datetime | None = None) -> datetime | None:
    """The instant the Sun reaches `degrees` of **sidereal** longitude."""
    lo = after or datetime(gregorian_year, 1, 1, tzinfo=timezone.utc)
    hi = datetime(gregorian_year + 1, 1, 1, tzinfo=timezone.utc)

    def gap(m: datetime) -> float:
        return ((longitudes(m, ayanamsa).sun_sidereal - degrees + 180.0) % 360.0) - 180.0

    step = timedelta(days=1)
    m = lo
    prev = gap(m)
    while m < hi:
        nxt = m + step
        cur = gap(nxt)
        if prev < 0 <= cur:
            a, b = m, nxt
            for _ in range(50):
                mid = a + (b - a) / 2
                if gap(a) < 0 <= gap(mid):
                    b = mid
                else:
                    a = mid
            return a + (b - a) / 2
        prev = cur
        m = nxt
    return None


def resolve_solar(
    anchor: dict, gregorian_year: int, lat: float = UJJAIN[0], lon: float = UJJAIN[1]
) -> Resolved | list[Resolved]:
    """
    A **saṅkrānti**: the Sun's ingress into a sidereal degree.

    Makara Saṅkrānti — Pongal in Tamil Nadu, Lohri in the Punjab, Magh Bihu in
    Assam — is one of the largest observances in India and was returning
    "unsupported anchor kind" until this existed, along with the twelve monthly
    saṅkrāntis and the Ambubachi Mela.

    **The frame is sidereal and that is not a detail.** Read tropically, 270°
    is the December solstice; read sidereally it is 14 January. The corpus
    states the frame on every solar anchor for exactly this reason.

    Which civil day owns the ingress has its own regional nirṇaya — the
    puṇyakāla rules that move the observance to the following day when the
    Sun crosses after sunset, and which differ between Tamil, Bengali and
    northern practice. Those are not modelled here, and the note says so
    rather than implying a ruling.
    """
    degrees = float(anchor.get("degrees", 0.0))
    every = anchor.get("recurrence") == "every 30 degrees"
    note = ("the civil day is taken from the ingress instant; regional "
            "puṇyakāla rules that can defer it to the next day are not applied")

    def one(deg: float, at: datetime) -> Resolved:
        local = at + timedelta(hours=lon / 15.0)
        return Resolved(
            key=anchor.get("key", ""), name=anchor.get("name", ""),
            date=local.date(), anchor=anchor, note=note,
        )

    if not every:
        at = _sun_ingress(gregorian_year, degrees)
        if at is None:
            return Resolved(
                key=anchor.get("key", ""), name=anchor.get("name", ""), date=None,
                anchor=anchor, skipped=True,
                skipped_reason=(f"the Sun did not reach {degrees}° sidereal in "
                                f"{gregorian_year}"),
            )
        return one(degrees, at)

    out: list[Resolved] = []
    for k in range(12):
        deg = (degrees + 30.0 * k) % 360.0
        at = _sun_ingress(gregorian_year, deg)
        if at is not None:
            out.append(one(deg, at))
    out.sort(key=lambda r: r.date)
    return out


def resolve(anchor: dict | None, gregorian_year: int, **kw):
    """
    An annual anchor yields one Resolved; a recurring one yields a list.

    The return type genuinely differs because the questions differ — "when is
    Dīpāvalī this year" has one answer and "when is Ekādaśī" has about
    twenty-four. Returning a one-element list for the first would make every
    caller unwrap it; returning only the first of the second would be wrong.
    """
    anchor = anchor or {}
    kind = anchor.get("kind")
    if kind is None:
        # A CONTAINER: an entry that names a multi-day festival whose individual
        # days are separate entries. Anthesteria is the case — Pithoigia, Choes
        # and Chytroi each have their own anchor, so giving the container one too
        # would put four events on three days.
        #
        # An empty anchor here is deliberate, not a defect. It took being caught
        # mid-"repair" to see that.
        return Resolved(
            key=anchor.get("key", ""), name=anchor.get("name", ""), date=None,
            anchor=anchor, skipped=True,
            skipped_reason=(
                "container entry — it has no date of its own because its "
                "constituent days are dated separately"
            ),
        )
    if kind == "lunar":
        if anchor.get("month") in (RECURRING, ADHIKA_ONLY):
            # Both walk the year rather than seeking one month: "*" takes every
            # lunation, "adhika" takes only the intercalary ones — which in most
            # years is none, and that empty list is the correct answer.
            return resolve_recurring(anchor, gregorian_year, **kw)
        return resolve_lunar(anchor, gregorian_year, **kw)
    if kind == "crescent":
        # The Attic month opens at a place too — half of them open on a
        # different day in Sydney than in Attica — so the observer goes down
        # here just as it does for the lunar branch.
        attic_kw = {k: v for k, v in kw.items() if k in ("lat", "lon", "reckoning")}
        if anchor.get("recurrence") == "monthly" or "month" not in anchor:
            return resolve_crescent_monthly(anchor, gregorian_year, **attic_kw)
        return resolve_crescent(anchor, gregorian_year, **attic_kw)
    if kind == "solar":
        solar_kw = {k: v for k, v in kw.items() if k in ("lat", "lon")}
        return resolve_solar(anchor, gregorian_year, **solar_kw)
    if kind == "relative":
        # Anchored to another festival rather than to the sky. Resolving it
        # needs that festival's date, which the caller has and this function
        # does not — so it says so rather than guessing a day from the range.
        after = anchor.get("after", "another occasion")
        rng = anchor.get("dayRange")
        return Resolved(
            key=anchor.get("key", ""), name=anchor.get("name", ""), date=None,
            anchor=anchor, skipped=True,
            skipped_reason=(
                f"anchored relative to {after}"
                + (f", within {rng[0]}–{rng[1]} of the month" if rng else "")
                + " — resolve that occasion first and pass its date"
            ),
        )
    if kind == "fixed":
        return Resolved(
            key=anchor.get("key", ""), name=anchor.get("name", ""),
            date=date_cls(gregorian_year, int(anchor["month"]), int(anchor["day"])),
            anchor=anchor,
        )
    raise ValueError(f"unsupported anchor kind: {kind!r}")
