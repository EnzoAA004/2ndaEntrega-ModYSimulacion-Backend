from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services import dataset_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    source_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Debe subir un archivo CSV.")
    try:
        return dataset_service.import_csv(db, await file.read(), file.filename, source_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/seed-demo")
def seed_demo(db: Session = Depends(get_db)):
    return dataset_service.seed_demo(db)


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    return dataset_service.summary(db)

