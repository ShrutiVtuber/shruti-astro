# SPDX-License-Identifier: AGPL-3.0-only
"""
Writing Magickal Bundle Format packs.

MBF is Theourgia's portable container: a zip holding `manifest.json` and one or
more payloads, each recorded in the manifest with its `sha256`. Building the
festival data this way rather than as a private table means Theourgia's Vedic
modules can install it directly when they land, and so can anything else that
learns the format.

**The manifest is a claim about the payload, so it must be true.** The digest is
computed from the bytes actually written, not from the object that was meant to
be written — those diverge the moment someone edits a payload by hand and
forgets to rebuild.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MBF_VERSION = 1


@dataclass
class Payload:
    kind: str
    path: str
    items: list[dict]

    def to_bytes(self) -> bytes:
        # Deterministic: sorted keys, fixed separators, trailing newline. Two
        # builds of the same data must produce byte-identical packs, or the
        # digests churn and stop meaning anything.
        return (json.dumps({"items": self.items}, ensure_ascii=False,
                           sort_keys=True, indent=1) + "\n").encode("utf-8")


@dataclass
class Asset:
    """A non-JSON file carried by the pack — a word list, an image, a font."""

    path: str
    media_type: str
    data: bytes

    def digest(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass
class Pack:
    slug: str
    name: str
    version: str
    description: str
    type: str = "festival-calendar"
    author_name: str = "Unattributed"
    spdx: str = "CC-BY-SA-4.0"
    closed_tradition: bool = False
    closed_tradition_note: str = ""
    source_citations: list[dict] = field(default_factory=list)
    payloads: list[Payload] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    created_at: str | None = None

    def manifest(self) -> dict:
        return {
            "mbf_version": MBF_VERSION,
            "type": self.type,
            "slug": self.slug,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": {"did": None, "name": self.author_name, "public_key": None},
            "license": {"spdx": self.spdx, "magickal_tags": []},
            "closed_tradition": self.closed_tradition,
            "closed_tradition_note": self.closed_tradition_note,
            "dependencies": [],
            "payloads": [
                {
                    "kind": p.kind,
                    "path": p.path,
                    "count": len(p.items),
                    "sha256": hashlib.sha256(p.to_bytes()).hexdigest(),
                }
                for p in self.payloads
            ],
            "provenance": [],
            "source_citations": self.source_citations,
            "assets": [
                {"path": a.path, "media_type": a.media_type, "sha256": a.digest()}
                for a in self.assets
            ],
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
        }

    def write(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        manifest = json.dumps(self.manifest(), ensure_ascii=False,
                              sort_keys=True, separators=(",", ":"))
        # ZIP_DEFLATED with a fixed date so rebuilds are reproducible.
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
            info = zipfile.ZipInfo("manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
            z.writestr(info, manifest)
            for p in self.payloads:
                pi = zipfile.ZipInfo(p.path, date_time=(1980, 1, 1, 0, 0, 0))
                z.writestr(pi, p.to_bytes())
            for a in self.assets:
                ai = zipfile.ZipInfo(a.path, date_time=(1980, 1, 1, 0, 0, 0))
                z.writestr(ai, a.data)
        return destination


def verify(path: Path) -> dict:
    """
    Read a pack back and check the manifest's claims against the bytes.

    A pack whose digests do not match its payloads is not a pack with a small
    problem — it is a pack whose manifest is lying, and nothing downstream
    should trust any part of it.
    """
    problems: list[str] = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "manifest.json" not in names:
            return {"valid": False, "problems": ["no manifest.json"]}

        manifest = json.loads(z.read("manifest.json"))
        for declared in manifest.get("payloads", []):
            p = declared["path"]
            if p not in names:
                problems.append(f"manifest declares {p}, which is not in the pack")
                continue
            raw = z.read(p)
            digest = hashlib.sha256(raw).hexdigest()
            if digest != declared["sha256"]:
                problems.append(
                    f"{p}: manifest says sha256 {declared['sha256'][:12]}…, "
                    f"bytes are {digest[:12]}…"
                )
            body = json.loads(raw)
            count = len(body.get("items", []))
            if count != declared["count"]:
                problems.append(
                    f"{p}: manifest says {declared['count']} items, found {count}"
                )

        for declared in manifest.get("assets", []):
            a = declared["path"]
            if a not in names:
                problems.append(f"manifest declares asset {a}, which is not in the pack")
                continue
            digest = hashlib.sha256(z.read(a)).hexdigest()
            if digest != declared["sha256"]:
                problems.append(
                    f"{a}: manifest says sha256 {declared['sha256'][:12]}…, "
                    f"bytes are {digest[:12]}…"
                )

        undeclared = names - {"manifest.json"} - {
            d["path"] for d in manifest.get("payloads", [])
        } - {d["path"] for d in manifest.get("assets", [])}
        for u in sorted(undeclared):
            problems.append(f"{u} is in the pack but not declared in the manifest")

    return {"valid": not problems, "problems": problems, "manifest": manifest}
