from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import admin, audit, auth, consents, dsr, health, organizations, purposes, webhooks
from app.core.config import get_settings
from app.core.exceptions import AppError, app_error_handler, unhandled_error_handler
from app.core.logging import setup_logging
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

settings = get_settings()
setup_logging(settings.log_level)

app = FastAPI(title="ConsentVault API", version="0.1.0", description="Consent & Data Privacy Management API")

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
)

app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_error_handler)

PREFIX = "/api/v1"
app.include_router(health.router, prefix=PREFIX)
app.include_router(auth.router, prefix=PREFIX)
app.include_router(organizations.router, prefix=PREFIX)
app.include_router(purposes.router, prefix=PREFIX)
app.include_router(consents.router, prefix=PREFIX)
app.include_router(audit.router, prefix=PREFIX)
app.include_router(dsr.router, prefix=PREFIX)
app.include_router(webhooks.router, prefix=PREFIX)
app.include_router(admin.router, prefix=PREFIX)


@app.get("/")
def root() -> dict:
    return {"service": "ConsentVault", "docs": "/docs", "health": "/api/v1/health"}
