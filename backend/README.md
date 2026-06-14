# Wastewater Sentinel Backend

API FastAPI para vigilancia epidemiológica temprana mediante análisis de aguas residuales. Incluye carga de mediciones, datos demo, analítica epidemiológica, simulaciones de sistemas dinámicos, estabilidad local, bifurcación, diagramas de fase, riesgo tipo Lyapunov y calibración inicial desde datos históricos.

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy 2
- PostgreSQL
- Pydantic 2
- NumPy, Pandas, SciPy
- python-dotenv
- Pytest

## Instalación

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Editá `.env` con tu conexión PostgreSQL:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/wastewater_sentinel
BACKEND_CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
APP_NAME=Wastewater Sentinel
ENVIRONMENT=development
```

Para una prueba rápida sin PostgreSQL, si no definís `DATABASE_URL` el backend usa SQLite local.

## PostgreSQL local

```bash
createdb wastewater_sentinel
```

O con Docker:

```bash
docker run --name wastewater-postgres -e POSTGRES_PASSWORD=password -e POSTGRES_USER=user -e POSTGRES_DB=wastewater_sentinel -p 5432:5432 -d postgres:16
```

Las tablas se crean automáticamente al iniciar la app. Para producción se recomienda sumar Alembic.

## Correr servidor

```bash
uvicorn app.main:app --reload
```

Swagger queda disponible en:

http://localhost:8000/docs

Health check:

```bash
curl http://localhost:8000/api/health
```

## Endpoints principales

- `GET /api/health`
- `GET /api/measurements`
- `POST /api/measurements`
- `GET /api/measurements/locations`
- `GET /api/measurements/latest`
- `POST /api/datasets/upload`
- `POST /api/datasets/seed-demo`
- `GET /api/datasets/summary`
- `GET /api/analytics/overview`
- `GET /api/analytics/location/{location_name}`
- `GET /api/analytics/risk-table`
- `POST /api/simulations/viral-decay-1d`
- `POST /api/simulations/infection-wastewater-2d`
- `POST /api/simulations/non-homogeneous-event`
- `POST /api/simulations/bifurcation`
- `POST /api/simulations/phase-diagram`
- `POST /api/simulations/lyapunov-risk`
- `POST /api/simulations/calibrate`

## Datos demo

`POST /api/datasets/seed-demo` inserta 720 mediciones:

- Buenos Aires - Planta Norte
- Buenos Aires - Planta Sur
- Córdoba - Planta Central
- Mendoza - Planta Oeste

Cada ubicación tiene 180 días con tendencia, ruido, lluvia, dilución, temperatura estacional, brotes artificiales y casos clínicos retrasados 7-10 días respecto de la señal viral.

## Modelos matemáticos

### Viral decay 1D

```text
dV/dt = S - kV - dV
V* = S / (k + d)
```

Métodos disponibles: `euler`, `heun`, `rk4`.

Ejemplo:

```json
{
  "S": 50000,
  "k": 0.08,
  "d": 0.04,
  "V0": 10000,
  "t_final": 60,
  "step": 1,
  "method": "rk4",
  "save": true
}
```

### Infection-wastewater 2D

```text
dI/dt = beta I (1 - I/K) - gamma I
dV/dt = alpha I - (k+d)V
```

Calcula equilibrios, jacobiano, autovalores, clasificación local y riesgo temporal.

Ejemplo:

```json
{
  "beta": 0.28,
  "K": 100000,
  "gamma": 0.08,
  "alpha": 40,
  "k": 0.08,
  "d": 0.04,
  "I0": 100,
  "V0": 10000,
  "t_final": 90,
  "step": 1,
  "method": "rk4",
  "save": true
}
```

## Tests

```bash
pytest
```

Los tests cubren métodos numéricos, clasificación de riesgo y simulaciones principales.

## Deploy en Render

1. Crear una base PostgreSQL en Render.
2. Crear un Web Service apuntando al repo.
3. Root directory: `backend`.
4. Build command: `pip install -r requirements.txt`.
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
6. Configurar `DATABASE_URL`, `BACKEND_CORS_ORIGINS`, `APP_NAME` y `ENVIRONMENT`.
