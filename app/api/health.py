"""
Application health endpoints.

Used by:
- developers to verify the API is running.
- container/orchestration platforms to determine application health.
- monitoring systems.

`/health/live` verifies that the process is alive.
`/health/ready` additionally verifies that PostgreSQL is reachable.
"""

from fastapi import APIRouter, HTTPException, status

from app.database.connection import pool

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Return success when the API process is running."""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness() -> dict[str, str]:
    """Return success only when required infrastructure is available."""

    try:
        async with pool.connection() as connection, connection.cursor() as cursor:
            await cursor.execute("SELECT 1")
            await cursor.fetchone()

        return {"status": "ready"}

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
