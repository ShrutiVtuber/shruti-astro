# SPDX-License-Identifier: AGPL-3.0-only
from shruti_astro.core.panchanga import karana, nakshatra, tithi, yoga


def test_new_moon_is_amavasya_end_and_pratipada_start():
    # Sun and Moon conjunct: the very start of Śukla Pratipadā.
    t = tithi(100.0, 100.0)
    assert t.index == 1 and "Pratipadā" in t.name


def test_full_moon_is_purnima():
    # Pūrṇimā spans 168°–180° of elongation. 179° is inside it.
    assert tithi(0.0, 179.0).name == "Pūrṇimā"


def test_tithi_boundaries_are_half_open():
    # Exactly 180° is not still Pūrṇimā — it is the instant Kṛṣṇa Pratipadā
    # begins. Reporting the outgoing tithi at its own end is the off-by-one
    # that makes a pañcāṅga disagree with every almanac by one day.
    assert tithi(0.0, 179.999).name == "Pūrṇimā"
    assert tithi(0.0, 180.0).name == "Kṛṣṇa Pratipadā"


def test_dark_fortnight_is_krishna():
    assert "Kṛṣṇa" in tithi(0.0, 200.0).name


def test_nakshatra_spans_thirteen_twenty():
    assert nakshatra(0.0).name == "Aśvinī"
    assert nakshatra(13.0).name == "Aśvinī"       # still inside the first span
    assert nakshatra(13.4).name == "Bharaṇī"      # just over 13°20'
    assert nakshatra(359.9).name == "Revatī"


def test_yoga_sums_both_longitudes():
    assert yoga(0.0, 0.0).index == 1
    assert yoga(180.0, 180.0).index == 1          # wraps at 360


def test_karana_cycle_is_not_uniform():
    # The classic bug is movable[i % 7] across all sixty. These three assert
    # the irregular head and tail that such an implementation gets wrong.
    assert karana(0.0, 1.0).name == "Kiṃstughna"   # first half-tithi only
    assert karana(0.0, 7.0).name == "Bava"         # movable cycle begins
    assert karana(0.0, 359.9).name == "Nāga"       # fixed karaṇas close it


def test_fractions_stay_in_range():
    for lon in (0.0, 37.5, 180.0, 359.99):
        for limb in (tithi(0.0, lon), nakshatra(lon), yoga(0.0, lon), karana(0.0, lon)):
            assert 0.0 <= limb.fraction < 1.0
