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
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    create_tables()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "message": "Wastewater Sentinel API is running",
        "docs": "/docs",
        "health": "/api/health",
    }


# Main API namespace used by the deployed frontend when VITE_API_URL ends with /api.
app.include_router(health.router, prefix="/api")
app.include_router(measurements.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(simulations.router, prefix="/api")

# Compatibility namespace for frontend builds that were deployed with VITE_API_URL
# without the /api suffix, e.g. https://wastewater-sentinel-backend.onrender.com.
# This keeps the app working while the Vercel environment variable is corrected.
app.include_router(measurements.router)
app.include_router(datasets.router)
app.include_router(analytics.router)
app.include_router(simulations.router)
