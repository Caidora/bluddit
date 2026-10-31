FROM python:3.13-slim-bookworm AS development
COPY --from=ghcr.io/astral-sh/uv:0.6.13 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --locked
COPY apps/api/ ./
EXPOSE 8000
CMD ["uv", "run", "--locked", "uvicorn", "bluddit_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM development AS dependencies
RUN uv sync --locked --no-dev

FROM python:3.13-slim-bookworm AS production
ENV PYTHONUNBUFFERED=1 APP_ENV=production PATH=/app/.venv/bin:$PATH
RUN useradd --system --uid 10001 --create-home app
WORKDIR /app
COPY --from=dependencies /app/.venv ./.venv
COPY apps/api/bluddit_api ./bluddit_api
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
ARG GIT_SHA=local
LABEL org.opencontainers.image.source="https://github.com/Caidora/bluddit" org.opencontainers.image.revision=$GIT_SHA
CMD ["uvicorn", "bluddit_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
