from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import create_tables
from app.routers import analytics, datasets, health, measurements, simulations


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="API para vigilancia epidemiológica temprana mediante análisis de aguas residuales.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    create_tables()


app.include_router(health.router, prefix="/api")
app.include_router(measurements.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(simulations.router, prefix="/api")

