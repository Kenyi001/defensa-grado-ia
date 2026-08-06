"""Endpoints de prediccion individual y en lote."""

from __future__ import annotations

from fastapi import APIRouter, Request

from api.schemas import (
    EstudianteInput,
    LoteInput,
    LoteOutput,
    PrediccionOutput,
)
from api.logica.prediccion import predecir_lote, predecir_uno

router = APIRouter(tags=["prediccion"])


def _campos_features(est: EstudianteInput) -> dict:
    data = est.model_dump()
    data.pop("sede_id", None)
    return data


@router.post("/predecir", response_model=PrediccionOutput)
def predecir(body: EstudianteInput, request: Request) -> PrediccionOutput:
    """Predice riesgo de desercion para un estudiante (36 variables UCI 697)."""
    estado = request.app.state
    resultado = predecir_uno(
        estado.modelo,
        _campos_features(body),
        umbral=estado.umbral_default,
        modelo_version=estado.modelo_version,
        sede_id=body.sede_id,
    )
    return PrediccionOutput(**resultado)


@router.post("/predecir/lote", response_model=LoteOutput)
def predecir_en_lote(body: LoteInput, request: Request) -> LoteOutput:
    """Predice en lote. `sede_id` se extrae antes de pasar features al modelo."""
    estado = request.app.state
    sedes = [e.sede_id or body.sede_id for e in body.estudiantes]
    predicciones = predecir_lote(
        estado.modelo,
        [_campos_features(e) for e in body.estudiantes],
        sedes,
        umbral=body.umbral,
        modelo_version=estado.modelo_version,
    )
    return LoteOutput(
        total=len(predicciones),
        en_riesgo=sum(1 for p in predicciones if p["en_riesgo"]),
        umbral=body.umbral,
        modelo_version=estado.modelo_version,
        predicciones=[PrediccionOutput(**p) for p in predicciones],
    )
