"""FastAPI application factory. Run: uvicorn healthmisinfo.main:app"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from healthmisinfo import DISCLAIMER_AR, DISCLAIMER_EN, __version__
from healthmisinfo.api.routes import admin, analytics, analyze, auth, datasets, models, reports, reviews
from healthmisinfo.config import get_settings
from healthmisinfo.db.session import SessionLocal

log = logging.getLogger("healthmisinfo")

DESCRIPTION = f"""
Bilingual (Arabic/English) research API for detecting health rumours and misinformation.

* Labels: `0 SUPPORTED`, `1 MISLEADING`, `2 NEEDS_REVIEW`.
* **{DISCLAIMER_EN}**
* {DISCLAIMER_AR}
* When no trained, evaluated and registered model exists for a language, `/api/v1/analyze` returns
  `status = "model_not_trained"` with **no label and no probabilities**.

Authentication: `POST /api/v1/auth/login` returns a bearer token and sets an HttpOnly cookie.
Cookie-authenticated unsafe requests must send `X-Requested-With`.
"""


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Health Misinformation Detection — Research API",
        version=__version__,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        max_age=600,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exc(_: Request, exc: StarletteHTTPException):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_exc(_: Request, exc: RequestValidationError):
        errors = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return JSONResponse({"detail": "Validation error", "errors": errors}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error: %s", exc)
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    @app.get("/health", tags=["system"], summary="Liveness + database connectivity")
    def health():
        db_ok = True
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
        except Exception:
            db_ok = False
        return JSONResponse(
            {"status": "ok" if db_ok else "degraded", "database": db_ok, "version": __version__},
            status_code=200 if db_ok else 503,
        )

    for r in (auth, models, analyze, datasets, reviews, analytics, reports, admin):
        app.include_router(r.router)
    return app


app = create_app()
