"""Contratos Pydantic de entrada/salida del servicio."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EstudianteInput(BaseModel):
    """36 predictoras del UCI 697 + sede_id opcional (metadata, no feature)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "marital_status": 1,
                "application_mode": 17,
                "application_order": 5,
                "course": 171,
                "daytime_evening_attendance": 1,
                "previous_qualification": 1,
                "previous_qualification_grade": 122.0,
                "nacionality": 1,
                "mothers_qualification": 19,
                "fathers_qualification": 12,
                "mothers_occupation": 5,
                "fathers_occupation": 9,
                "admission_grade": 127.3,
                "displaced": 1,
                "educational_special_needs": 0,
                "debtor": 0,
                "tuition_fees_up_to_date": 1,
                "gender": 1,
                "scholarship_holder": 0,
                "age_at_enrollment": 20,
                "international": 0,
                "cu_1st_credited": 0,
                "cu_1st_enrolled": 0,
                "cu_1st_evaluations": 0,
                "cu_1st_approved": 0,
                "cu_1st_grade": 0.0,
                "cu_1st_without_evaluations": 0,
                "cu_2nd_credited": 0,
                "cu_2nd_enrolled": 0,
                "cu_2nd_evaluations": 0,
                "cu_2nd_approved": 0,
                "cu_2nd_grade": 0.0,
                "cu_2nd_without_evaluations": 0,
                "unemployment_rate": 10.8,
                "inflation_rate": 1.4,
                "gdp": 1.74,
                "sede_id": "cochabamba",
            }
        }
    )

    marital_status: int = Field(..., ge=1, le=6)
    application_mode: int = Field(..., ge=1, le=57)
    application_order: int = Field(..., ge=0, le=9)
    course: int = Field(..., ge=1, le=9999)
    daytime_evening_attendance: int = Field(..., ge=0, le=1)
    previous_qualification: int = Field(..., ge=1, le=43)
    previous_qualification_grade: float = Field(..., ge=0, le=200)
    nacionality: int = Field(..., ge=1, le=200)
    mothers_qualification: int = Field(..., ge=1, le=44)
    fathers_qualification: int = Field(..., ge=1, le=44)
    mothers_occupation: int = Field(..., ge=0, le=200)
    fathers_occupation: int = Field(..., ge=0, le=200)
    admission_grade: float = Field(..., ge=0, le=200)
    displaced: int = Field(..., ge=0, le=1)
    educational_special_needs: int = Field(..., ge=0, le=1)
    debtor: int = Field(..., ge=0, le=1)
    tuition_fees_up_to_date: int = Field(..., ge=0, le=1)
    gender: int = Field(..., ge=0, le=1)
    scholarship_holder: int = Field(..., ge=0, le=1)
    age_at_enrollment: int = Field(..., ge=15, le=100)
    international: int = Field(..., ge=0, le=1)
    cu_1st_credited: int = Field(..., ge=0, le=30)
    cu_1st_enrolled: int = Field(..., ge=0, le=30)
    cu_1st_evaluations: int = Field(..., ge=0, le=50)
    cu_1st_approved: int = Field(..., ge=0, le=30)
    cu_1st_grade: float = Field(..., ge=0, le=20)
    cu_1st_without_evaluations: int = Field(..., ge=0, le=20)
    cu_2nd_credited: int = Field(..., ge=0, le=30)
    cu_2nd_enrolled: int = Field(..., ge=0, le=30)
    cu_2nd_evaluations: int = Field(..., ge=0, le=50)
    cu_2nd_approved: int = Field(..., ge=0, le=30)
    cu_2nd_grade: float = Field(..., ge=0, le=20)
    cu_2nd_without_evaluations: int = Field(..., ge=0, le=20)
    unemployment_rate: float = Field(..., ge=0, le=30)
    inflation_rate: float = Field(..., ge=-5, le=20)
    gdp: float = Field(..., ge=-10, le=10)

    # Metadata de peticion: NO se pasa al Random Forest.
    sede_id: Optional[str] = Field(
        default=None,
        description="Sede UNAL (filtro/etiqueta de reporte; no es predictor)",
        max_length=64,
    )


class PrediccionOutput(BaseModel):
    """Clase predicha + probabilidad de desercion (y metadatos de decision)."""

    clase: Literal["desertor", "no_desertor"]
    probabilidad_desercion: float = Field(..., ge=0, le=1)
    en_riesgo: bool
    umbral: float = Field(..., ge=0, le=1)
    modelo_version: str
    sede_id: Optional[str] = None


class LoteInput(BaseModel):
    estudiantes: list[EstudianteInput] = Field(..., min_length=1, max_length=500)
    umbral: float = Field(default=0.5, ge=0, le=1)
    sede_id: Optional[str] = Field(
        default=None,
        description="Sede por defecto para filas que no traen sede_id propia",
        max_length=64,
    )


class LoteOutput(BaseModel):
    total: int
    en_riesgo: int
    umbral: float
    modelo_version: str
    predicciones: list[PrediccionOutput]


class SaludOutput(BaseModel):
    estado: Literal["ok"]
    modelo_version: str
    modelo_cargado: bool
    # Metricas sobre el conjunto de prueba, si el modelo cargado las trae
    # serializadas (el placeholder sintetico no las tiene). Los criterios
    # viajan junto a los valores para que el frontend no repita los numeros
    # de la Fase 1 del caso.
    recall: Optional[float] = None
    precision: Optional[float] = None
    roc_auc: Optional[float] = None
    criterio_recall: Optional[float] = None
    criterio_precision: Optional[float] = None


class ReporteAgregado(BaseModel):
    """Conteos por clase y promedio de probabilidad (corte por umbral)."""

    total: int
    en_riesgo: int
    no_en_riesgo: int
    tasa_riesgo: float
    probabilidad_promedio: float
    umbral: float
    sede_id: Optional[str] = None
    carrera: Optional[int] = None
    modelo_version: str


class EstudianteReporte(BaseModel):
    indice: int
    probabilidad_desercion: float
    en_riesgo: bool
    clase: Literal["desertor", "no_desertor"]
    carrera: Optional[int] = None
    sede_id: Optional[str] = None
    # Por que este estudiante esta señalado y que corresponde hacer. Sin esto
    # el reporte es una lista de probabilidades: no permite actuar.
    motivos: str = ""
    accion_sugerida: str = ""


class ReporteOutput(BaseModel):
    agregado: ReporteAgregado
    estudiantes: list[EstudianteReporte]
    total_filtrado: int
    limite: int
    desplazamiento: int
