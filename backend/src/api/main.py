from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api import __version__
from api.errors import install_error_handler
from shared.config import get_settings
from shared.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    app.state.settings = settings

    engine = create_async_engine(settings.postgres_dsn, pool_pre_ping=True, future=True)
    app.state.engine = engine
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)

    redis = Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
    app.state.redis = redis

    try:
        yield
    finally:
        await redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="telegram-feed-api", lifespan=lifespan)

    install_error_handler(app)

    from api.routers import auth as auth_router
    app.include_router(auth_router.router)

    from api.routers import sources as sources_router
    app.include_router(sources_router.router)

    from api.routers import feed as feed_router
    app.include_router(feed_router.router)

    from api.routers import posts as posts_router
    app.include_router(posts_router.router)

    from api.routers import media as media_router
    app.include_router(media_router.router)

    from api.routers import channels as channels_router
    app.include_router(channels_router.router)

    from api.routers.admin.auth import router as admin_auth_router
    app.include_router(admin_auth_router)

    from api.routers.admin.channels import router as admin_channels_router
    app.include_router(admin_channels_router)

    from api.routers.admin.stats import router as admin_stats_router
    app.include_router(admin_stats_router)

    from api.routers.admin.actions import router as admin_actions_router
    app.include_router(admin_actions_router)

    origins = [o.strip() for o in get_settings().api_cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/internal/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
