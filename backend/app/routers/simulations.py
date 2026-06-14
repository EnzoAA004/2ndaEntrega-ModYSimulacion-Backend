from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import SimulationRun
from app.schemas import (
    BifurcationRequest,
    CalibrationRequest,
    InfectionWastewaterRequest,
    LyapunovRiskRequest,
    NonHomogeneousEventRequest,
    PhaseDiagramRequest,
    SimulationResult,
    ViralDecayRequest,
)
from app.services import calibration_service, simulation_service

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.get("")
def list_simulations(db: Session = Depends(get_db)):
    return simulation_service.list_simulations(db)


@router.post("/viral-decay-1d", response_model=SimulationResult)
def viral_decay(payload: ViralDecayRequest, db: Session = Depends(get_db)):
    return simulation_service.viral_decay_1d(payload, db)


@router.post("/infection-wastewater-2d", response_model=SimulationResult)
def infection_wastewater(payload: InfectionWastewaterRequest, db: Session = Depends(get_db)):
    return simulation_service.infection_wastewater_2d(payload, db)


@router.post("/non-homogeneous-event", response_model=SimulationResult)
def non_homogeneous_event(payload: NonHomogeneousEventRequest, db: Session = Depends(get_db)):
    return simulation_service.non_homogeneous_event(payload, db)


@router.post("/bifurcation")
def bifurcation(payload: BifurcationRequest):
    return simulation_service.bifurcation(payload)


@router.post("/phase-diagram")
def phase_diagram(payload: PhaseDiagramRequest):
    return simulation_service.phase_diagram(payload)


@router.post("/lyapunov-risk")
def lyapunov_risk(payload: LyapunovRiskRequest):
    return simulation_service.lyapunov_risk(payload)


@router.post("/calibrate")
def calibrate(payload: CalibrationRequest, db: Session = Depends(get_db)):
    try:
        return calibration_service.calibrate(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{simulation_id}")
def get_simulation(simulation_id: int, db: Session = Depends(get_db)):
    row = db.get(SimulationRun, simulation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return simulation_service.simulation_to_read(row)


@router.delete("/{simulation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_simulation(simulation_id: int, db: Session = Depends(get_db)):
    row = db.get(SimulationRun, simulation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    db.delete(row)
    db.commit()
    return None
