#!/usr/bin/env bash
# Run the test suite.
#
# NOT `docker compose exec astro pytest`. The running container is the prod
# image: it carries no pytest, and it deliberately does not contain packs/ or
# tests/ — the Dockerfile copies only shruti_astro. Running the suite in there
# produces failures that say the shipped festival packs are missing when the
# packs are committed and perfectly fine; the container simply has no packs/
# directory. That misdiagnosis cost real time, so this script exists to make
# the wrong way harder than the right one.
#
# This builds the dev stage and mounts the working tree read-only, so the suite
# always runs against the files as they are on disk.
set -euo pipefail
cd "$(dirname "$0")/.."

docker build --quiet --target dev -t shruti-astro-test . >/dev/null

exec docker run --rm \
  -v "$PWD/shruti_astro:/app/shruti_astro:ro" \
  -v "$PWD/tests:/app/tests:ro" \
  -v "$PWD/packs:/app/packs:ro" \
  -v "$PWD/scripts:/app/scripts:ro" \
  shruti-astro-test \
  python -m pytest tests "$@"
