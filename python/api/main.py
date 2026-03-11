"""
ENLACE API — Main Application

FastAPI application with CORS, security headers, rate limiting, structured
logging, and all platform routers: geographic, market, health, opportunity,
design, compliance, network_health, rural, reports, auth, mna, and satellite.
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
    admin,
    events,
    satellite,
    intelligence,
    research,
    # Wave 1 — new feature routers
    buildings,
    fiber,
    h3,
    timeseries,
    speedtest,
    coverage,
    colocation,
    alerts,
    mna_enhanced,
    pulso_score,
    credit,
    # Wave 2 — research-driven feature routers
    spatial_analytics,
    starlink_threat,
    fwa_fiber,
    backhaul,
    weather_risk,
    compliance_rgst,
    obligations,
    peering,
    ixp,
    # Wave 3 — cross-reference analytics
    cross_analytics,
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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept"],
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
app.include_router(admin.router)
app.include_router(events.router)
app.include_router(satellite.router)
app.include_router(intelligence.router)
app.include_router(research.router)

# Wave 1 — new feature routers
app.include_router(buildings.router)
app.include_router(fiber.router)
app.include_router(h3.router)
app.include_router(timeseries.router)
app.include_router(speedtest.router)
app.include_router(coverage.router)
app.include_router(colocation.router)
app.include_router(alerts.router)
app.include_router(mna_enhanced.router)
app.include_router(pulso_score.router)
app.include_router(credit.router)

# Wave 2 — research-driven feature routers
app.include_router(spatial_analytics.router)
app.include_router(starlink_threat.router)
app.include_router(fwa_fiber.router)
app.include_router(backhaul.router)
app.include_router(weather_risk.router)
app.include_router(compliance_rgst.router)
app.include_router(obligations.router)
app.include_router(peering.router)
app.include_router(ixp.router)

# Wave 3 — cross-reference analytics
app.include_router(cross_analytics.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
    }
