"""
Entrena un Random Forest placeholder con datos SINTETICOS.

No usa el dataset UCI 697. Solo sirve para probar el contrato de la API
(Swagger, /predecir, /reporte) hasta que el notebook exporte el modelo real.

Uso (desde la raiz del repo):
  python models/entrenar_placeholder.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from api.config import DIR_MODELOS, FEATURE_COLS  # noqa: E402

SEMILLA = 42
RUTA_SALIDA = DIR_MODELOS / "random_forest_v1.joblib"
N_MUESTRAS = 400
N_ARBOLES = 20


def main() -> int:
    X_arr, y = make_classification(
        n_samples=N_MUESTRAS,
        n_features=len(FEATURE_COLS),
        n_informative=20,
        n_redundant=8,
        n_clusters_per_class=2,
        class_sep=1.2,
        random_state=SEMILLA,
    )
    X = pd.DataFrame(X_arr, columns=FEATURE_COLS)

    clf = RandomForestClassifier(
        n_estimators=N_ARBOLES,
        max_depth=6,
        random_state=SEMILLA,
        n_jobs=-1,
    )
    clf.fit(X, y)

    DIR_MODELOS.mkdir(parents=True, exist_ok=True)
    paquete = {
        "model": clf,
        "feature_names": FEATURE_COLS,
        "version": "v1",
        "threshold_default": 0.5,
        "placeholder": True,
        "target_positive": "Dropout",
        "train_rows": int(N_MUESTRAS),
    }
    joblib.dump(paquete, RUTA_SALIDA)
    print(
        f"OK placeholder -> {RUTA_SALIDA} "
        f"({RUTA_SALIDA.stat().st_size / 1024:.1f} KB, "
        f"n={N_MUESTRAS}, trees={N_ARBOLES})"
    )
    print("Reemplazar por el modelo real del notebook (Fase 5) antes de la defensa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
