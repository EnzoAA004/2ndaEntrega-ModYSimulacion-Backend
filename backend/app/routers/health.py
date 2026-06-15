from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        status = "disconnected"
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment, "database": status}


@router.head("")
def health_head():
    return Response(status_code=200)
