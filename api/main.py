"""
App FastAPI: carga el modelo UNA vez al arrancar (lifespan).

Start (local):
  uvicorn api.main:app --reload

Start (Render):
  uvicorn api.main:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from api.config import MODELO_VERSION, RUTA_DATASET, RUTA_MODELO, UMBRAL_DEFAULT
from api.logica.prediccion import cargar_paquete
from api.logica.reporte import cargar_poblacion
from api.routers import prediccion, reportes, salud


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not RUTA_MODELO.is_file():
        raise RuntimeError(
            f"Modelo no encontrado: {RUTA_MODELO}. "
            "Ejecuta: python models/entrenar_placeholder.py "
            "(o exporta tu modelo real desde el notebook, Fase 5)"
        )
    paquete = cargar_paquete(RUTA_MODELO)
    app.state.modelo = paquete["model"]
    app.state.modelo_version = paquete.get("version", MODELO_VERSION)
    app.state.umbral_default = float(paquete.get("threshold_default", UMBRAL_DEFAULT))
    app.state.poblacion = cargar_poblacion(RUTA_DATASET)
    yield
    app.state.modelo = None
    app.state.poblacion = None


app = FastAPI(
    title="Alerta Temprana — Desercion Estudiantil",
    description=(
        "Servicio de inferencia del Random Forest (UCI 697). "
        "Entrenamiento offline en el notebook (Fase 5); "
        "aqui solo se predice. Multi-sede via sede_id (metadata, no feature)."
    ),
    version=MODELO_VERSION,
    lifespan=lifespan,
)

app.include_router(salud.router)
app.include_router(prediccion.router)
app.include_router(reportes.router)

# La raiz sirve la interfaz de Bienestar Universitario. Sin esta ruta, entrar a
# la URL del servicio devolvia {"detail":"Not Found"} — correcto para una API,
# pero da impresion de roto a quien no sabe que las rutas son /salud, /predecir
# y /reporte. En una demostracion en vivo eso es un problema real.
INTERFAZ = Path(__file__).resolve().parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
async def interfaz():
    """Panel de Bienestar Universitario: lista priorizada y evaluacion puntual."""
    return FileResponse(INTERFAZ)
