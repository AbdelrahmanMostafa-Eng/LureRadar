# syntax=docker/dockerfile:1
# Slim, non-root, read-only-filesystem friendly image for the CLI and `watch`.
#   docker run --rm --read-only ghcr.io/abdelrahmanmostafa-eng/lureradar check "hxxps://example[.]test"
# Base images are tracked by Dependabot (docker ecosystem); pin by digest in
# your own deployments if you need fully reproducible pulls.

FROM python:3.15-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /src
COPY . .
RUN uv build --wheel --out-dir /dist

FROM python:3.15-slim
LABEL org.opencontainers.image.title="LureRadar" \
      org.opencontainers.image.description="Open threat radar for hyped-launch scams" \
      org.opencontainers.image.source="https://github.com/AbdelrahmanMostafa-Eng/LureRadar" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LURERADAR_CACHE_DIR=/tmp/lureradar
COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-compile /tmp/*.whl "websockets>=13" && rm -f /tmp/*.whl \
 && useradd --create-home --uid 10001 lureradar
USER 10001
WORKDIR /home/lureradar
ENTRYPOINT ["lureradar"]
CMD ["--help"]
