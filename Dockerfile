# SPDX-License-Identifier: AGPL-3.0-only
FROM python:3.13-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE ./
COPY shruti_astro ./shruti_astro
RUN pip install --upgrade pip && pip install .

FROM base AS prod
# Baked at build time so /version can report what is actually running — the
# AGPL s13 source offer has to point at this exact tree.
ARG SHRUTI_ASTRO_SHA=dev
ENV SHRUTI_ASTRO_SHA=${SHRUTI_ASTRO_SHA}
RUN useradd --create-home --uid 10001 astro && chown -R astro:astro /app
USER astro
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "shruti_astro.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
