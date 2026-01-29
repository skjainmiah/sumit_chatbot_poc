"""Health check endpoint."""
import os
from fastapi import APIRouter
from backend.config import settings

router = APIRouter()


@router.get("")
async def health_check():
    """Check system health."""
    checks = {
        "status": "healthy",
        "databases": {},
        "llm_configured": bool(settings.LLM_API_KEY and settings.LLM_CHAT_URL),
    }

    # Check each database
    db_paths = {
        "crew_management": settings.crew_db_path,
        "flight_operations": settings.flight_db_path,
        "hr_payroll": settings.hr_db_path,
        "compliance_training": settings.compliance_db_path,
        "app": settings.app_db_path,
    }

    for name, path in db_paths.items():
        checks["databases"][name] = os.path.exists(path)

    # Overall status
    all_dbs_ok = all(checks["databases"].values())
    if not all_dbs_ok or not checks["llm_configured"]:
        checks["status"] = "degraded"

    return checks
