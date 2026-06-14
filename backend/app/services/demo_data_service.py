from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from app.schemas import MeasurementCreate


LOCATIONS = [
    ("Buenos Aires - Planta Norte", "Buenos Aires", "Argentina", -34.54, -58.46, 850_000),
    ("Buenos Aires - Planta Sur", "Buenos Aires", "Argentina", -34.70, -58.40, 620_000),
    ("Córdoba - Planta Central", "Córdoba", "Argentina", -31.42, -64.18, 520_000),
    ("Mendoza - Planta Oeste", "Mendoza", "Argentina", -32.89, -68.85, 300_000),
]


def generate_demo_measurements(days: int = 180, seed: int = 42) -> list[MeasurementCreate]:
    rng = np.random.default_rng(seed)
    start = date.today() - timedelta(days=days - 1)
    generated: list[MeasurementCreate] = []
    viral_by_location: dict[str, list[float]] = {}

    for loc_idx, (name, city, country, lat, lon, population) in enumerate(LOCATIONS):
        values: list[float] = []
        for day in range(days):
            seasonal_temp = 18 + 8 * np.sin(2 * np.pi * (day + 30) / 365)
            rainfall = max(0, rng.gamma(1.2, 5.0) - 3.0)
            base = 35_000 + loc_idx * 12_000 + 8_000 * np.sin(2 * np.pi * day / 60)
            outbreak = 0.0
            if loc_idx == 0 and 45 <= day <= 80:
                outbreak = 280_000 * np.exp(-((day - 62) ** 2) / (2 * 9**2))
            if loc_idx == 2 and 100 <= day <= 140:
                outbreak = 450_000 * np.exp(-((day - 120) ** 2) / (2 * 11**2))
            if loc_idx == 3 and 125 <= day <= 155:
                outbreak = 130_000 * np.exp(-((day - 140) ** 2) / (2 * 7**2))
            dilution = 1 / (1 + rainfall / 45)
            noise = rng.normal(1.0, 0.12)
            viral = max(500.0, (base + outbreak) * dilution * noise)
            values.append(float(viral))

            flow = population * 0.18 + rainfall * population * 0.002 + rng.normal(0, population * 0.006)
            generated.append(
                MeasurementCreate(
                    sample_date=start + timedelta(days=day),
                    location_name=name,
                    city=city,
                    country=country,
                    latitude=lat,
                    longitude=lon,
                    population_served=population,
                    flow_rate_m3_day=max(1000.0, float(flow)),
                    viral_concentration_gc_l=float(viral),
                    temperature_c=float(seasonal_temp + rng.normal(0, 1.5)),
                    rainfall_mm=float(rainfall),
                    ph=float(np.clip(rng.normal(7.2, 0.25), 6.2, 8.4)),
                    turbidity_ntu=float(max(1.0, rng.normal(20 + rainfall * 0.7, 5))),
                    clinical_cases=None,
                    notes="Dato demo generado automáticamente.",
                )
            )
        viral_by_location[name] = values

    for row in generated:
        series = viral_by_location[row.location_name]
        day = (row.sample_date - start).days
        lag = 8 if row.location_name.startswith("Buenos Aires") else 9
        lag_idx = max(0, day - lag)
        clinical = max(0, int(series[lag_idx] / 18_000 + rng.normal(0, 4)))
        row.clinical_cases = clinical

    return generated

