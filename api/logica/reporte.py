"""Agregacion de reportes sobre una poblacion de estudiantes (demo / Enrolled)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from api.config import FEATURE_COLS, MODELO_VERSION, SEDES, UMBRAL_DEFAULT
from api.logica.prediccion import predecir_proba


def _asignar_sedes(n: int, rng: np.random.Generator | None = None) -> list[str]:
    """Reparte sedes de forma determinista para poder filtrar en /reporte."""
    if rng is None:
        return [SEDES[i % len(SEDES)] for i in range(n)]
    return [SEDES[i] for i in rng.integers(0, len(SEDES), size=n)]


def poblacion_sintetica(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """
    Poblacion demo cuando no hay CSV UCI.
    Columnas = FEATURE_COLS + sede_id (metadata; el modelo no la ve).
    """
    rng = np.random.default_rng(seed)
    data: dict[str, Any] = {}
    for col in FEATURE_COLS:
        if col in (
            "Previous qualification (grade)",
            "Admission grade",
        ):
            data[col] = rng.uniform(95, 190, size=n)
        elif col in (
            "Curricular units 1st sem (grade)",
            "Curricular units 2nd sem (grade)",
        ):
            data[col] = rng.uniform(0, 20, size=n)
        elif col == "Unemployment rate":
            data[col] = rng.uniform(5, 16, size=n)
        elif col == "Inflation rate":
            data[col] = rng.uniform(-1, 5, size=n)
        elif col == "GDP":
            data[col] = rng.uniform(-4, 4, size=n)
        elif col == "Age at enrollment":
            data[col] = rng.integers(17, 45, size=n)
        elif col == "Course":
            data[col] = rng.choice([33, 171, 9003, 9119, 9130, 9147, 9670, 9853], size=n)
        elif col in (
            "Daytime/evening attendance",
            "Displaced",
            "Educational special needs",
            "Debtor",
            "Tuition fees up to date",
            "Gender",
            "Scholarship holder",
            "International",
        ):
            data[col] = rng.integers(0, 2, size=n)
        else:
            data[col] = rng.integers(0, 10, size=n)
    df = pd.DataFrame(data)
    df["sede_id"] = _asignar_sedes(n, rng)
    return df


def cargar_enrolled(ruta_csv: str | Path) -> pd.DataFrame:
    """Poblacion de inferencia: Target == Enrolled (sin ground truth)."""
    df = pd.read_csv(ruta_csv)
    if "Target" not in df.columns:
        raise ValueError("El CSV no tiene columna Target")
    enrolled = df[df["Target"] == "Enrolled"].copy()
    faltan = [c for c in FEATURE_COLS if c not in enrolled.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en el CSV: {faltan}")
    enrolled = enrolled.reset_index(drop=True)
    # Dataset real no tiene sede: se etiqueta de forma estable para demos multi-sede.
    enrolled["sede_id"] = _asignar_sedes(len(enrolled))
    return enrolled


def cargar_poblacion(ruta_csv: str | Path | None = None) -> pd.DataFrame:
    """CSV Enrolled si existe; si no, poblacion sintetica (demo sin UCI)."""
    if ruta_csv is not None and Path(ruta_csv).is_file():
        return cargar_enrolled(ruta_csv)
    return poblacion_sintetica()


# Medianas de quienes SI se graduaron, calculadas sobre el dataset real.
# Son la referencia contra la que se explica por que un estudiante esta en
# riesgo: no "porque el modelo lo dice", sino "aprobo 2 de las 6 materias que
# aprueba la mediana de quienes se graduan".
REFERENCIA_GRADUADOS = {
    "Curricular units 1st sem (approved)": 6,
    "Curricular units 2nd sem (approved)": 6,
    "Curricular units 2nd sem (grade)": 13,
}


def motivos_y_accion(fila: Any) -> tuple[str, str]:
    """Explica por que este estudiante esta señalado y que corresponde hacer.

    Devuelve (motivos, accion_sugerida).

    Un listado de probabilidades no es accionable: quien recibe el reporte
    necesita saber POR QUE. Los motivos se derivan comparando al estudiante
    contra la mediana de quienes se graduaron.

    Nota de diseño: "no tiene beca" NO se usa como motivo. La mediana de beca
    entre graduados es 0 y 664 de los 794 matriculados tampoco la tienen, asi
    que no distingue a nadie. Si funciona como ACCION (Politica 3, becas
    focalizadas al cuartil de mayor riesgo). Un motivo explica, una accion
    propone: no son lo mismo.
    """
    motivos: list[str] = []

    ap2 = fila.get("Curricular units 2nd sem (approved)")
    ap1 = fila.get("Curricular units 1st sem (approved)")
    nota2 = fila.get("Curricular units 2nd sem (grade)")
    al_dia = fila.get("Tuition fees up to date")
    deudor = fila.get("Debtor")
    becado = fila.get("Scholarship holder")

    if ap2 is not None and ap2 < REFERENCIA_GRADUADOS["Curricular units 2nd sem (approved)"]:
        motivos.append(f"Aprobo {int(ap2)} de 6 materias en el 2do semestre")
    if ap1 is not None and ap1 < REFERENCIA_GRADUADOS["Curricular units 1st sem (approved)"]:
        motivos.append(f"Aprobo {int(ap1)} de 6 materias en el 1er semestre")
    if nota2 is not None and nota2 < REFERENCIA_GRADUADOS["Curricular units 2nd sem (grade)"]:
        motivos.append(f"Nota promedio {nota2:.1f} en el 2do semestre (referencia: 13)")
    if al_dia is not None and int(al_dia) == 0:
        motivos.append("Matricula impaga")
    if deudor is not None and int(deudor) == 1:
        motivos.append("Registra deuda con la institucion")

    # La accion sale del motivo dominante, atada a las 3 politicas propuestas.
    financiero = (al_dia is not None and int(al_dia) == 0) or (
        deudor is not None and int(deudor) == 1
    )
    bajo_rendimiento = ap2 is not None and ap2 < 4

    if financiero:
        accion = "Alerta financiera preventiva"
    elif bajo_rendimiento:
        accion = "Tutoria academica temprana"
    elif becado is not None and int(becado) == 0 and motivos:
        accion = "Evaluar beca focalizada"
    elif motivos:
        accion = "Seguimiento academico"
    else:
        accion = "Sin accion inmediata"

    return " | ".join(motivos) if motivos else "Sin factores de alerta", accion


def resumen_correo(
    estudiantes: list[dict[str, Any]],
    umbral: float,
    sede_id: Optional[str] = None,
) -> str:
    """Cuerpo del correo que recibe Bienestar Universitario.

    Vive en la API y no en el script del cron para que la interfaz pueda
    mostrar exactamente el mismo texto que se enviaria: si el operador ve una
    vista previa distinta del correo real, la vista previa no sirve.
    """
    senalados = [e for e in estudiantes if e.get("en_riesgo")]
    total = len(senalados)
    alto = sum(1 for e in senalados if e["probabilidad_desercion"] >= 0.70)
    medio = total - alto

    acciones: dict[str, int] = {}
    for e in senalados:
        a = e.get("accion_sugerida", "")
        if a:
            acciones[a] = acciones.get(a, 0) + 1
    detalle = "\n".join(
        f"  - {a}: {n} estudiantes"
        for a, n in sorted(acciones.items(), key=lambda kv: -kv[1])
    ) or "  - sin acciones sugeridas"

    sede = sede_id or "todas las sedes"
    return f"""Reporte de alerta temprana - {sede}

Se identificaron {total} estudiantes por encima del umbral {umbral:.2f}:
  - Riesgo alto:  {alto}
  - Riesgo medio: {medio}

Acciones sugeridas:
{detalle}

El archivo adjunto trae la lista completa ordenada por prioridad, con el motivo
de cada caso y la accion que corresponde. Se atiende de arriba hacia abajo hasta
donde alcance la capacidad del periodo.

---
Este reporte estima RIESGO a partir del desempeno academico y la situacion
financiera del estudiante. No es un pronostico sobre ninguna persona en
particular ni una decision tomada: la intervencion la define Bienestar
Universitario. No se emplean genero, nacionalidad ni nivel educativo de los
padres como criterio de priorizacion.
"""


def armar_reporte(
    modelo: Any,
    df_poblacion: pd.DataFrame,
    *,
    umbral: float = UMBRAL_DEFAULT,
    sede_id: Optional[str] = None,
    carrera: Optional[int] = None,
    limite: int = 50,
    desplazamiento: int = 0,
    modelo_version: str = MODELO_VERSION,
) -> dict[str, Any]:
    """
    Puntua la poblacion, filtra por sede_id/carrera y pagina.

    sede_id no es feature del modelo: solo filtra/etiqueta el reporte.
    """
    df = df_poblacion
    if sede_id is not None:
        df = df[df["sede_id"] == sede_id]
    if carrera is not None:
        df = df[df["Course"] == carrera]

    if df.empty:
        agregado = {
            "total": 0,
            "en_riesgo": 0,
            "no_en_riesgo": 0,
            "tasa_riesgo": 0.0,
            "probabilidad_promedio": 0.0,
            "umbral": umbral,
            "sede_id": sede_id,
            "carrera": carrera,
            "modelo_version": modelo_version,
        }
        return {
            "agregado": agregado,
            "estudiantes": [],
            "total_filtrado": 0,
            "limite": limite,
            "desplazamiento": desplazamiento,
        }

    X = df[FEATURE_COLS]
    probas = predecir_proba(modelo, X)
    trabajo = pd.DataFrame(
        {
            "indice": df.index,
            "probabilidad_desercion": probas,
            "carrera": df["Course"].values,
            "sede_id": df["sede_id"].values,
        }
    )
    trabajo["en_riesgo"] = trabajo["probabilidad_desercion"] >= umbral
    trabajo["clase"] = trabajo["en_riesgo"].map(
        {True: "desertor", False: "no_desertor"}
    )

    total = len(trabajo)
    en_riesgo = int(trabajo["en_riesgo"].sum())
    agregado = {
        "total": total,
        "en_riesgo": en_riesgo,
        "no_en_riesgo": total - en_riesgo,
        "tasa_riesgo": round(en_riesgo / total, 6) if total else 0.0,
        "probabilidad_promedio": round(float(trabajo["probabilidad_desercion"].mean()), 6),
        "umbral": umbral,
        "sede_id": sede_id,
        "carrera": carrera,
        "modelo_version": modelo_version,
    }

    # Triaje: mayor riesgo primero
    ordenado = trabajo.sort_values("probabilidad_desercion", ascending=False)
    pagina = ordenado.iloc[desplazamiento : desplazamiento + limite]

    # Los motivos se sacan de la fila original del estudiante, que es donde
    # estan las variables crudas (materias aprobadas, notas, situacion de pago).
    estudiantes = []
    for row in pagina.itertuples(index=False):
        idx = int(row.indice)
        cruda = df.loc[idx].to_dict() if idx in df.index else {}
        motivos, accion = motivos_y_accion(cruda)
        estudiantes.append(
            {
                "indice": idx,
                "probabilidad_desercion": round(float(row.probabilidad_desercion), 6),
                "en_riesgo": bool(row.en_riesgo),
                "clase": row.clase,
                "carrera": int(row.carrera) if pd.notna(row.carrera) else None,
                "sede_id": row.sede_id,
                "motivos": motivos,
                "accion_sugerida": accion,
            }
        )

    return {
        "agregado": agregado,
        "estudiantes": estudiantes,
        "total_filtrado": total,
        "limite": limite,
        "desplazamiento": desplazamiento,
    }
