from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MeasurementBase(BaseModel):
    sample_date: date
    location_name: str = Field(min_length=1)
    city: str = Field(default="Unknown")
    country: str = Field(default="Unknown")
    latitude: float | None = None
    longitude: float | None = None
    population_served: int = Field(gt=0)
    flow_rate_m3_day: float = Field(gt=0)
    viral_concentration_gc_l: float = Field(ge=0)
    temperature_c: float | None = None
    rainfall_mm: float | None = Field(default=None, ge=0)
    ph: float | None = Field(default=None, ge=0, le=14)
    turbidity_ntu: float | None = Field(default=None, ge=0)
    clinical_cases: int | None = Field(default=None, ge=0)
    notes: str | None = None


class MeasurementCreate(MeasurementBase):
    pass


class MeasurementUpdate(BaseModel):
    sample_date: date | None = None
    location_name: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    population_served: int | None = Field(default=None, gt=0)
    flow_rate_m3_day: float | None = Field(default=None, gt=0)
    viral_concentration_gc_l: float | None = Field(default=None, ge=0)
    temperature_c: float | None = None
    rainfall_mm: float | None = Field(default=None, ge=0)
    ph: float | None = Field(default=None, ge=0, le=14)
    turbidity_ntu: float | None = Field(default=None, ge=0)
    clinical_cases: int | None = Field(default=None, ge=0)
    notes: str | None = None


class MeasurementRead(MeasurementBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MeasurementFilters(BaseModel):
    location_name: str | None = None
    city: str | None = None
    country: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    limit: int = Field(default=200, ge=1, le=5000)
    offset: int = Field(default=0, ge=0)


class DatasetSummary(BaseModel):
    total_measurements: int
    active_locations: int
    date_range: dict[str, date | None]
    average_viral_concentration: float | None
    max_viral_concentration: float | None
    latest_locations: list[dict[str, Any]]


class SimulationRequest(BaseModel):
    save: bool = False
    name: str | None = None
    location_name: str | None = None


class ViralDecayRequest(SimulationRequest):
    S: float = Field(ge=0)
    k: float = Field(ge=0)
    d: float = Field(ge=0)
    V0: float = Field(ge=0)
    t_final: float = Field(gt=0)
    step: float = Field(gt=0)
    method: Literal["euler", "heun", "rk4"] = "rk4"

    @model_validator(mode="after")
    def validate_rates(self):
        if self.k + self.d <= 0:
            raise ValueError("k + d must be greater than zero")
        if self.step > self.t_final:
            raise ValueError("step must be lower than t_final")
        return self


class InfectionWastewaterRequest(SimulationRequest):
    beta: float = Field(gt=0)
    K: float = Field(gt=0)
    gamma: float = Field(ge=0)
    alpha: float = Field(ge=0)
    k: float = Field(ge=0)
    d: float = Field(ge=0)
    I0: float = Field(ge=0)
    V0: float = Field(ge=0)
    t_final: float = Field(gt=0)
    step: float = Field(gt=0)
    method: Literal["euler", "heun", "rk4"] = "rk4"

    @model_validator(mode="after")
    def validate_model(self):
        if self.k + self.d <= 0:
            raise ValueError("k + d must be greater than zero")
        if self.step > self.t_final:
            raise ValueError("step must be lower than t_final")
        return self


class NonHomogeneousEventRequest(SimulationRequest):
    event_type: Literal["constant", "sinusoidal", "outbreak_shock", "rainfall_dilution"]
    base_source: float = Field(ge=0)
    amplitude: float = Field(default=0, ge=0)
    frequency: float = Field(default=0, ge=0)
    shock_start: float | None = Field(default=None, ge=0)
    shock_end: float | None = Field(default=None, ge=0)
    shock_magnitude: float = Field(default=0, ge=0)
    rainfall_start: float | None = Field(default=None, ge=0)
    rainfall_end: float | None = Field(default=None, ge=0)
    dilution_multiplier: float = Field(default=1, gt=0)
    k: float = Field(ge=0)
    d: float = Field(ge=0)
    V0: float = Field(ge=0)
    t_final: float = Field(gt=0)
    step: float = Field(gt=0)
    method: Literal["euler", "heun", "rk4"] = "rk4"


class BifurcationRequest(BaseModel):
    parameter_name: Literal["beta", "gamma"]
    parameter_min: float = Field(ge=0)
    parameter_max: float = Field(gt=0)
    steps: int = Field(default=80, ge=2, le=500)
    K: float = Field(gt=0)
    beta: float = Field(gt=0)
    gamma: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.parameter_min >= self.parameter_max:
            raise ValueError("parameter_min must be lower than parameter_max")
        return self


class PhaseDiagramRequest(BaseModel):
    I_min: float = Field(ge=0)
    I_max: float = Field(gt=0)
    V_min: float = Field(ge=0)
    V_max: float = Field(gt=0)
    grid_size: int = Field(default=20, ge=5, le=60)
    beta: float = Field(gt=0)
    K: float = Field(gt=0)
    gamma: float = Field(ge=0)
    alpha: float = Field(ge=0)
    k: float = Field(ge=0)
    d: float = Field(ge=0)


class LyapunovRiskRequest(BaseModel):
    I_values: list[float] | None = None
    V_values: list[float] | None = None
    a: float = Field(default=1.0, gt=0)
    b: float = Field(default=1.0, gt=0)
    I_safe: float = Field(default=100.0, ge=0)
    V_safe: float = Field(default=10000.0, ge=0)
    parameters: InfectionWastewaterRequest | None = None


class CalibrationRequest(BaseModel):
    location_name: str = Field(min_length=1)
    date_from: date | None = None
    date_to: date | None = None
    model_type: Literal["viral-decay-1d", "infection-wastewater-2d"] = "infection-wastewater-2d"


class SimulationResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    model_type: str
    parameters: dict[str, Any]
    initial_conditions: dict[str, Any]
    time: list[float]
    series: dict[str, list[float]]
    equilibria: list[dict[str, Any]]
    stability: dict[str, Any]
    risk: dict[str, Any]
    interpretation: str
    saved_simulation_id: int | None = None


class SimulationRunRead(BaseModel):
    id: int
    name: str
    model_type: str
    location_name: str | None = None
    parameters: dict[str, Any]
    initial_conditions: dict[str, Any]
    result: dict[str, Any]
    equilibria: Any | None = None
    stability: Any | None = None
    risk: Any | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
