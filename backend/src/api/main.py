import importlib.metadata
from contextlib import asynccontextmanager

from fastapi import FastAPI

from shared.config import get_settings
from shared.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    app.state.settings = settings
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="telegram-feed-api", lifespan=lifespan)

    try:
        version = importlib.metadata.version("telegram-feed-backend")
    except importlib.metadata.PackageNotFoundError:
        version = "0.0.0"

    @app.get("/internal/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": version}

    return app


app = create_app()
