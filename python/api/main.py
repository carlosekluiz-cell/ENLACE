"""
ENLACE API — Main Application

FastAPI application with CORS middleware and all platform routers:
geographic, market, health, opportunity, design, compliance, network_health,
rural, reports, and auth.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from python.api.config import settings
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
)

app = FastAPI(
    title="ENLACE API",
    description="AI-Powered Telecom Decision Intelligence Platform for Brazil",
    version=settings.app_version,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
    }
