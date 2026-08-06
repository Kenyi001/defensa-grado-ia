"""Configuracion del servicio de inferencia (sin dependencias de FastAPI)."""

from __future__ import annotations

import os
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DIR_MODELOS = RAIZ_PROYECTO / "models"
RUTA_MODELO = Path(
    os.getenv("MODELO_PATH", str(DIR_MODELOS / "random_forest_v1.joblib"))
)
RUTA_DATASET = Path(
    os.getenv(
        "DATASET_PATH",
        str(RAIZ_PROYECTO / "data" / "raw" / "desercion_estudiantil.csv"),
    )
)

MODELO_VERSION = os.getenv("MODELO_VERSION", "v1")
UMBRAL_DEFAULT = float(os.getenv("UMBRAL_DEFAULT", "0.5"))
LIMITE_REPORTE_DEFAULT = int(os.getenv("LIMITE_REPORTE_DEFAULT", "50"))
LIMITE_REPORTE_MAX = int(os.getenv("LIMITE_REPORTE_MAX", "500"))

# Placeholder multi-sede (metadata de peticion; el modelo no las ve).
SEDES: list[str] = [
    "la_paz",
    "santa_cruz",
    "cochabamba",
    "tarija",
    "el_alto",
]

# Orden EXACTO de columnas del CSV UCI 697 (sin Target). El modelo se entrena
# y se sirve con este orden — no reordenar.
FEATURE_COLS: list[str] = [
    "Marital Status",
    "Application mode",
    "Application order",
    "Course",
    "Daytime/evening attendance",
    "Previous qualification",
    "Previous qualification (grade)",
    "Nacionality",
    "Mother's qualification",
    "Father's qualification",
    "Mother's occupation",
    "Father's occupation",
    "Admission grade",
    "Displaced",
    "Educational special needs",
    "Debtor",
    "Tuition fees up to date",
    "Gender",
    "Scholarship holder",
    "Age at enrollment",
    "International",
    "Curricular units 1st sem (credited)",
    "Curricular units 1st sem (enrolled)",
    "Curricular units 1st sem (evaluations)",
    "Curricular units 1st sem (approved)",
    "Curricular units 1st sem (grade)",
    "Curricular units 1st sem (without evaluations)",
    "Curricular units 2nd sem (credited)",
    "Curricular units 2nd sem (enrolled)",
    "Curricular units 2nd sem (evaluations)",
    "Curricular units 2nd sem (approved)",
    "Curricular units 2nd sem (grade)",
    "Curricular units 2nd sem (without evaluations)",
    "Unemployment rate",
    "Inflation rate",
    "GDP",
]

# snake_case del contrato JSON -> nombre de columna del CSV/modelo
CAMPO_A_FEATURE: dict[str, str] = {
    "marital_status": "Marital Status",
    "application_mode": "Application mode",
    "application_order": "Application order",
    "course": "Course",
    "daytime_evening_attendance": "Daytime/evening attendance",
    "previous_qualification": "Previous qualification",
    "previous_qualification_grade": "Previous qualification (grade)",
    "nacionality": "Nacionality",
    "mothers_qualification": "Mother's qualification",
    "fathers_qualification": "Father's qualification",
    "mothers_occupation": "Mother's occupation",
    "fathers_occupation": "Father's occupation",
    "admission_grade": "Admission grade",
    "displaced": "Displaced",
    "educational_special_needs": "Educational special needs",
    "debtor": "Debtor",
    "tuition_fees_up_to_date": "Tuition fees up to date",
    "gender": "Gender",
    "scholarship_holder": "Scholarship holder",
    "age_at_enrollment": "Age at enrollment",
    "international": "International",
    "cu_1st_credited": "Curricular units 1st sem (credited)",
    "cu_1st_enrolled": "Curricular units 1st sem (enrolled)",
    "cu_1st_evaluations": "Curricular units 1st sem (evaluations)",
    "cu_1st_approved": "Curricular units 1st sem (approved)",
    "cu_1st_grade": "Curricular units 1st sem (grade)",
    "cu_1st_without_evaluations": "Curricular units 1st sem (without evaluations)",
    "cu_2nd_credited": "Curricular units 2nd sem (credited)",
    "cu_2nd_enrolled": "Curricular units 2nd sem (enrolled)",
    "cu_2nd_evaluations": "Curricular units 2nd sem (evaluations)",
    "cu_2nd_approved": "Curricular units 2nd sem (approved)",
    "cu_2nd_grade": "Curricular units 2nd sem (grade)",
    "cu_2nd_without_evaluations": "Curricular units 2nd sem (without evaluations)",
    "unemployment_rate": "Unemployment rate",
    "inflation_rate": "Inflation rate",
    "gdp": "GDP",
}

assert list(CAMPO_A_FEATURE.values()) == FEATURE_COLS
assert len(FEATURE_COLS) == 36
