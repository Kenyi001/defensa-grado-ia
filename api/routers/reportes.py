"""Endpoint de reporte agregado configurable (triaje para Bienestar)."""

from __future__ import annotations

import csv
import io
from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from api.config import LIMITE_REPORTE_DEFAULT, LIMITE_REPORTE_MAX, SEDES, UMBRAL_DEFAULT
from api.logica.destino import guardar_destino, leer_destino, validar
from api.logica.envio import SMTPNoConfigurado, enviar, hay_smtp
from api.logica.reporte import armar_reporte, resumen_correo
from api.schemas import ReporteOutput

router = APIRouter(tags=["reportes"])

CABECERA_CSV = [
    "prioridad",
    "estudiante_id",
    "carrera",
    "sede",
    "nivel_riesgo",
    "probabilidad",
    "motivos",
    "accion_sugerida",
]


def armar_csv(senalados: list[dict[str, Any]], desde: int = 1) -> str:
    """El CSV que recibe Bienestar Universitario.

    Se arma para que alguien pueda ACTUAR con el, no para volcar el modelo:
      - prioridad en vez de indice suelto: el orden es el producto
      - probabilidad a 2 decimales: nadie decide con 6
      - nivel de riesgo en palabras, NUNCA la etiqueta "desertor". El modelo
        estima riesgo, no dicta un desenlace; un archivo que circula por correo
        diciendo "desertor" al lado de un nombre es un problema real, no un
        detalle de redaccion.
      - motivos y accion: sin eso no se sabe que hacer con cada caso.

    Una sola funcion para la descarga y para el adjunto del correo: lo que
    Bienestar baja de la pantalla y lo que le llega por correo tienen que ser
    el mismo archivo.
    """
    buffer = io.StringIO()
    w = csv.writer(buffer, lineterminator="\n")
    w.writerow(CABECERA_CSV)
    for i, e in enumerate(senalados, start=desde):
        p = e["probabilidad_desercion"]
        nivel = "ALTO" if p >= 0.70 else "MEDIO" if p >= 0.40 else "BAJO"
        w.writerow(
            [
                i,
                f"EST-{e['indice']:05d}",
                e["carrera"] or "",
                e["sede_id"] or "",
                nivel,
                f"{p:.2f}",
                e.get("motivos", ""),
                e.get("accion_sugerida", ""),
            ]
        )
    return buffer.getvalue()


@router.get("/reporte/destino", response_model=None)
def obtener_destino():
    """A quien se le envia el reporte, hoy.

    La interfaz lo consulta al abrirse para mostrar la configuracion REAL en
    vez de un valor de ejemplo: si la pantalla mostrara un placeholder, el
    operador no tendria forma de saber a quien le esta llegando el reporte.
    """
    actual = leer_destino()
    return {
        **actual,
        # La interfaz lo usa para no ofrecer "Enviar ahora" cuando el servicio
        # no tiene servidor de correo: un boton que no puede funcionar es peor
        # que no tenerlo.
        "envio_disponible": hay_smtp(),
        # Declarado en la respuesta y no solo en la documentacion: en el plan
        # gratuito de Render el disco es efimero y esto se pierde al redesplegar.
        "persistencia": (
            "El archivo de configuracion vive en el disco del servicio. En el plan "
            "gratuito ese disco es efimero: al redesplegar vuelve al valor de la "
            "variable de entorno REPORTE_EMAIL_TO."
        ),
    }


@router.put("/reporte/destino", response_model=None)
def actualizar_destino(destinatarios: list[str] = Body(..., embed=True)):
    """Cambia los destinatarios desde la interfaz.

    No toca credenciales: el servidor de correo se configura por variables de
    entorno del servicio y no se expone por HTTP en ningun sentido.
    """
    limpios = [d.strip() for d in destinatarios if d and d.strip()]
    errores = validar(limpios)
    if errores:
        raise HTTPException(status_code=422, detail=errores)
    return {"guardado": True, **guardar_destino(limpios)}


def _componer(estado, umbral: float, sede_id: Optional[str], destinatarios: str = ""):
    """Arma el correo y el CSV adjunto de una sola pasada.

    Lo usan la vista previa y el envio real, para que sean necesariamente lo
    mismo: si se compusieran por separado, el operador podria aprobar en
    pantalla un correo distinto del que sale.
    """
    if getattr(estado, "poblacion", None) is None:
        raise HTTPException(status_code=503, detail="Poblacion de reporte no disponible")

    data = armar_reporte(
        estado.modelo,
        estado.poblacion,
        umbral=umbral,
        sede_id=sede_id,
        limite=LIMITE_REPORTE_MAX,
        modelo_version=estado.modelo_version,
    )
    senalados = [e for e in data["estudiantes"] if e["en_riesgo"]]
    sede_txt = sede_id or "todas las sedes"
    # Sin destinatarios explicitos se usan los configurados. Asi el envio real,
    # que no pasa ninguno, manda exactamente a quien dice la pantalla.
    pedidos = [d.strip() for d in destinatarios.split(",") if d.strip()]
    correo = {
        "asunto": f"Alerta temprana de desercion - {sede_txt}",
        "destinatarios": pedidos or leer_destino()["destinatarios"],
        "cuerpo": resumen_correo(data["estudiantes"], umbral, sede_id),
        "adjunto": {"nombre": "alerta_temprana.csv", "filas": len(senalados)},
    }
    return correo, armar_csv(senalados)


@router.get("/reporte/correo", response_model=None)
def vista_previa_correo(
    request: Request,
    sede_id: Optional[str] = Query(default=None, max_length=64),
    umbral: float = Query(default=UMBRAL_DEFAULT, ge=0, le=1),
    destinatarios: str = Query(default="", max_length=300),
):
    """Devuelve el correo exacto que recibiria Bienestar, sin enviarlo.

    Existe para que el operador pueda revisar el contenido antes de enviarlo o
    de programarlo. Las credenciales SMTP viven en variables de entorno del
    servicio: **nunca se piden por la interfaz**.
    """
    correo, _ = _componer(request.app.state, umbral, sede_id, destinatarios)
    return correo


@router.post("/reporte/enviar", response_model=None)
def enviar_ahora(
    request: Request,
    sede_id: Optional[str] = Query(default=None, max_length=64),
    umbral: float = Query(default=UMBRAL_DEFAULT, ge=0, le=1),
):
    """Envia el reporte en el momento, a los destinatarios configurados.

    Existe para dos cosas: que Bienestar pueda mandar un reporte fuera de
    calendario cuando lo necesita, y que el envio se pueda demostrar sin
    esperar al lunes.

    No recibe destinatarios por parametro a proposito: manda a los que estan
    configurados, que son los que muestra la pantalla. Un endpoint que acepte
    destinatarios arbitrarios por HTTP es un relay de correo abierto.
    """
    correo, csv_texto = _componer(request.app.state, umbral, sede_id)
    try:
        return enviar(correo, csv_texto)
    except SMTPNoConfigurado as exc:
        # 503 y no 500: el servicio funciona, le falta configuracion.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        # Falla de red o de autenticacion contra el servidor de correo.
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo contactar al servidor de correo: {exc}",
        ) from exc


@router.get("/reporte", response_model=None)
def reporte(
    request: Request,
    sede_id: Optional[str] = Query(
        default=None,
        description=(
            "Filtro/etiqueta de sede (metadata de peticion; no es feature del modelo). "
            f"Valores validos: {', '.join(SEDES)}"
        ),
        max_length=64,
    ),
    umbral: float = Query(
        default=UMBRAL_DEFAULT,
        ge=0,
        le=1,
        description="Corte de probabilidad para declarar en riesgo (decision de negocio)",
    ),
    carrera: Optional[int] = Query(
        default=None,
        description="Codigo de carrera UCI (columna Course)",
    ),
    limite: int = Query(default=LIMITE_REPORTE_DEFAULT, ge=1, le=LIMITE_REPORTE_MAX),
    desplazamiento: int = Query(default=0, ge=0),
    formato: Literal["json", "csv"] = Query(default="json"),
):
    """
    Agrega predicciones sobre la poblacion cargada (Enrolled UCI o demo sintetica).

    Devuelve conteos por clase, tasa de riesgo y probabilidad promedio.
    Con `formato=csv` exporta el listado de estudiantes de la pagina.
    """
    if sede_id is not None and sede_id not in SEDES:
        raise HTTPException(
            status_code=422,
            detail=f"sede_id invalida. Use una de: {SEDES}",
        )

    estado = request.app.state
    if getattr(estado, "poblacion", None) is None:
        raise HTTPException(status_code=503, detail="Poblacion de reporte no disponible")

    data = armar_reporte(
        estado.modelo,
        estado.poblacion,
        umbral=umbral,
        sede_id=sede_id,
        carrera=carrera,
        limite=limite,
        desplazamiento=desplazamiento,
        modelo_version=estado.modelo_version,
    )

    if formato == "csv":
        # Solo los señalados. El JSON devuelve la poblacion completa porque otros
        # sistemas la necesitan, pero el CSV que recibe Bienestar es una lista de
        # trabajo: mandar tambien a los que no superan el umbral es ruido, y
        # ademas contradice el resumen ("N estudiantes por encima del umbral").
        senalados = [e for e in data["estudiantes"] if e["en_riesgo"]]
        return PlainTextResponse(
            armar_csv(senalados, desde=desplazamiento + 1),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="alerta_temprana.csv"'
            },
        )

    return ReporteOutput(**data)
