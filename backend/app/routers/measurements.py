from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas import MeasurementCreate, MeasurementFilters, MeasurementRead, MeasurementUpdate, PaginatedMeasurements
from app.services import measurement_service

router = APIRouter(prefix="/measurements", tags=["measurements"])


@router.get("", response_model=PaginatedMeasurements)
def list_measurements(
    location_name: str | None = None,
    city: str | None = None,
    country: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    filters = MeasurementFilters(
        location_name=location_name,
        city=city,
        country=country,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return measurement_service.list_measurements(db, filters)


@router.get("/locations")
def locations(db: Session = Depends(get_db)):
    return measurement_service.locations(db)


@router.get("/latest", response_model=list[MeasurementRead])
def latest(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return measurement_service.latest(db, limit)


@router.get("/{measurement_id}", response_model=MeasurementRead)
def get_measurement(measurement_id: int, db: Session = Depends(get_db)):
    row = measurement_service.get_measurement(db, measurement_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return row


@router.post("", response_model=MeasurementRead, status_code=status.HTTP_201_CREATED)
def create_measurement(payload: MeasurementCreate, db: Session = Depends(get_db)):
    return measurement_service.create_measurement(db, payload)


@router.put("/{measurement_id}", response_model=MeasurementRead)
def update_measurement(measurement_id: int, payload: MeasurementUpdate, db: Session = Depends(get_db)):
    row = measurement_service.get_measurement(db, measurement_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return measurement_service.update_measurement(db, row, payload)


@router.delete("/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_measurement(measurement_id: int, db: Session = Depends(get_db)):
    row = measurement_service.get_measurement(db, measurement_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Measurement not found")
    measurement_service.delete_measurement(db, row)
    return None

