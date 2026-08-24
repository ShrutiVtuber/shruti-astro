# SPDX-License-Identifier: AGPL-3.0-only
"""
shruti-astro — astrological computation daemon.

AGPL-3.0-only. This program uses Swiss Ephemeris under the AGPL arm of its dual
licence, which is why the whole daemon is AGPL and why its source is public.

AGPL §13: anyone interacting with this program over a network must be offered
its Corresponding Source *for the version actually running*. `GET /version`
returns the build SHA precisely so consuming pages can link the right tree, and
every response carries the source URL in a header so the obligation travels with
the data rather than depending on someone remembering to add a footer link.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

SOURCE_URL = "https://github.com/ShrutiVtuber/shruti-astro"
BUILD_SHA = os.environ.get("SHRUTI_ASTRO_SHA", "dev")

app = FastAPI(
    title="shruti-astro",
    version="0.1.0",
    description="Hellenistic and Vedic computation. AGPL-3.0-only.",
)


@app.middleware("http")
async def attach_source_offer(request: Request, call_next):
    """Carry the §13 source offer on every response."""
    response = await call_next(request)
    response.headers["X-Source-Licence"] = "AGPL-3.0-only"
    response.headers["X-Source-Url"] = f"{SOURCE_URL}/tree/{BUILD_SHA}"
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/version")
async def version() -> dict:
    """
    What a consuming page must link to satisfy AGPL §13.

    Link `sourceUrl`, not the repo root — §13 asks for the source of the running
    version, and `main` will not be that for long.
    """
    return {
        "service": "shruti-astro",
        "version": "0.1.0",
        "licence": "AGPL-3.0-only",
        "sha": BUILD_SHA,
        "sourceUrl": f"{SOURCE_URL}/tree/{BUILD_SHA}",
    }


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    # Never leak internals to a public tool page.
    return JSONResponse(status_code=500, content={"error": "computation failed"})
