"""Tests del contrato HTTP de la API (TestClient, sin servidor externo)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

MODELO = RAIZ / "models" / "random_forest_v1.joblib"


def _asegurar_modelo() -> None:
    """Los tests solo verifican el contrato HTTP: usan siempre el placeholder
    sintetico, nunca entrenan sobre el dataset real (eso es trabajo del
    notebook, no de esta suite)."""
    if MODELO.is_file():
        return
    from models.entrenar_placeholder import main as entrenar

    assert entrenar() == 0
    assert MODELO.is_file()


@pytest.fixture(scope="module")
def client():
    _asegurar_modelo()
    from api.main import app

    with TestClient(app) as c:
        yield c


PAYLOAD_OK = {
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
    "cu_1st_enrolled": 6,
    "cu_1st_evaluations": 6,
    "cu_1st_approved": 6,
    "cu_1st_grade": 14.0,
    "cu_1st_without_evaluations": 0,
    "cu_2nd_credited": 0,
    "cu_2nd_enrolled": 6,
    "cu_2nd_evaluations": 6,
    "cu_2nd_approved": 6,
    "cu_2nd_grade": 13.5,
    "cu_2nd_without_evaluations": 0,
    "unemployment_rate": 10.8,
    "inflation_rate": 1.4,
    "gdp": 1.74,
    "sede_id": "cochabamba",
}


def test_salud(client: TestClient) -> None:
    r = client.get("/salud")
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "ok"
    assert body["modelo_version"] == "v1"
    assert body["modelo_cargado"] is True


def test_predecir_ok(client: TestClient) -> None:
    r = client.post("/predecir", json=PAYLOAD_OK)
    assert r.status_code == 200
    body = r.json()
    assert body["clase"] in ("desertor", "no_desertor")
    assert 0.0 <= body["probabilidad_desercion"] <= 1.0
    assert body["sede_id"] == "cochabamba"


def test_predecir_fuera_de_rango(client: TestClient) -> None:
    malo = dict(PAYLOAD_OK)
    malo["admission_grade"] = 999.0  # Field(le=200)
    r = client.post("/predecir", json=malo)
    assert r.status_code == 422


def test_reporte_json(client: TestClient) -> None:
    r = client.get("/reporte", params={"sede_id": "cochabamba", "umbral": 0.5})
    assert r.status_code == 200
    body = r.json()
    assert "agregado" in body
    assert body["agregado"]["sede_id"] == "cochabamba"
    assert body["agregado"]["total"] >= 0


def test_reporte_csv_nunca_etiqueta_desertor(client: TestClient) -> None:
    """El CSV que recibe Bienestar no puede rotular a nadie como 'desertor'.

    El modelo estima riesgo; un archivo que circula por correo diciendo
    'desertor' al lado de un estudiante contradice la seccion etica del
    trabajo. Se verifica en el contrato, no solo por convencion.
    """
    r = client.get("/reporte", params={"umbral": 0.5, "formato": "csv"})
    assert r.status_code == 200
    texto = r.text
    assert "desertor" not in texto.lower()
    cabecera = texto.splitlines()[0]
    assert cabecera == (
        "prioridad,estudiante_id,carrera,sede,nivel_riesgo,"
        "probabilidad,motivos,accion_sugerida"
    )
    # Solo se exportan los señalados: cada fila supera el umbral.
    for linea in texto.splitlines()[1:]:
        if not linea.strip():
            continue
        assert linea.split(",")[4] in ("ALTO", "MEDIO", "BAJO")


def test_vista_previa_correo(client: TestClient) -> None:
    """La vista previa tiene que traer el correo completo y los destinatarios
    que se le pasan desde la interfaz, sin enviarlo."""
    r = client.get(
        "/reporte/correo",
        params={"umbral": 0.5, "destinatarios": "bienestar@u.edu, tutorias@u.edu"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["destinatarios"] == ["bienestar@u.edu", "tutorias@u.edu"]
    assert body["adjunto"]["nombre"] == "alerta_temprana.csv"
    assert "Reporte de alerta temprana" in body["cuerpo"]
    # El descargo etico viaja en el cuerpo, no es opcional.
    assert "No es un pronostico" in body["cuerpo"]


def test_vista_previa_y_csv_cuentan_lo_mismo(client: TestClient) -> None:
    """La vista previa no puede diferir del adjunto real.

    Si el numero del resumen y las filas del CSV no coinciden, la vista previa
    deja de servir para revisar antes de enviar — que es su unica razon de ser.
    """
    params = {"umbral": 0.5}
    previa = client.get("/reporte/correo", params=params).json()
    csv = client.get("/reporte", params={**params, "formato": "csv", "limite": 1000}).text
    filas = len([l for l in csv.splitlines()[1:] if l.strip()])
    assert previa["adjunto"]["filas"] == filas
