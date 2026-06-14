from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    return analytics_service.overview(db)


@router.get("/location/{location_name}")
def location_analysis(location_name: str, db: Session = Depends(get_db)):
    return analytics_service.location_analysis(db, location_name)


@router.get("/risk-table")
def risk_table(db: Session = Depends(get_db)):
    return analytics_service.risk_table(db)

