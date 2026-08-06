"""Endpoint de salud del servicio."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.schemas import SaludOutput

router = APIRouter(tags=["salud"])


@router.get("/salud", response_model=SaludOutput)
def salud(request: Request) -> SaludOutput:
    """Confirma que el servicio responde y el modelo esta cargado en memoria."""
    if getattr(request.app.state, "modelo", None) is None:
        raise HTTPException(status_code=503, detail="Modelo no cargado")
    return SaludOutput(
        estado="ok",
        modelo_version=request.app.state.modelo_version,
        modelo_cargado=True,
    )
