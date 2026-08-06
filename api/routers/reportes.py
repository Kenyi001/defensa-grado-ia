"""Endpoint de reporte agregado configurable (triaje para Bienestar)."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from api.config import LIMITE_REPORTE_DEFAULT, LIMITE_REPORTE_MAX, SEDES, UMBRAL_DEFAULT
from api.logica.reporte import armar_reporte
from api.schemas import ReporteOutput

router = APIRouter(tags=["reportes"])


@router.get("/reporte", response_model=None)
def reporte(
    request: Request,
    sede_id: Optional[str] = Query(
        default=None,
        description=(
            "Filtro/etiqueta de sede (metadata de peticion; no es feature del modelo). "
            f"Valores validos: {', '.join(SEDES)}"
        ),
        max_length=64,
    ),
    umbral: float = Query(
        default=UMBRAL_DEFAULT,
        ge=0,
        le=1,
        description="Corte de probabilidad para declarar en riesgo (decision de negocio)",
    ),
    carrera: Optional[int] = Query(
        default=None,
        description="Codigo de carrera UCI (columna Course)",
    ),
    limite: int = Query(default=LIMITE_REPORTE_DEFAULT, ge=1, le=LIMITE_REPORTE_MAX),
    desplazamiento: int = Query(default=0, ge=0),
    formato: Literal["json", "csv"] = Query(default="json"),
):
    """
    Agrega predicciones sobre la poblacion cargada (Enrolled UCI o demo sintetica).

    Devuelve conteos por clase, tasa de riesgo y probabilidad promedio.
    Con `formato=csv` exporta el listado de estudiantes de la pagina.
    """
    if sede_id is not None and sede_id not in SEDES:
        raise HTTPException(
            status_code=422,
            detail=f"sede_id invalida. Use una de: {SEDES}",
        )

    estado = request.app.state
    if getattr(estado, "poblacion", None) is None:
        raise HTTPException(status_code=503, detail="Poblacion de reporte no disponible")

    data = armar_reporte(
        estado.modelo,
        estado.poblacion,
        umbral=umbral,
        sede_id=sede_id,
        carrera=carrera,
        limite=limite,
        desplazamiento=desplazamiento,
        modelo_version=estado.modelo_version,
    )

    if formato == "csv":
        lineas = [
            "indice,probabilidad_desercion,en_riesgo,clase,carrera,sede_id"
        ]
        for e in data["estudiantes"]:
            lineas.append(
                f"{e['indice']},{e['probabilidad_desercion']},{int(e['en_riesgo'])},"
                f"{e['clase']},{e['carrera'] or ''},{e['sede_id'] or ''}"
            )
        return PlainTextResponse(
            "\n".join(lineas) + "\n",
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="reporte_desercion.csv"'
            },
        )

    return ReporteOutput(**data)
