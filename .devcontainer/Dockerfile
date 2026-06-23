FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

# libarchive to work with archives in f2:
RUN apt-get update \
    && apt-get install -y --no-install-recommends libarchive13 \
    && rm -rf /var/lib/apt/lists/*

# install uv:
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
