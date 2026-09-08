# Install the Python app with uv into a venv, then ship the venv and the app
# source into the runtime image. The project is installed in editable mode, so
# the standalone UI can live next to the source instead of being packaged into
# a wheel (no static-file packaging needed).
#
# Build context: repository root.
#   docker build -f pde_operator/Dockerfile -t pde-operator:<tag> .
#
# The React UI is built once in CI (build-ui job) and shared with the Argo CD
# extension UI image; this stage consumes the prebuilt standalone bundle.

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_NO_DEV=1

WORKDIR /app

COPY pde_operator/pyproject.toml pde_operator/uv.lock pde_operator/README.md ./
COPY pde_operator/src ./src
COPY argocd_extension/ui/dist/standalone ./src/pde_operator/ui/standalone

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.13-slim-bookworm

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

EXPOSE 8000
ENTRYPOINT ["pde-operator"]
