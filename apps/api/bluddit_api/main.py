import os

from fastapi import FastAPI


def create_app() -> FastAPI:
    environment = os.environ.get("APP_ENV", "development")
    if environment not in {"development", "test", "production"}:
        raise RuntimeError("APP_ENV must be development, test, or production")
    app = FastAPI(
        title="Bluddit API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
