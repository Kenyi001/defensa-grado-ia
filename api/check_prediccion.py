"""
Self-check minimo de la logica de prediccion (sin levantar servidor).

  python -m api.check_prediccion
"""

from __future__ import annotations

import sys
from pathlib import Path

# Raiz del repo en sys.path si se ejecuta como script suelto
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from api.config import CAMPO_A_FEATURE, FEATURE_COLS
from api.logica.prediccion import predecir_lote, predecir_uno


def _fila_sintetica() -> dict:
    out: dict = {}
    for campo, col in CAMPO_A_FEATURE.items():
        if col in (
            "Previous qualification (grade)",
            "Admission grade",
            "Curricular units 1st sem (grade)",
            "Curricular units 2nd sem (grade)",
            "Unemployment rate",
            "Inflation rate",
            "GDP",
        ):
            out[campo] = 0.0
        elif col in (
            "Marital Status",
            "Application mode",
            "Previous qualification",
            "Nacionality",
            "Mother's qualification",
            "Father's qualification",
        ):
            out[campo] = 1
        elif col == "Age at enrollment":
            out[campo] = 20
        elif col == "Course":
            out[campo] = 171
        else:
            out[campo] = 0
    out["previous_qualification_grade"] = 120.0
    out["admission_grade"] = 120.0
    out["unemployment_rate"] = 10.0
    out["inflation_rate"] = 1.0
    out["gdp"] = 1.0
    return out


def main() -> int:
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(40, len(FEATURE_COLS))), columns=FEATURE_COLS)
    y = (X["Curricular units 2nd sem (approved)"] < 0).astype(int)
    clf = RandomForestClassifier(n_estimators=10, random_state=0)
    clf.fit(X, y)

    fila = _fila_sintetica()
    r1 = predecir_uno(clf, fila, umbral=0.5, modelo_version="test", sede_id="scz")
    assert 0.0 <= r1["probabilidad_desercion"] <= 1.0
    assert r1["sede_id"] == "scz"
    assert r1["clase"] in ("desertor", "no_desertor")

    lote = predecir_lote(clf, [fila, fila], ["a", "b"], umbral=0.3, modelo_version="test")
    assert len(lote) == 2
    assert lote[0]["sede_id"] == "a"
    assert lote[1]["umbral"] == 0.3
    assert "sede_id" not in CAMPO_A_FEATURE
    assert len(FEATURE_COLS) == 36

    print("check_prediccion: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
