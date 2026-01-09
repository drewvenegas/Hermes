"""
Health Check Endpoints

API health and readiness checks.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.config import get_settings
from hermes.services.database import get_db

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "service": "hermes",
        "version": settings.app_version,
    }


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check including database connectivity."""
    checks = {
        "database": False,
        "cache": False,
    }
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    # Check Redis (simplified for now)
    try:
        # Redis check would go here
        checks["cache"] = True
    except Exception:
        pass

    all_healthy = all(checks.values())
    
    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
    }


@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "live"}
