# SPDX-License-Identifier: AGPL-3.0-only
"""
iCalendar export for station times.

**A download and a subscription are not the same product.** An `.ics` file is a
snapshot: it is correct on the day it is generated and drifts thereafter, and it
never gains next month's times. A subscribed feed is refetched by the client and
stays right as the year turns. The feed is the one that actually produces the
notification someone is trying to set, so it is the one to put forward.

Two details that decide whether the notification fires at all:

  - **UTC throughout, with a trailing Z.** Station times are instants. Writing
    them as floating local times means a phone that crosses a timezone rings at
    the wrong moment.
  - **A stable UID per event.** A calendar client matches on UID: keep it stable
    and a refetch *updates* an event, change it and the client accumulates
    duplicates until the calendar is unusable.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from shruti_astro.core.stations import StationDay

PRODID = "-//shrutivtuber.com//station times//EN"
# Clients treat this as a hint. An hour is frequent enough to pick up a
# correction and rare enough not to be rude.
REFRESH = "PT1H"


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _fold(line: str) -> str:
    """
    RFC 5545 says lines are folded at 75 octets. Clients that enforce it will
    reject an over-long SUMMARY outright rather than truncating it.
    """
    out = []
    raw = line.encode("utf-8")
    while len(raw) > 75:
        cut = 75
        # Never split a UTF-8 sequence.
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n ".join(out)


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", r"\;")
                .replace(",", r"\,").replace("\n", r"\n"))


def _uid(body: str, station: str, at: datetime, lat: float, lon: float) -> str:
    """
    Stable for a given station, instant and place.

    Derived rather than random so a refetch updates the event instead of
    creating a second one beside it.
    """
    seed = f"{body}|{station}|{at.astimezone(timezone.utc).isoformat()}|{lat:.4f},{lon:.4f}"
    return f"{hashlib.sha256(seed.encode()).hexdigest()[:32]}@shrutivtuber.com"


def to_ical(
    days: list[StationDay],
    lat: float,
    lon: float,
    calendar_name: str | None = None,
    duration_minutes: int = 15,
    alarm_minutes_before: int | None = 10,
    generated_at: datetime | None = None,
) -> str:
    """
    A VCALENDAR of every station that occurred.

    Stations that did not occur are simply absent — a calendar cannot express
    "no moonrise today", and inventing a zero-length event to say so would put a
    misleading entry in someone's day.
    """
    now = generated_at or datetime.now(timezone.utc)
    body = days[0].body if days else "sun"
    name = calendar_name or f"{body.title()} stations"

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
        f"X-PUBLISHED-TTL:{REFRESH}",
        f"REFRESH-INTERVAL;VALUE=DURATION:{REFRESH}",
    ]

    for day in days:
        for station in day.stations:
            if not station.occurred:
                continue
            summary = station.name.replace("_", " ").title()
            if station.dedication:
                summary = f"{summary} — {station.dedication}"

            lines += [
                "BEGIN:VEVENT",
                _fold(f"UID:{_uid(day.body, station.name, station.at, lat, lon)}"),
                f"DTSTAMP:{_stamp(now)}",
                f"DTSTART:{_stamp(station.at)}",
                f"DTEND:{_stamp(station.at + timedelta(minutes=duration_minutes))}",
                _fold(f"SUMMARY:{_escape(summary)}"),
                _fold(
                    f"DESCRIPTION:{_escape(station.name)} at "
                    f"{_escape(f'{lat:.4f}, {lon:.4f}')}"
                ),
                "TRANSP:TRANSPARENT",
            ]
            if alarm_minutes_before is not None:
                lines += [
                    "BEGIN:VALARM",
                    "ACTION:DISPLAY",
                    _fold(f"DESCRIPTION:{_escape(summary)}"),
                    f"TRIGGER:-PT{alarm_minutes_before}M",
                    "END:VALARM",
                ]
            lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    # RFC 5545 requires CRLF.
    return "\r\n".join(lines) + "\r\n"


def google_calendar_link(station_name: str, at: datetime, duration_minutes: int = 15) -> str:
    """A one-off "add to Google Calendar" URL for a single station."""
    from urllib.parse import urlencode

    start = _stamp(at)
    end = _stamp(at + timedelta(minutes=duration_minutes))
    return "https://calendar.google.com/calendar/render?" + urlencode({
        "action": "TEMPLATE",
        "text": station_name.replace("_", " ").title(),
        "dates": f"{start}/{end}",
    })
