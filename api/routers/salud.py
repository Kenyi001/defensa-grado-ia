"""Endpoint de salud del servicio."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.config import CRITERIO_PRECISION_MIN, CRITERIO_RECALL_MIN
from api.schemas import SaludOutput

router = APIRouter(tags=["salud"])


@router.get("/salud", response_model=SaludOutput)
def salud(request: Request) -> SaludOutput:
    """Confirma que el servicio responde y el modelo esta cargado en memoria.

    Si el modelo trae sus metricas de test serializadas (el modelo real las
    tiene; el placeholder sintetico no), tambien informa Recall/Precision/AUC
    contra los criterios declarados en la Fase 1 del caso — la Evaluacion de
    CRISP-DM es de negocio, no solo metricas, y esto lo hace visible en vivo.
    """
    if getattr(request.app.state, "modelo", None) is None:
        raise HTTPException(status_code=503, detail="Modelo no cargado")

    metricas = getattr(request.app.state, "metricas_test", None)
    extra = {}
    if metricas:
        extra = {
            "recall": metricas.get("recall"),
            "precision": metricas.get("precision"),
            "roc_auc": metricas.get("roc_auc"),
            "criterio_recall": CRITERIO_RECALL_MIN,
            "criterio_precision": CRITERIO_PRECISION_MIN,
        }

    return SaludOutput(
        estado="ok",
        modelo_version=request.app.state.modelo_version,
        modelo_cargado=True,
        **extra,
    )
