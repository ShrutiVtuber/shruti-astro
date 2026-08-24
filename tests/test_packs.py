# SPDX-License-Identifier: AGPL-3.0-only
"""The festival corpora as MBF packs — reproducible, verifiable, not stale."""

import json
import zipfile
from pathlib import Path

import pytest

from shruti_astro.core.festival_registry import CORPORA, load
from shruti_astro.packs.mbf import Pack, Payload, verify

DIST = Path(__file__).resolve().parent.parent / "packs" / "dist"


def _pack(tradition, tmp_path, version="9.9.9"):
    corpus = load(tradition)
    p = Pack(slug=f"t-{tradition}", name=tradition, version=version,
             description="x", author_name="Soror Eu. A.",
             created_at="2026-08-24T00:00:00+00:00",
             payloads=[Payload("festival-calendar",
                               "payloads/festival-calendar.json", corpus.entries)])
    return p.write(tmp_path / f"{tradition}.mbf")


@pytest.mark.parametrize("tradition", sorted(CORPORA))
def test_a_corpus_packs_and_verifies(tradition, tmp_path):
    assert verify(_pack(tradition, tmp_path))["valid"]


@pytest.mark.parametrize("tradition", sorted(CORPORA))
def test_packing_is_reproducible(tradition, tmp_path):
    """Two builds of the same data must be byte-identical or digests mean nothing."""
    a = _pack(tradition, tmp_path / "a").read_bytes()
    b = _pack(tradition, tmp_path / "b").read_bytes()
    assert a == b


@pytest.mark.parametrize("tradition", sorted(CORPORA))
def test_only_verified_corpora_are_shipped(tradition):
    assert load(tradition).verified, f"{tradition} must not be packed unverified"


@pytest.mark.parametrize("tradition", sorted(CORPORA))
def test_the_shipped_pack_is_not_stale(tradition):
    """
    The 0.1.0 Attic pack sat in dist/ carrying a payload the corpus had moved
    past — competing dates, alternate names and the attested/conventional
    split of the deities were all missing from what shipped.
    """
    slug = {"attic": "shruti-attic-festivals", "hindu": "shruti-hindu-festivals"}[tradition]
    built = [p for p in DIST.glob(f"{slug}-v*.mbf")]
    assert len(built) == 1, f"exactly one version of {slug} should be in dist/"
    shipped = json.loads(
        zipfile.ZipFile(built[0]).read("payloads/festival-calendar.json"))["items"]
    assert shipped == load(tradition).entries


def test_no_pack_carries_closed_material():
    for path in DIST.glob("*.mbf"):
        manifest = json.loads(zipfile.ZipFile(path).read("manifest.json"))
        assert manifest["closed_tradition"] is False
        assert manifest["closed_tradition_note"]


def test_the_corpus_level_bibliography_survives_packing():
    """
    Parke, Deubner, Mikalson and Simon are cited by no single Attic entry.
    Deriving citations from entries alone dropped all four silently.
    """
    path = next(DIST.glob("shruti-attic-festivals-v*.mbf"))
    manifest = json.loads(zipfile.ZipFile(path).read("manifest.json"))
    works = {c["work"] for c in manifest["source_citations"]}
    assert "Festivals of the Athenians" in works
    assert "Attische Feste" in works


def test_citations_are_deduplicated():
    """Kane is cited by dozens of entries; listing him dozens of times says nothing."""
    path = next(DIST.glob("shruti-hindu-festivals-v*.mbf"))
    manifest = json.loads(zipfile.ZipFile(path).read("manifest.json"))
    seen = [(c["author"], c["work"], c["locus"]) for c in manifest["source_citations"]]
    assert len(seen) == len(set(seen))
