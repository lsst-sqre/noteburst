FROM mcr.microsoft.com/devcontainers/python:3.14

# uv version should match UV_VERSION in .github/workflows/ci.yaml
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

# Same build dependencies as scripts/install-dependency-packages.sh
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get update \
    && apt-get -y install --no-install-recommends build-essential git libffi-dev \
    && rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy \
    UV_PYTHON_PREFERENCE=only-system
