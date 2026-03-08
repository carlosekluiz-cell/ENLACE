"""
ENLACE API — Main Application

FastAPI application with CORS, security headers, rate limiting, structured
logging, and all platform routers: geographic, market, health, opportunity,
design, compliance, network_health, rural, reports, auth, and mna.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from python.api.config import settings
from python.api.logging_config import RequestLoggingMiddleware, setup_logging
from python.api.middleware.rate_limiter import RateLimiterMiddleware
from python.api.middleware.security_headers import SecurityHeadersMiddleware
from python.api.routers import (
    geographic,
    market,
    health,
    opportunity,
    design,
    compliance,
    network_health,
    rural,
    reports,
    auth,
    mna,
)

# Initialize structured JSON logging before anything else
setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ENLACE API",
    description="AI-Powered Telecom Decision Intelligence Platform for Brazil",
    version=settings.app_version,
)

# ---------------------------------------------------------------------------
# Middleware stack (applied in reverse order — last added runs first)
# ---------------------------------------------------------------------------

# 1. CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Security headers on every response
app.add_middleware(SecurityHeadersMiddleware)

# 3. Rate limiting (60 req/min general, 10 req/min auth)
app.add_middleware(RateLimiterMiddleware, default_limit=60, auth_limit=10)

# 4. Request logging with correlation IDs
app.add_middleware(RequestLoggingMiddleware)

# ---------------------------------------------------------------------------
# Global exception handler — prevent stack trace leaks
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(geographic.router)
app.include_router(market.router)
app.include_router(health.router)
app.include_router(opportunity.router)
app.include_router(design.router)
app.include_router(compliance.router)
app.include_router(network_health.router)
app.include_router(rural.router)
app.include_router(reports.router)
app.include_router(auth.router)
app.include_router(mna.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
    }
