from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.backup import backup_scheduler


def create_app() -> FastAPI:
    app = FastAPI(
        title="Manufacturing ERP API",
        version="0.1.0",
        description="Configurable manufacturing ERP backend for order-to-cash production flow.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")
    app.add_event_handler("startup", backup_scheduler.start)
    app.add_event_handler("shutdown", backup_scheduler.stop)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
