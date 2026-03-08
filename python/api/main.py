"""
ENLACE API — Main Application

FastAPI application with CORS middleware, geographic, market, and health routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from python.api.config import settings
from python.api.routers import geographic, market, health, opportunity, design

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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
    }
