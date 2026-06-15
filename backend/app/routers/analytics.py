from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import WastewaterMeasurement
from app.services import advanced_analytics_service, analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    return analytics_service.overview(db)


@router.get("/predictive-ranking")
def predictive_ranking(
    horizon: int = Query(21, ge=7, le=90),
    window: int = Query(45, ge=14, le=180),
    db: Session = Depends(get_db),
):
    return advanced_analytics_service.predictive_ranking(db, horizon=horizon, window=window)


@router.get("/map-risk")
def map_risk(
    horizon: int = Query(21, ge=7, le=90),
    window: int = Query(45, ge=14, le=180),
    db: Session = Depends(get_db),
):
    return advanced_analytics_service.map_risk(db, horizon=horizon, window=window)


@router.get("/location/{location_name}/forecast")
def location_forecast(
    location_name: str,
    horizon: int = Query(21, ge=7, le=90),
    window: int = Query(45, ge=14, le=180),
    db: Session = Depends(get_db),
):
    return analytics_service.forecast_location(db, location_name, horizon=horizon, window=window)


@router.get("/location/{location_name}")
def location_analysis(location_name: str, db: Session = Depends(get_db)):
    return analytics_service.location_analysis(db, location_name)


@router.get("/risk-table")
def risk_table(db: Session = Depends(get_db)):
    return analytics_service.risk_table(db)


@router.get("/report")
def report(db: Session = Depends(get_db)):
    payload = advanced_analytics_service.executive_report_payload(db)
    overview_data = payload["overview"]
    risk_rows = payload["risk_table"]
    critical = [row for row in risk_rows if row.get("risk_level") == "Crítico"]
    high = [row for row in risk_rows if row.get("risk_level") in {"Alto", "Crítico"}]
    early = [row for row in risk_rows if row.get("early_warning")]
    return {
        **payload,
        "title": "Wastewater Sentinel - Reporte ejecutivo",
        "summary": {
            "critical_locations": len(critical),
            "high_or_critical_locations": len(high),
            "early_warning_locations": len(early),
            "highest_risk_location": overview_data.get("highest_risk_location"),
        },
    }


@router.get("/report/html", response_class=HTMLResponse)
def report_html(db: Session = Depends(get_db)):
    return HTMLResponse(advanced_analytics_service.executive_report_html(db))


@router.get("/export/measurements.csv")
def export_measurements_csv(db: Session = Depends(get_db)):
    rows = db.query(WastewaterMeasurement).order_by(WastewaterMeasurement.sample_date.asc()).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "sample_date",
        "location_name",
        "city",
        "country",
        "population_served",
        "flow_rate_m3_day",
        "viral_concentration_gc_l",
        "temperature_c",
        "rainfall_mm",
        "clinical_cases",
    ])
    for row in rows:
        writer.writerow([
            row.sample_date,
            row.location_name,
            row.city,
            row.country,
            row.population_served,
            row.flow_rate_m3_day,
            row.viral_concentration_gc_l,
            row.temperature_c,
            row.rainfall_mm,
            row.clinical_cases,
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=wastewater_measurements.csv"},
    )
