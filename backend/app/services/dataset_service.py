from __future__ import annotations

from io import BytesIO

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ImportedDataset, WastewaterMeasurement
from app.schemas import MeasurementCreate
from app.services.demo_data_service import generate_demo_measurements
from app.services.measurement_service import create_measurement
from app.utils.json_utils import dumps
from app.utils.math_utils import safe_float, safe_int


ALIASES = {
    "sample_date": ["sample_date", "date", "fecha", "sampling_date"],
    "location_name": ["location_name", "location", "ubicacion", "planta"],
    "city": ["city", "ciudad"],
    "country": ["country", "pais", "país"],
    "population_served": ["population_served", "population", "poblacion"],
    "flow_rate_m3_day": ["flow_rate_m3_day", "flow", "caudal"],
    "viral_concentration_gc_l": ["viral_concentration_gc_l", "viral_load", "concentration", "carga_viral"],
}


def _pick(row, columns: dict[str, str], field: str, default=None):
    source = columns.get(field)
    return row[source] if source and source in row else default


def _map_columns(df: pd.DataFrame) -> dict[str, str]:
    normalized = {str(col).strip().lower(): col for col in df.columns}
    mapped: dict[str, str] = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if alias.lower() in normalized:
                mapped[target] = normalized[alias.lower()]
                break
    return mapped


def import_csv(db: Session, content: bytes, filename: str, source_name: str | None = None) -> dict:
    try:
        df = pd.read_csv(BytesIO(content))
    except Exception as exc:
        raise ValueError(f"CSV inválido: {exc}") from exc
    if df.empty:
        raise ValueError("El CSV no contiene filas.")
    mapped = _map_columns(df)
    required = {"sample_date", "location_name", "population_served", "flow_rate_m3_day", "viral_concentration_gc_l"}
    missing = sorted(required - set(mapped))
    if missing:
        raise ValueError(f"Faltan columnas requeridas o compatibles: {', '.join(missing)}")

    created = []
    errors = []
    for idx, row in df.iterrows():
        try:
            payload = MeasurementCreate(
                sample_date=pd.to_datetime(_pick(row, mapped, "sample_date")).date(),
                location_name=str(_pick(row, mapped, "location_name")),
                city=str(_pick(row, mapped, "city", "Unknown")),
                country=str(_pick(row, mapped, "country", "Unknown")),
                latitude=safe_float(row.get("latitude"), None),
                longitude=safe_float(row.get("longitude"), None),
                population_served=safe_int(_pick(row, mapped, "population_served")),
                flow_rate_m3_day=safe_float(_pick(row, mapped, "flow_rate_m3_day")),
                viral_concentration_gc_l=safe_float(_pick(row, mapped, "viral_concentration_gc_l")),
                temperature_c=safe_float(row.get("temperature_c"), None),
                rainfall_mm=safe_float(row.get("rainfall_mm"), None),
                ph=safe_float(row.get("ph"), None),
                turbidity_ntu=safe_float(row.get("turbidity_ntu"), None),
                clinical_cases=safe_int(row.get("clinical_cases"), None),
                notes=str(row.get("notes")) if "notes" in row and not pd.isna(row.get("notes")) else None,
            )
            created.append(create_measurement(db, payload))
        except Exception as exc:
            errors.append({"row": int(idx) + 2, "error": str(exc)})
    if not created:
        raise ValueError(f"No se pudo importar ninguna fila. Errores: {errors[:5]}")

    dataset = ImportedDataset(
        filename=filename,
        source_name=source_name,
        rows_imported=len(created),
        columns_json=dumps({"original": list(df.columns), "mapped": mapped}),
    )
    db.add(dataset)
    db.commit()
    return {"rows_imported": len(created), "errors": errors, "dataset_id": dataset.id, "columns_mapped": mapped}


def seed_demo(db: Session) -> dict:
    payloads = generate_demo_measurements()
    for payload in payloads:
        create_measurement(db, payload)
    dataset = ImportedDataset(
        filename="demo-generated",
        source_name="Wastewater Sentinel demo",
        rows_imported=len(payloads),
        columns_json=dumps(list(MeasurementCreate.model_fields.keys())),
    )
    db.add(dataset)
    db.commit()
    return {"rows_inserted": len(payloads), "locations": 4, "days": 180}


def summary(db: Session) -> dict:
    total = db.query(func.count(WastewaterMeasurement.id)).scalar() or 0
    active = db.query(func.count(func.distinct(WastewaterMeasurement.location_name))).scalar() or 0
    min_date, max_date = db.query(func.min(WastewaterMeasurement.sample_date), func.max(WastewaterMeasurement.sample_date)).one()
    avg_viral, max_viral = db.query(
        func.avg(WastewaterMeasurement.viral_concentration_gc_l),
        func.max(WastewaterMeasurement.viral_concentration_gc_l),
    ).one()
    latest = (
        db.query(WastewaterMeasurement.location_name, func.max(WastewaterMeasurement.sample_date))
        .group_by(WastewaterMeasurement.location_name)
        .order_by(func.max(WastewaterMeasurement.sample_date).desc())
        .limit(10)
        .all()
    )
    return {
        "total_measurements": total,
        "active_locations": active,
        "date_range": {"from": min_date, "to": max_date},
        "average_viral_concentration": float(avg_viral) if avg_viral is not None else None,
        "max_viral_concentration": float(max_viral) if max_viral is not None else None,
        "latest_locations": [{"location_name": row[0], "latest_sample_date": row[1]} for row in latest],
    }

