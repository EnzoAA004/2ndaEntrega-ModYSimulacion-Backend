# Wastewater Sentinel Backend

API FastAPI para vigilancia epidemiologica temprana mediante analisis de aguas residuales. Incluye carga de mediciones, datos demo, analitica epidemiologica, simulaciones de sistemas dinamicos, estabilidad local, bifurcacion, diagramas de fase, riesgo tipo Lyapunov, calibracion desde datos historicos y prediccion aplicada.

## Stack

- Python 3.11+
- FastAPI y Uvicorn
- SQLAlchemy 2
- PostgreSQL
- Pydantic 2
- NumPy, Pandas, SciPy
- Pytest

## Instalacion local

1. Entrar a la carpeta backend.
2. Crear entorno virtual.
3. Instalar requirements.
4. Crear archivo de entorno a partir de .env.example.
5. Ejecutar el servidor con Uvicorn.

La documentacion interactiva queda disponible en `/docs` y el health check en `/api/health`.

## Endpoints disponibles

### Mediciones y dataset

- GET /api/measurements
- POST /api/measurements
- GET /api/measurements/locations
- GET /api/measurements/latest
- POST /api/datasets/upload
- POST /api/datasets/seed-demo
- GET /api/datasets/summary

### Analitica actual

- GET /api/analytics/overview
- GET /api/analytics/location/{location_name}
- GET /api/analytics/risk-table

### Analitica predictiva avanzada

- GET /api/analytics/location/{location_name}/forecast
- GET /api/analytics/predictive-ranking
- GET /api/analytics/map-risk
- GET /api/analytics/report
- GET /api/analytics/report/html
- GET /api/analytics/export/measurements.csv

### Simulaciones

- POST /api/simulations/viral-decay-1d
- POST /api/simulations/infection-wastewater-2d
- POST /api/simulations/non-homogeneous-event
- POST /api/simulations/scenario-compare
- POST /api/simulations/bifurcation
- POST /api/simulations/phase-diagram
- POST /api/simulations/lyapunov-risk
- POST /api/simulations/calibrate

## Datos demo

El endpoint seed demo inserta 720 mediciones para cuatro ubicaciones: Buenos Aires Norte, Buenos Aires Sur, Cordoba Central y Mendoza Oeste. Cada ubicacion tiene 180 dias con tendencia, ruido, lluvia, dilucion, temperatura estacional, brotes artificiales y casos clinicos retrasados.

## Modelos matematicos

### Modelo 1D

dV/dt = S - kV - dV.

Representa la evolucion de carga viral en aguas residuales. El equilibrio es V* = S / (k+d). Si k+d es positivo, el equilibrio es estable.

### Modelo 2D

dI/dt = beta I(1 - I/K) - gamma I.

dV/dt = alpha I - (k+d)V.

Vincula infectados estimados con carga viral observada. El backend calcula equilibrios, jacobiano, autovalores, estabilidad local y riesgo temporal.

### Prediccion aplicada

El forecast ajusta una tendencia log-lineal sobre la carga viral historica reciente. Devuelve prediccion base, banda de incertidumbre, escenario de mitigacion, escenario de crecimiento alto, fechas de cruce de umbral, tasa de crecimiento, tiempo de duplicacion y recomendacion automatica.

### Ranking predictivo

El ranking predictivo ejecuta predicciones para todas las ubicaciones y ordena por score. El score combina riesgo proyectado, crecimiento esperado, magnitud maxima y cruce de umbrales.

### Mapa operativo

El mapa operativo devuelve una vista resumida por ubicacion con riesgo actual, riesgo proyectado y score predictivo. Sirve para alimentar el panel visual del frontend.

### Calibracion

La calibracion estima parametros desde datos historicos y devuelve payloads listos para correr simulaciones 1D y 2D.

## Reportes

El backend permite generar reporte ejecutivo JSON, reporte HTML imprimible y exportacion CSV de mediciones.

## Deploy

En produccion se debe configurar la base PostgreSQL, los origenes permitidos por CORS y las variables de entorno del servicio. No se deben subir credenciales reales al repositorio.
