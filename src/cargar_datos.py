"""
Descarga del dataset oficial del Caso #01 - Sistema de Alerta Temprana
para la Desercion Estudiantil.

Dataset: "Predicting Student Dropout and Academic Success"
Repositorio: UCI Machine Learning Repository, id = 697
URL: https://archive.ics.uci.edu/dataset/697/predicting+student+dropout+and+academic+success

Estrategia:
  1) Metodo principal: paquete `ucimlrepo` (API oficial del repositorio UCI).
  2) Fallback: descarga directa del ZIP publicado por UCI y lectura del CSV
     que viene dentro (separado por ';').

El resultado se guarda en data/raw/desercion_estudiantil.csv (separado por ',').

Uso:
    python src/cargar_datos.py
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pandas as pd

# Rutas del proyecto (independientes del directorio desde el que se ejecute)
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DIR_DATOS_RAW = RAIZ_PROYECTO / "data" / "raw"
ARCHIVO_SALIDA = DIR_DATOS_RAW / "desercion_estudiantil.csv"

UCI_DATASET_ID = 697
UCI_ZIP_URL = "https://archive.ics.uci.edu/static/public/697/predicting+student+dropout+and+academic+success.zip"

# Valores esperados segun la ficha oficial del dataset (para verificacion)
FILAS_ESPERADAS = 4424
COLUMNAS_MINIMAS = 35


def descargar_con_ucimlrepo() -> pd.DataFrame:
    """Metodo principal: usa el paquete oficial `ucimlrepo`."""
    from ucimlrepo import fetch_ucirepo

    print(f"[1/3] Descargando dataset UCI id={UCI_DATASET_ID} con ucimlrepo...")
    repo = fetch_ucirepo(id=UCI_DATASET_ID)

    X = repo.data.features
    y = repo.data.targets

    # Se reconstruye el dataframe completo (features + target) en un solo objeto
    df = pd.concat([X, y], axis=1)
    print("      OK - descarga via ucimlrepo completada.")
    return df


def descargar_con_zip_directo() -> pd.DataFrame:
    """Fallback: descarga el ZIP publicado por UCI y lee el CSV interno."""
    import urllib.request

    print(f"[1/3] Fallback: descargando ZIP directo desde {UCI_ZIP_URL} ...")
    with urllib.request.urlopen(UCI_ZIP_URL, timeout=120) as respuesta:
        contenido = respuesta.read()

    with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
        nombres_csv = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not nombres_csv:
            raise RuntimeError(f"El ZIP no contiene ningun CSV. Contenido: {zf.namelist()}")
        nombre = nombres_csv[0]
        print(f"      CSV encontrado dentro del ZIP: {nombre}")
        with zf.open(nombre) as f:
            # El CSV original de UCI usa punto y coma como separador
            df = pd.read_csv(f, sep=";")

    print("      OK - descarga via ZIP directo completada.")
    return df


def verificar(df: pd.DataFrame) -> bool:
    """Imprime la verificacion de forma del dataset. Devuelve True si coincide con lo esperado."""
    filas, columnas = df.shape
    print("\n[3/3] Verificacion del dataset descargado")
    print(f"      Filas   : {filas}   (esperado: {FILAS_ESPERADAS})")
    print(f"      Columnas: {columnas}   (esperado: >= {COLUMNAS_MINIMAS})")

    ok_filas = filas == FILAS_ESPERADAS
    ok_columnas = columnas >= COLUMNAS_MINIMAS

    if not ok_filas:
        print("      AVISO: el numero de filas NO coincide con la ficha oficial.")
    if not ok_columnas:
        print("      AVISO: el numero de columnas es menor al esperado.")

    # Distribucion del target (ultima columna: Target)
    columna_target = df.columns[-1]
    print(f"\n      Distribucion de '{columna_target}':")
    for valor, conteo in df[columna_target].value_counts().items():
        porcentaje = conteo / filas * 100
        print(f"        {valor:<12} {conteo:>5}  ({porcentaje:.1f}%)")

    print(f"\n      Nulos totales: {int(df.isnull().sum().sum())}")
    return ok_filas and ok_columnas


def main() -> int:
    DIR_DATOS_RAW.mkdir(parents=True, exist_ok=True)

    try:
        df = descargar_con_ucimlrepo()
    except Exception as error_principal:  # noqa: BLE001 - se quiere capturar cualquier fallo
        print(f"      FALLO ucimlrepo: {type(error_principal).__name__}: {error_principal}")
        try:
            df = descargar_con_zip_directo()
        except Exception as error_fallback:  # noqa: BLE001
            print(f"      FALLO tambien el ZIP directo: {type(error_fallback).__name__}: {error_fallback}")
            print("\nNo se pudo descargar el dataset. Revisa la conexion a internet.")
            return 1

    print(f"\n[2/3] Guardando CSV en: {ARCHIVO_SALIDA}")
    df.to_csv(ARCHIVO_SALIDA, index=False, encoding="utf-8")
    print(f"      OK - {ARCHIVO_SALIDA.stat().st_size / 1024:.1f} KB escritos.")

    todo_ok = verificar(df)

    print("\nListo. El notebook ya puede leer data/raw/desercion_estudiantil.csv")
    return 0 if todo_ok else 2


if __name__ == "__main__":
    sys.exit(main())
