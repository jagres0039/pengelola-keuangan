"""FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pengelola_keuangan.api.routers import (
    admin,
    auth,
    billing,
    budgets,
    categories,
    contacts,
    export_import,
    receipt,
    summary,
    transactions,
)
from pengelola_keuangan.config import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="Pengelola Keuangan API",
        description=(
            "REST API untuk PWA pengelola keuangan. Pakai bareng bot Telegram. "
            "Auth: email + password → JWT bearer token."
        ),
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router, prefix="/api")
    app.include_router(categories.router, prefix="/api")
    app.include_router(transactions.router, prefix="/api")
    app.include_router(summary.router, prefix="/api")
    app.include_router(receipt.router, prefix="/api")
    app.include_router(budgets.router, prefix="/api")
    app.include_router(export_import.router, prefix="/api")
    app.include_router(billing.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(contacts.router, prefix="/api")

    return app


app = create_app()


def run() -> None:
    """Entrypoint for running uvicorn directly."""
    import uvicorn

    settings = get_settings()
    log_level = settings.log_level.lower()
    uvicorn.run(
        "pengelola_keuangan.api.main:app",
        host="0.0.0.0",  # noqa: S104 - container-bound; published via nginx
        port=8000,
        log_level=log_level,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    run()
