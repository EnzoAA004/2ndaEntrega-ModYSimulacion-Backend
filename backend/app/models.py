from datetime import datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WastewaterMeasurement(TimestampMixin, Base):
    __tablename__ = "wastewater_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sample_date: Mapped[datetime] = mapped_column(Date, index=True)
    location_name: Mapped[str] = mapped_column(String(160), index=True)
    city: Mapped[str] = mapped_column(String(120), index=True)
    country: Mapped[str] = mapped_column(String(120), index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    population_served: Mapped[int] = mapped_column(Integer)
    flow_rate_m3_day: Mapped[float] = mapped_column(Float)
    viral_concentration_gc_l: Mapped[float] = mapped_column(Float, index=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    turbidity_ntu: Mapped[float | None] = mapped_column(Float, nullable=True)
    clinical_cases: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    model_type: Mapped[str] = mapped_column(String(80), index=True)
    location_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    parameters_json: Mapped[str] = mapped_column(Text)
    initial_conditions_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    equilibrium_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    stability_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportedDataset(Base):
    __tablename__ = "imported_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    source_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    rows_imported: Mapped[int] = mapped_column(Integer)
    columns_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

