from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from sqlalchemy.orm import Session

from app.services import analytics_service
from app.services.measurement_service import locations, query_location_series

RISK_WEIGHT = {"Sin datos": 0, "Bajo": 1, "Moderado": 2, "Alto": 3, "Crítico": 4}


def _score_forecast(summary: dict) -> float:
    risk = RISK_WEIGHT.get(summary.get("forecast_risk_level", "Sin datos"), 0) * 25
    change = summary.get("projected_change_percent") or 0
    max_value = summary.get("max_predicted_viral_concentration_gc_l") or 0
    crossing_bonus = 20 if summary.get("critical_threshold_crossing_date") else 10 if summary.get("high_threshold_crossing_date") else 0
    growth_bonus = max(0, min(25, change / 4))
    magnitude_bonus = min(20, max_value / 100_000)
    return round(risk + crossing_bonus + growth_bonus + magnitude_bonus, 2)


def predictive_ranking(db: Session, horizon: int = 21, window: int = 45) -> list[dict]:
    result: list[dict] = []
    for loc in locations(db):
        forecast = analytics_service.forecast_location(db, loc["location_name"], horizon=horizon, window=window)
        summary = forecast.get("summary", {})
        rows = query_location_series(db, loc["location_name"])
        latest = rows[-1] if rows else None
        result.append({
            "location_name": loc["location_name"],
            "city": loc.get("city"),
            "country": loc.get("country"),
            "samples": loc.get("samples"),
            "latest_sample_date": loc.get("latest_sample_date"),
            "latest_viral_concentration_gc_l": float(latest.viral_concentration_gc_l) if latest else None,
            "forecast_risk_level": summary.get("forecast_risk_level"),
            "predictive_score": _score_forecast(summary),
            "projected_change_percent": summary.get("projected_change_percent"),
            "max_predicted_viral_concentration_gc_l": summary.get("max_predicted_viral_concentration_gc_l"),
            "doubling_time_days": summary.get("doubling_time_days"),
            "high_threshold_crossing_date": summary.get("high_threshold_crossing_date"),
            "critical_threshold_crossing_date": summary.get("critical_threshold_crossing_date"),
            "recommendation": summary.get("recommendation") or summary.get("message"),
        })
    return sorted(result, key=lambda item: item["predictive_score"], reverse=True)


def map_risk(db: Session, horizon: int = 21, window: int = 45) -> list[dict]:
    risk_rows = {row["location_name"]: row for row in analytics_service.risk_table(db)}
    ranking_rows = {row["location_name"]: row for row in predictive_ranking(db, horizon=horizon, window=window)}
    result = []
    for loc in locations(db):
        rows = query_location_series(db, loc["location_name"])
        latest = rows[-1] if rows else None
        risk = risk_rows.get(loc["location_name"], {})
        ranking = ranking_rows.get(loc["location_name"], {})
        result.append({
            "location_name": loc["location_name"],
            "city": loc.get("city"),
            "country": loc.get("country"),
            "latitude": latest.latitude if latest else None,
            "longitude": latest.longitude if latest else None,
            "latest_sample_date": loc.get("latest_sample_date"),
            "latest_viral_concentration_gc_l": risk.get("latest_viral_concentration_gc_l"),
            "risk_level": risk.get("risk_level"),
            "risk_score": risk.get("risk_score"),
            "forecast_risk_level": ranking.get("forecast_risk_level"),
            "predictive_score": ranking.get("predictive_score"),
            "projected_change_percent": ranking.get("projected_change_percent"),
            "critical_threshold_crossing_date": ranking.get("critical_threshold_crossing_date"),
            "high_threshold_crossing_date": ranking.get("high_threshold_crossing_date"),
        })
    return result


def executive_report_payload(db: Session) -> dict:
    overview = analytics_service.overview(db)
    risk_rows = analytics_service.risk_table(db)
    predictive_rows = predictive_ranking(db)
    map_rows = map_risk(db)
    critical_forecast = [row for row in predictive_rows if row.get("forecast_risk_level") == "Crítico"]
    high_forecast = [row for row in predictive_rows if row.get("forecast_risk_level") in {"Alto", "Crítico"}]
    recommendations = []
    if not overview.get("total_measurements"):
        recommendations.append("Cargar datos demo o CSV real para activar el análisis.")
    if critical_forecast:
        recommendations.append("Priorizar ubicaciones con cruce crítico proyectado y aumentar frecuencia de muestreo.")
    if high_forecast:
        recommendations.append("Comparar escenarios de mitigación y crecimiento alto para planificar intervención preventiva.")
    if not recommendations:
        recommendations.append("Mantener monitoreo periódico y utilizar la predicción como alerta temprana complementaria.")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": "Wastewater Sentinel - Reporte ejecutivo predictivo",
        "overview": overview,
        "risk_table": risk_rows,
        "predictive_ranking": predictive_rows,
        "map_risk": map_rows,
        "recommendations": recommendations,
        "academic_mapping": [
            {"topic": "Sistemas dinámicos autónomos", "application": "Evolución temporal de carga viral."},
            {"topic": "Sistemas no homogéneos", "application": "Eventos externos, lluvias y shocks epidemiológicos."},
            {"topic": "Bifurcación", "application": "Umbrales de crecimiento de brote y cambio de régimen."},
            {"topic": "Lyapunov", "application": "Región segura definida por carga viral e infectados estimados."},
            {"topic": "Predicción aplicada", "application": "Forecast log-lineal, bandas de incertidumbre y escenarios."},
        ],
    }


def executive_report_html(db: Session) -> str:
    payload = executive_report_payload(db)
    overview = payload["overview"]
    rows = payload["predictive_ranking"][:8]
    recommendations = "".join("<li>" + escape(str(item)) + "</li>" for item in payload["recommendations"])
    ranking_rows = "".join(
        "<tr>"
        + "<td>" + escape(str(row.get("location_name") or "-")) + "</td>"
        + "<td>" + escape(str(row.get("forecast_risk_level") or "-")) + "</td>"
        + "<td>" + escape(str(row.get("predictive_score") or "-")) + "</td>"
        + "<td>" + escape(str(row.get("projected_change_percent") or "-")) + "</td>"
        + "<td>" + escape(str(row.get("critical_threshold_crossing_date") or row.get("high_threshold_crossing_date") or "No cruza")) + "</td>"
        + "</tr>"
        for row in rows
    )
    mapping = "".join("<li><strong>" + escape(item["topic"]) + ":</strong> " + escape(item["application"]) + "</li>" for item in payload["academic_mapping"])
    return """
<!doctype html>
<html lang='es'>
<head>
  <meta charset='utf-8'>
  <title>Wastewater Sentinel - Reporte ejecutivo</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 40px; color: #0f172a; }
    h1 { color: #0e7490; }
    .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 24px 0; }
    .card { border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; background: #f8fafc; }
    .label { font-size: 11px; text-transform: uppercase; color: #64748b; letter-spacing: .08em; }
    .value { font-size: 22px; font-weight: 800; margin-top: 8px; }
    table { border-collapse: collapse; width: 100%; margin-top: 20px; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 10px; text-align: left; }
    th { background: #ecfeff; }
    .note { background: #ecfeff; border-left: 4px solid #0891b2; padding: 14px; margin: 22px 0; }
  </style>
</head>
<body>
  <h1>""" + escape(payload["title"]) + """</h1>
  <p>Generado: """ + escape(payload["generated_at"]) + """</p>
  <p>Usá la opción de imprimir del navegador para guardarlo como PDF.</p>
  <div class='grid'>
    <div class='card'><div class='label'>Mediciones</div><div class='value'>""" + str(overview.get("total_measurements", "-")) + """</div></div>
    <div class='card'><div class='label'>Ubicaciones</div><div class='value'>""" + str(overview.get("active_locations", "-")) + """</div></div>
    <div class='card'><div class='label'>Riesgo actual</div><div class='value'>""" + escape(str(overview.get("latest_risk_level", "-"))) + """</div></div>
    <div class='card'><div class='label'>Alertas tempranas</div><div class='value'>""" + str(overview.get("early_warning_locations", "-")) + """</div></div>
  </div>
  <div class='note'><strong>Interpretación:</strong> """ + escape(str(overview.get("status_message", "Sin interpretación disponible."))) + """</div>
  <h2>Ranking predictivo</h2>
  <table><thead><tr><th>Ubicación</th><th>Riesgo proyectado</th><th>Score</th><th>Cambio %</th><th>Cruce de umbral</th></tr></thead><tbody>""" + ranking_rows + """</tbody></table>
  <h2>Recomendaciones</h2><ul>""" + recommendations + """</ul>
  <h2>Relación con Modelado y Simulación</h2><ul>""" + mapping + """</ul>
</body>
</html>
"""
