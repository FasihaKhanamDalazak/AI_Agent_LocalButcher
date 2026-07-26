# Deploy target: Koyeb's free tier (a container host, not a buildpack-only
# platform) — see README.md's "Deployment" section for the full picture
# (why Koyeb, the keep-alive-ping requirement, env vars needed).
FROM python:3.12-slim

# uv is this project's package manager (see pyproject.toml/uv.lock) — the
# official image ships a static binary, copied in rather than pip-installed
# so it's available before any project dependencies exist.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dependencies installed from the lockfile BEFORE the app code is copied in,
# so an app-code-only change doesn't invalidate this (slow) layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Migrations are NOT run automatically here — Supabase already has this
# project's schema applied; re-running alembic on every container start
# would be one more thing to go wrong on a cold start. Run
# `uv run alembic upgrade head` manually against DATABASE_URL_SYNC if a
# migration genuinely needs applying before a deploy.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
