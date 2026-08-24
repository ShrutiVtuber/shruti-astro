# SPDX-License-Identifier: AGPL-3.0-only
"""
MBF packs. The manifest is a claim about the payload, so the tests are mostly
about that claim being true.
"""

import json
import zipfile
from pathlib import Path

import pytest

from shruti_astro.packs.mbf import Asset, Pack, Payload, verify

ITEMS = [
    {"key": "dipavali", "name": "Dīpāvalī", "ref": "occasions:dipavali",
     "summary": "The row of lamps.",
     "anchor": {"kind": "lunar", "month": "Kārtika", "paksha": "krishna",
                "tithi": 15, "reckoning": "purnimanta", "dayRule": "pradosha"}},
]


def _pack(**kw) -> Pack:
    return Pack(
        slug="shruti-test", name="Test", version="0.1.0",
        description="A pack for tests.",
        payloads=[Payload("festival-calendar", "payloads/festival-calendar.json", ITEMS)],
        created_at="2026-08-24T00:00:00+00:00", **kw,
    )


def test_a_written_pack_verifies(tmp_path: Path):
    p = _pack().write(tmp_path / "t.mbf")
    r = verify(p)
    assert r["valid"], r["problems"]
    assert r["manifest"]["payloads"][0]["count"] == 1


def test_builds_are_byte_identical(tmp_path: Path):
    """
    Two builds of the same data must produce the same bytes, or the digests
    churn on every rebuild and stop meaning anything.
    """
    a = _pack().write(tmp_path / "a.mbf")
    b = _pack().write(tmp_path / "b.mbf")
    assert a.read_bytes() == b.read_bytes()


def test_a_tampered_payload_is_caught(tmp_path: Path):
    """
    Hand-edit a payload without rebuilding and the manifest is lying. Nothing
    downstream should trust any part of such a pack.
    """
    src = _pack().write(tmp_path / "t.mbf")
    with zipfile.ZipFile(src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts["payloads/festival-calendar.json"] = b'{"items": []}\n'
    tampered = tmp_path / "tampered.mbf"
    with zipfile.ZipFile(tampered, "w") as z:
        for n, data in parts.items():
            z.writestr(n, data)

    r = verify(tampered)
    assert not r["valid"]
    assert any("sha256" in p for p in r["problems"])


def test_a_miscounted_manifest_is_caught(tmp_path: Path):
    src = _pack().write(tmp_path / "t.mbf")
    with zipfile.ZipFile(src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    m = json.loads(parts["manifest.json"])
    m["payloads"][0]["count"] = 99
    parts["manifest.json"] = json.dumps(m).encode()
    out = tmp_path / "miscounted.mbf"
    with zipfile.ZipFile(out, "w") as z:
        for n, data in parts.items():
            z.writestr(n, data)
    assert any("99 items" in p for p in verify(out)["problems"])


def test_assets_are_declared_and_digested(tmp_path: Path):
    p = _pack(assets=[Asset("assets/words/x.txt", "text/plain", b"alpha\nbeta\n")])
    written = p.write(tmp_path / "t.mbf")
    r = verify(written)
    assert r["valid"], r["problems"]
    assert r["manifest"]["assets"][0]["path"] == "assets/words/x.txt"


def test_an_undeclared_file_is_caught(tmp_path: Path):
    src = _pack().write(tmp_path / "t.mbf")
    with zipfile.ZipFile(src, "a") as z:
        z.writestr("payloads/stowaway.json", b"{}")
    assert any("stowaway" in p for p in verify(src)["problems"])


# ── interop with the real thing ─────────────────────────────────────────────

THEOURGIA_PACKS = Path(
    "/home/sophia/Documents/development/theourgia/packs/dist"
)


@pytest.mark.skipif(not THEOURGIA_PACKS.is_dir(), reason="theourgia checkout not present")
def test_every_real_theourgia_pack_validates():
    """
    The whole point of using MBF rather than a private table: what is built here
    must be readable there, and what is built there must be readable here.
    """
    failures = []
    packs = sorted(THEOURGIA_PACKS.glob("*.mbf"))
    assert packs, "no packs found to check against"
    for f in packs:
        r = verify(f)
        if not r["valid"]:
            failures.append((f.name, r["problems"]))
    assert not failures, failures
