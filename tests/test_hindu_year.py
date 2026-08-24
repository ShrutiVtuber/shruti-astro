# SPDX-License-Identifier: AGPL-3.0-only
"""The year table, and the intercalation rule that makes it matter."""

import pytest

from shruti_astro.core.hindu_calendar import hindu_year
from shruti_astro.core.samvatsara import SAMVATSARAS, samvatsara


@pytest.mark.parametrize("year", [2026, 2029])
def test_intercalary_years_carry_thirteen_months(year):
    y = hindu_year(year)
    assert y["hasAdhikaMasa"] is True
    assert y["monthCount"] == 13


def test_an_adhika_month_repeats_the_name_that_follows_it():
    y = hindu_year(2026)
    adhika = [m for m in y["months"] if m["adhika"]]
    assert len(adhika) == 1
    a = adhika[0]
    following = y["months"][y["months"].index(a) + 1]
    assert following["name"] == a["name"]
    assert following["adhika"] is False


def test_adhika_months_carry_no_festivals():
    """
    The rule that makes intercalation more than decoration. Letting festivals
    fall in the repeat puts every observance a month early.
    """
    for m in hindu_year(2026)["months"]:
        assert m["carriesFestivals"] == (not m["adhika"])


def test_every_lunation_is_a_lunation_long():
    for m in hindu_year(2026)["months"]:
        assert 29.0 < m["days"] < 30.5


def test_months_are_contiguous():
    months = hindu_year(2026)["months"]
    for a, b in zip(months, months[1:]):
        assert a["end"] == b["start"]


def test_chaitra_2026_opens_at_ugadi():
    """Chaitra Śukla Pratipadā 2026 falls on 19 March — cross-checks the
    lunation walk against a date the calendar is named by."""
    chaitra = next(m for m in hindu_year(2026)["months"]
                   if m["name"] == "Chaitra" and not m["adhika"])
    assert chaitra["start"][:10] == "2026-03-19"


def test_eras_are_all_named():
    e = hindu_year(2026)["eras"]
    assert e["vikrama"] == 2083 and e["shaka"] == 1948
    assert e["kali"] == 5127 and e["bengali"] == 1433
    assert e["samvatsara"]["name"] == "Parābhava"


def test_the_jovian_cycle_is_sixty_names_long_and_wraps():
    assert len(SAMVATSARAS) == 60 == len(set(SAMVATSARAS))
    assert samvatsara(1948)["name"] == "Parābhava"
    assert samvatsara(1948 + 60)["name"] == "Parābhava"


def test_the_surya_siddhanta_year_also_builds():
    y = hindu_year(2026, authority="surya_siddhanta")
    assert 12 <= y["monthCount"] <= 13
    assert y["authority"] == "surya_siddhanta"
