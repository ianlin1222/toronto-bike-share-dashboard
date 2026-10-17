FROM ghcr.io/astral-sh/uv:0.12.10 AS uv

FROM python:3.13.15-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /app app

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

COPY alembic.ini ./
COPY alembic ./alembic
COPY sql ./sql
COPY tests/fixtures ./tests/fixtures

RUN mkdir -p /app/var/raw /app/var/archive /app/var/models \
    && chown app:app /app /app/var /app/var/raw /app/var/archive /app/var/models
USER app

EXPOSE 8000
CMD ["uvicorn", "bikeshare.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
USER root
COPY tests ./tests
COPY scripts ./scripts
COPY analysis ./analysis
COPY .env.example ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --group dev
RUN chown app:app /app
USER app

FROM runtime AS production
