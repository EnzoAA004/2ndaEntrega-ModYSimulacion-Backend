from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import WastewaterMeasurement
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


@router.get("/report")
def report(db: Session = Depends(get_db)):
    overview_data = analytics_service.overview(db)
    risk_rows = analytics_service.risk_table(db)
    critical = [row for row in risk_rows if row.get("risk_level") == "Crítico"]
    high = [row for row in risk_rows if row.get("risk_level") in {"Alto", "Crítico"}]
    early = [row for row in risk_rows if row.get("early_warning")]
    recommendations = []
    if not overview_data.get("total_measurements"):
        recommendations.append("Cargar datos demo o CSV real para activar el análisis.")
    if critical:
        recommendations.append("Priorizar ubicaciones críticas y revisar tendencia de 7 y 14 días.")
    if early:
        recommendations.append("Contrastar alertas tempranas de aguas residuales con casos clínicos rezagados.")
    if not recommendations:
        recommendations.append("Mantener monitoreo periódico y comparar escenarios de intervención.")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": "Wastewater Sentinel - Reporte ejecutivo",
        "overview": overview_data,
        "risk_table": risk_rows,
        "summary": {
            "critical_locations": len(critical),
            "high_or_critical_locations": len(high),
            "early_warning_locations": len(early),
            "highest_risk_location": overview_data.get("highest_risk_location"),
        },
        "recommendations": recommendations,
        "academic_mapping": [
            {"topic": "Sistemas autónomos 1D", "application": "Decaimiento y equilibrio de carga viral."},
            {"topic": "Sistemas no homogéneos", "application": "Eventos externos, shocks y dilución por lluvia."},
            {"topic": "Sistemas no lineales 2D", "application": "Interacción infectados-carga viral."},
            {"topic": "Bifurcación", "application": "Umbral beta = gamma."},
            {"topic": "Lyapunov", "application": "Función V_risk y región segura."},
            {"topic": "Métodos numéricos", "application": "Comparación Euler, Heun y RK4."},
        ],
    }


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
