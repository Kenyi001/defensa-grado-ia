"""Logica pura de prediccion — sin FastAPI, testeable aislada."""

from __future__ import annotations

from typing import Any

import joblib
import numpy as np
import pandas as pd

from api.config import CAMPO_A_FEATURE, FEATURE_COLS, MODELO_VERSION, UMBRAL_DEFAULT


def cargar_paquete(ruta: str | Any) -> dict[str, Any]:
    """Carga el artefacto joblib. Espera dict con model + feature_names + version."""
    paquete = joblib.load(ruta)
    if not isinstance(paquete, dict) or "model" not in paquete:
        raise ValueError(
            "El .joblib debe ser un dict con clave 'model' "
            "(usa models/entrenar_placeholder.py, o exporta tu modelo real "
            "desde el notebook con joblib.dump({'model': clf, "
            "'feature_names': FEATURE_COLS, ...}))."
        )
    nombres = paquete.get("feature_names")
    if nombres is not None and list(nombres) != FEATURE_COLS:
        raise ValueError(
            "feature_names del artefacto no coinciden con FEATURE_COLS de la API."
        )
    return paquete


def fila_desde_campos(campos: dict[str, Any]) -> dict[str, Any]:
    """Mapea snake_case del contrato JSON a nombres de columna del modelo."""
    return {CAMPO_A_FEATURE[k]: campos[k] for k in CAMPO_A_FEATURE}


def matriz_desde_filas(filas: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(filas)[FEATURE_COLS]


def predecir_proba(modelo: Any, X: pd.DataFrame) -> np.ndarray:
    """Probabilidad de clase positiva (desertor=1)."""
    if hasattr(modelo, "predict_proba"):
        return modelo.predict_proba(X)[:, 1]
    # Fallback raro: decision_function -> sigmoid no; usar predict como 0/1
    return modelo.predict(X).astype(float)


def predecir_uno(
    modelo: Any,
    campos: dict[str, Any],
    *,
    umbral: float = UMBRAL_DEFAULT,
    modelo_version: str = MODELO_VERSION,
    sede_id: str | None = None,
) -> dict[str, Any]:
    fila = fila_desde_campos(campos)
    X = matriz_desde_filas([fila])
    proba = float(predecir_proba(modelo, X)[0])
    en_riesgo = proba >= umbral
    return {
        "clase": "desertor" if en_riesgo else "no_desertor",
        "probabilidad_desercion": round(proba, 6),
        "en_riesgo": en_riesgo,
        "umbral": umbral,
        "modelo_version": modelo_version,
        "sede_id": sede_id,
    }


def predecir_lote(
    modelo: Any,
    lista_campos: list[dict[str, Any]],
    sedes: list[str | None],
    *,
    umbral: float = UMBRAL_DEFAULT,
    modelo_version: str = MODELO_VERSION,
) -> list[dict[str, Any]]:
    filas = [fila_desde_campos(c) for c in lista_campos]
    X = matriz_desde_filas(filas)
    probas = predecir_proba(modelo, X)
    out: list[dict[str, Any]] = []
    for i, proba in enumerate(probas):
        p = float(proba)
        en_riesgo = p >= umbral
        out.append(
            {
                "clase": "desertor" if en_riesgo else "no_desertor",
                "probabilidad_desercion": round(p, 6),
                "en_riesgo": en_riesgo,
                "umbral": umbral,
                "modelo_version": modelo_version,
                "sede_id": sedes[i],
            }
        )
    return out
