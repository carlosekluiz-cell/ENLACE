"""
ENLACE Health Check Router

System health endpoint with database and Redis status.
"""

from fastapi import APIRouter

from python.api.models.schemas import HealthCheckResponse

router = APIRouter(tags=["health"])


@router.get("/api/v1/health", response_model=HealthCheckResponse)
async def health_check():
    """System health check with database and Redis status."""
    db_status = "unknown"
    redis_status = "unknown"

    # Check PostgreSQL
    try:
        import psycopg2

        conn = psycopg2.connect(
            "postgresql://enlace:enlace_dev_2026@localhost:5432/enlace"
        )
        conn.cursor().execute("SELECT 1")
        conn.close()
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    # Check Redis
    try:
        import redis

        r = redis.from_url("redis://localhost:6379")
        r.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unavailable"

    return HealthCheckResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        version="1.0.0",
        database=db_status,
        redis=redis_status,
    )
