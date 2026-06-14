from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import WastewaterMeasurement
from app.schemas import MeasurementCreate, MeasurementFilters, MeasurementUpdate


def _apply_filters(query, filters: MeasurementFilters):
    if filters.location_name:
        query = query.filter(WastewaterMeasurement.location_name.ilike(f"%{filters.location_name}%"))
    if filters.city:
        query = query.filter(WastewaterMeasurement.city.ilike(f"%{filters.city}%"))
    if filters.country:
        query = query.filter(WastewaterMeasurement.country.ilike(f"%{filters.country}%"))
    if filters.date_from:
        query = query.filter(WastewaterMeasurement.sample_date >= filters.date_from)
    if filters.date_to:
        query = query.filter(WastewaterMeasurement.sample_date <= filters.date_to)
    return query


def list_measurements(db: Session, filters: MeasurementFilters) -> dict:
    base = _apply_filters(db.query(WastewaterMeasurement), filters)
    total = base.count()
    items = (
        base.order_by(WastewaterMeasurement.sample_date.desc(), WastewaterMeasurement.id.desc())
        .offset(filters.offset)
        .limit(filters.limit)
        .all()
    )
    return {"total": total, "limit": filters.limit, "offset": filters.offset, "items": items}


def get_measurement(db: Session, measurement_id: int) -> WastewaterMeasurement | None:
    return db.get(WastewaterMeasurement, measurement_id)


def create_measurement(db: Session, payload: MeasurementCreate) -> WastewaterMeasurement:
    row = WastewaterMeasurement(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_measurement(db: Session, row: WastewaterMeasurement, payload: MeasurementUpdate) -> WastewaterMeasurement:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_measurement(db: Session, row: WastewaterMeasurement) -> None:
    db.delete(row)
    db.commit()


def locations(db: Session) -> list[dict]:
    rows = (
        db.query(
            WastewaterMeasurement.location_name,
            WastewaterMeasurement.city,
            WastewaterMeasurement.country,
            func.count(WastewaterMeasurement.id),
            func.max(WastewaterMeasurement.sample_date),
        )
        .group_by(WastewaterMeasurement.location_name, WastewaterMeasurement.city, WastewaterMeasurement.country)
        .order_by(WastewaterMeasurement.location_name)
        .all()
    )
    return [
        {
            "location_name": r[0],
            "city": r[1],
            "country": r[2],
            "samples": r[3],
            "latest_sample_date": r[4],
        }
        for r in rows
    ]


def latest(db: Session, limit: int = 20) -> list[WastewaterMeasurement]:
    return db.query(WastewaterMeasurement).order_by(WastewaterMeasurement.sample_date.desc()).limit(limit).all()


def query_location_series(db: Session, location_name: str, date_from: date | None = None, date_to: date | None = None):
    query = db.query(WastewaterMeasurement).filter(WastewaterMeasurement.location_name == location_name)
    if date_from:
        query = query.filter(WastewaterMeasurement.sample_date >= date_from)
    if date_to:
        query = query.filter(WastewaterMeasurement.sample_date <= date_to)
    return query.order_by(WastewaterMeasurement.sample_date.asc()).all()

