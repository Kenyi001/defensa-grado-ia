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


def test_salud_expone_metricas_del_modelo_real(client: TestClient) -> None:
    """/salud tiene que traer las metricas de test reales, no solo "modelo_cargado".

    El modelo real (models/random_forest_v1.joblib, versionado en el repo) trae
    sus metricas de test serializadas adentro del paquete. Si el placeholder
    sintetico estuviera cargado en su lugar, estos campos vendrian en None —
    este test asume que el .joblib real esta presente, igual que el resto de
    la suite.
    """
    body = client.get("/salud").json()
    assert body["recall"] == pytest.approx(0.9049, abs=0.001)
    assert body["precision"] == pytest.approx(0.8682, abs=0.001)
    assert body["roc_auc"] == pytest.approx(0.9677, abs=0.001)
    assert body["criterio_recall"] == 0.80
    assert body["criterio_precision"] == 0.60
    # Con estos numeros, el modelo cumple ambos criterios de la Fase 1 —
    # es literalmente el argumento de la fase de Evaluacion, medido.
    assert body["recall"] >= body["criterio_recall"]
    assert body["precision"] >= body["criterio_precision"]


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


def test_reporte_ejecutivo_usa_datos_en_vivo(client: TestClient) -> None:
    """El resumen ejecutivo tiene que reflejar el modelo y la poblacion de AHORA,
    no numeros escritos a mano -- es justamente lo que lo distingue del .docx
    estatico entregado en la tesis.
    """
    r = client.get("/reporte/ejecutivo", params={"umbral": 0.5})
    assert r.status_code == 200
    body = r.json()

    # Confiabilidad: mismos numeros que /salud, no una copia separada.
    salud = client.get("/salud").json()
    assert body["que_tan_confiable_es"]["recall"] == salud["recall"]
    assert body["que_tan_confiable_es"]["precision"] == salud["precision"]
    assert body["que_tan_confiable_es"]["cumple_criterio"] is True

    # El desglose de riesgo (ALTO/MEDIO/BAJO) es una clasificacion fija de TODA
    # la poblacion -- como en el documento entregado -- asi que suma el total
    # evaluado, no el total de senalados por el umbral.
    situacion = body["situacion_actual"]
    suma = situacion["en_riesgo_alto"] + situacion["en_riesgo_medio"] + situacion["en_riesgo_bajo"]
    reporte = client.get("/reporte", params={"umbral": 0.5}).json()
    assert suma == reporte["agregado"]["total"]
    assert situacion["total_evaluados"] == reporte["agregado"]["total"]
    # Lo que SI depende del umbral es "priorizados_con_este_umbral".
    assert situacion["priorizados_con_este_umbral"] == reporte["agregado"]["en_riesgo"]

    assert "que_explica_el_abandono" in body
    assert len(body["tres_medidas_recomendadas"]) == 3


def test_reporte_ejecutivo_desglose_no_depende_del_umbral(client: TestClient) -> None:
    """ALTO/MEDIO/BAJO es una propiedad fija de cada estudiante (0.70/0.40),
    no de la decision operativa de a quien atender este periodo -- por eso
    tiene que dar lo mismo sin importar el umbral pedido.
    """
    a = client.get("/reporte/ejecutivo", params={"umbral": 0.1}).json()["situacion_actual"]
    b = client.get("/reporte/ejecutivo", params={"umbral": 0.9}).json()["situacion_actual"]
    assert (a["en_riesgo_alto"], a["en_riesgo_medio"], a["en_riesgo_bajo"]) == (
        b["en_riesgo_alto"], b["en_riesgo_medio"], b["en_riesgo_bajo"],
    )
    # Lo que si cambia con el umbral es cuantos se priorizarian este periodo.
    assert a["priorizados_con_este_umbral"] != b["priorizados_con_este_umbral"]


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


def test_destino_configurable(client: TestClient, tmp_path, monkeypatch) -> None:
    """Lo que se guarda desde la interfaz es lo que se lee despues.

    Si no persistiera, el panel seria decorativo: mostraria un destinatario y el
    correo se iria a otro.
    """
    from api.logica import destino as mod

    monkeypatch.setattr(mod, "RUTA_DESTINO", tmp_path / "destino.json")

    r = client.put(
        "/reporte/destino",
        json={
            "destinatarios": ["bienestar@utepsa.edu", "tutorias@utepsa.edu"],
            "frecuencia": "Semanal, lunes 09:00",
        },
    )
    assert r.status_code == 200

    leido = client.get("/reporte/destino").json()
    assert leido["destinatarios"] == ["bienestar@utepsa.edu", "tutorias@utepsa.edu"]
    assert leido["frecuencia"] == "Semanal, lunes 09:00"
    # La frecuencia es una referencia declarada, no un envio programado: no
    # existe ningun proceso en el servicio que la lea para enviar solo.
    assert "no dispara" in leido["frecuencia_nota"].lower()

    # Sin destinatarios en la query, la vista previa usa los configurados —
    # que es lo mismo que hace el envio real.
    previa = client.get("/reporte/correo", params={"umbral": 0.5}).json()
    assert previa["destinatarios"] == ["bienestar@utepsa.edu", "tutorias@utepsa.edu"]


def test_destino_rechaza_datos_invalidos(client: TestClient, tmp_path, monkeypatch) -> None:
    """Un correo mal escrito tiene que fallar al guardar, con el error a la vista.

    Si se aceptara, el fallo aparecería recién al apretar "Enviar ahora" y sin
    decir por qué.
    """
    from api.logica import destino as mod

    monkeypatch.setattr(mod, "RUTA_DESTINO", tmp_path / "destino.json")

    r = client.put(
        "/reporte/destino",
        json={"destinatarios": ["no-es-un-correo"], "frecuencia": "Semanal"},
    )
    assert r.status_code == 422
    assert "correo" in " ".join(r.json()["detail"]).lower()

    # Uno valido y uno invalido: tampoco pasa, y el error nombra al culpable.
    r = client.put(
        "/reporte/destino",
        json={"destinatarios": ["a@b.com", "roto@"], "frecuencia": "Semanal"},
    )
    assert r.status_code == 422
    assert "roto@" in " ".join(r.json()["detail"])

    r = client.put("/reporte/destino", json={"destinatarios": [], "frecuencia": "Semanal"})
    assert r.status_code == 422


def test_destino_rechaza_frecuencia_invalida(client: TestClient, tmp_path, monkeypatch) -> None:
    """Una frecuencia vacia o demasiado larga tiene que fallar al guardar.

    Es texto libre, no un cron real -- pero vacia no dice nada, y sin limite de
    largo alguien puede pegar un parrafo entero en un campo pensado para "cada
    cuanto".
    """
    from api.logica import destino as mod

    monkeypatch.setattr(mod, "RUTA_DESTINO", tmp_path / "destino.json")

    r = client.put(
        "/reporte/destino",
        json={"destinatarios": ["bienestar@utepsa.edu"], "frecuencia": ""},
    )
    assert r.status_code == 422
    assert "frecuencia" in " ".join(r.json()["detail"]).lower()

    r = client.put(
        "/reporte/destino",
        json={"destinatarios": ["bienestar@utepsa.edu"], "frecuencia": "x" * 61},
    )
    assert r.status_code == 422


def test_enviar_sin_proveedor_avisa_en_vez_de_romper(client: TestClient, monkeypatch) -> None:
    """Sin ningun proveedor de correo el envio responde 503, no 500.

    La diferencia importa: 500 dice "el sistema esta roto", 503 dice "falta
    configurar el correo". La interfaz usa eso para ocultar el boton en vez de
    ofrecer algo que no puede funcionar.
    """
    monkeypatch.delenv("REPORTE_SMTP_HOST", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    r = client.post("/reporte/enviar", params={"umbral": 0.5})
    assert r.status_code == 503
    assert "proveedor de correo" in r.json()["detail"]

    # Y la interfaz se entera por /reporte/destino.
    assert client.get("/reporte/destino").json()["envio_disponible"] is False


def test_enviar_usa_los_destinatarios_configurados(client: TestClient, tmp_path, monkeypatch) -> None:
    """El envio no acepta destinatarios por parametro: manda a los guardados.

    Un endpoint que acepta destinatarios arbitrarios por HTTP es un relay de
    correo abierto. Se verifica en el contrato para que no se relaje despues.
    """
    from api.logica import destino as mod_destino
    from api.logica import envio as mod_envio

    monkeypatch.setattr(mod_destino, "RUTA_DESTINO", tmp_path / "destino.json")
    client.put(
        "/reporte/destino",
        json={"destinatarios": ["bienestar@utepsa.edu"], "frecuencia": "Semanal, lunes 09:00"},
    )

    capturado: dict = {}

    monkeypatch.setenv("REPORTE_SMTP_HOST", "smtp.ejemplo.invalido")
    monkeypatch.setattr(
        mod_envio,
        "enviar",
        lambda correo, csv: capturado.update(correo=correo, csv=csv)
        or {"enviado": True, **{k: correo[k] for k in ("destinatarios", "asunto", "adjunto")}},
    )
    # El router importo `enviar` por nombre: hay que sustituirlo ahi tambien.
    from api.routers import reportes as mod_router

    monkeypatch.setattr(mod_router, "enviar", mod_envio.enviar)

    r = client.post("/reporte/enviar", params={"umbral": 0.5})
    assert r.status_code == 200
    assert r.json()["destinatarios"] == ["bienestar@utepsa.edu"]
    # El adjunto es el MISMO CSV que se descarga de la pantalla.
    assert capturado["csv"].splitlines()[0] == (
        "prioridad,estudiante_id,carrera,sede,nivel_riesgo,probabilidad,motivos,accion_sugerida"
    )


def test_enviar_con_resend(client: TestClient, tmp_path, monkeypatch) -> None:
    """Con RESEND_API_KEY seteada, el envio usa la API REST de Resend, no SMTP.

    Verifica la forma exacta del pedido: URL, header de autorizacion, y que el
    adjunto viaja en base64 — si alguno de estos cambia sin querer, Resend
    rechaza el correo en silencio o lo manda sin el CSV.
    """
    import base64

    from api.logica import destino as mod_destino
    from api.logica import envio as mod_envio

    monkeypatch.setattr(mod_destino, "RUTA_DESTINO", tmp_path / "destino.json")
    client.put(
        "/reporte/destino",
        json={"destinatarios": ["bienestar@utepsa.edu"], "frecuencia": "Semanal, lunes 09:00"},
    )

    monkeypatch.delenv("REPORTE_SMTP_HOST", raising=False)
    monkeypatch.setenv("RESEND_API_KEY", "re_test_falsa")
    monkeypatch.setenv("REPORTE_EMAIL_FROM", "alertas@utepsa.edu")

    capturado: dict = {}

    class RespuestaFalsa:
        status_code = 200
        text = "ok"

    def post_falso(url, headers=None, json=None, timeout=None):
        capturado["url"] = url
        capturado["headers"] = headers
        capturado["payload"] = json
        return RespuestaFalsa()

    monkeypatch.setattr(mod_envio.httpx, "post", post_falso)

    r = client.post("/reporte/enviar", params={"umbral": 0.5})
    assert r.status_code == 200
    assert r.json()["destinatarios"] == ["bienestar@utepsa.edu"]

    assert capturado["url"] == "https://api.resend.com/emails"
    assert capturado["headers"]["Authorization"] == "Bearer re_test_falsa"
    payload = capturado["payload"]
    assert payload["from"] == "alertas@utepsa.edu"
    assert payload["to"] == ["bienestar@utepsa.edu"]
    # El adjunto viaja en base64: decodificarlo tiene que devolver el mismo CSV.
    adjunto_b64 = payload["attachments"][0]["content"]
    csv_decodificado = base64.b64decode(adjunto_b64).decode("utf-8")
    assert csv_decodificado.splitlines()[0] == (
        "prioridad,estudiante_id,carrera,sede,nivel_riesgo,probabilidad,motivos,accion_sugerida"
    )


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


def test_capacidad_recorta_el_csv(client: TestClient) -> None:
    """La capacidad tiene que recortar la descarga, no solo la vista en pantalla.

    Sin esto, un operador ve "sin cupo" marcado en gris en la tabla pero se
    lleva la lista completa de señalados — la brecha mas seria del analisis
    critico del 8 de agosto (ver docs/CRITICA-Y-MEJORAS.md).
    """
    params = {"umbral": 0.5, "formato": "csv", "limite": 1000}
    sin_capacidad = client.get("/reporte", params=params).text
    total = len([l for l in sin_capacidad.splitlines()[1:] if l.strip()])
    assert total > 5, "el umbral 0.5 deberia señalar mas de 5 estudiantes en la poblacion demo"

    con_capacidad = client.get("/reporte", params={**params, "capacidad": 5}).text
    filas = [l for l in con_capacidad.splitlines()[1:] if l.strip()]
    assert len(filas) == 5
    # La prioridad tiene que seguir siendo 1..5: se recorta la cola, no se
    # cambia el orden de quien va primero.
    assert [l.split(",")[0] for l in filas] == ["1", "2", "3", "4", "5"]


def test_capacidad_recorta_el_adjunto_pero_no_el_resumen(client: TestClient) -> None:
    """El correo tiene que seguir informando el riesgo real, aunque el adjunto
    accionable se recorte a la capacidad del periodo — son dos cosas distintas:
    cuantos estan en riesgo, y a cuantos se llega a atender.
    """
    params = {"umbral": 0.5}
    sin_capacidad = client.get("/reporte/correo", params=params).json()
    total_real = sin_capacidad["adjunto"]["filas"]
    assert total_real > 5

    con_capacidad = client.get("/reporte/correo", params={**params, "capacidad": 5}).json()
    assert con_capacidad["adjunto"]["filas"] == 5
    # El cuerpo sigue contando el total real de señalados, no los 5 del adjunto.
    assert f"Se identificaron {total_real} estudiantes" in con_capacidad["cuerpo"]
    assert con_capacidad["cuerpo"] == sin_capacidad["cuerpo"]
