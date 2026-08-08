"""Endpoint de reporte agregado configurable (triaje para Bienestar)."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from api.config import LIMITE_REPORTE_DEFAULT, LIMITE_REPORTE_MAX, SEDES, UMBRAL_DEFAULT
from api.logica.destino import (
    FRECUENCIAS,
    guardar_destino,
    leer_destino,
    validar,
)
from api.logica.reporte import armar_reporte, resumen_correo
from api.schemas import ReporteOutput

router = APIRouter(tags=["reportes"])


@router.get("/reporte/destino", response_model=None)
def obtener_destino():
    """A quien y cada cuanto se envia el reporte, hoy.

    La interfaz lo consulta al abrirse para mostrar la configuracion REAL en
    vez de un valor de ejemplo: si la pantalla mostrara un placeholder, el
    operador no tendria forma de saber a quien le esta llegando el reporte.
    """
    actual = leer_destino()
    return {
        **actual,
        "frecuencias_disponibles": FRECUENCIAS,
        # Declarado en la respuesta y no solo en la documentacion: en el plan
        # gratuito de Render el disco es efimero y esto se pierde al redesplegar.
        "persistencia": (
            "El archivo de configuracion vive en el disco del servicio. En el plan "
            "gratuito ese disco es efimero: al redesplegar vuelve al valor de la "
            "variable de entorno REPORTE_EMAIL_TO."
        ),
    }


@router.put("/reporte/destino", response_model=None)
def actualizar_destino(
    destinatarios: list[str] = Body(..., embed=True),
    frecuencia: str = Body(..., embed=True),
):
    """Cambia los destinatarios y la frecuencia desde la interfaz.

    No toca credenciales: el servidor de correo se configura por variables de
    entorno del servicio y no se expone por HTTP en ningun sentido.
    """
    limpios = [d.strip() for d in destinatarios if d and d.strip()]
    errores = validar(limpios, frecuencia)
    if errores:
        raise HTTPException(status_code=422, detail=errores)
    return {"guardado": True, **guardar_destino(limpios, frecuencia)}


@router.get("/reporte/correo", response_model=None)
def vista_previa_correo(
    request: Request,
    sede_id: Optional[str] = Query(default=None, max_length=64),
    umbral: float = Query(default=UMBRAL_DEFAULT, ge=0, le=1),
    destinatarios: str = Query(default="", max_length=300),
):
    """Devuelve el correo exacto que recibiria Bienestar, sin enviarlo.

    Existe para que el operador pueda revisar el contenido antes de programar
    el envio. El envio real lo hace el cron job, con las credenciales SMTP en
    variables de entorno del servicio: **nunca se piden por la interfaz**.
    """
    estado = request.app.state
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
    # Sin destinatarios explicitos se usan los configurados. Asi el cron, que no
    # pasa ninguno, envia exactamente a quien dice la pantalla.
    pedidos = [d.strip() for d in destinatarios.split(",") if d.strip()]
    return {
        "asunto": f"Alerta temprana de desercion - {sede_txt}",
        "destinatarios": pedidos or leer_destino()["destinatarios"],
        "cuerpo": resumen_correo(data["estudiantes"], umbral, sede_id),
        "adjunto": {
            "nombre": "alerta_temprana.csv",
            "filas": len(senalados),
        },
    }


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
        # Este CSV es el que recibe Bienestar Universitario, asi que se arma
        # para que alguien pueda ACTUAR con el, no para volcar el modelo:
        #   - prioridad en vez de indice suelto: el orden es el producto
        #   - probabilidad a 2 decimales: nadie decide con 6
        #   - nivel de riesgo en palabras, NUNCA la etiqueta "desertor". El
        #     modelo estima riesgo, no dicta un desenlace; un archivo que
        #     circula por correo diciendo "desertor" al lado de un nombre es
        #     un problema real, no un detalle de redaccion.
        #   - motivos y accion: sin eso no se sabe que hacer con cada caso.
        import csv
        import io

        buffer = io.StringIO()
        w = csv.writer(buffer, lineterminator="\n")
        w.writerow(
            [
                "prioridad",
                "estudiante_id",
                "carrera",
                "sede",
                "nivel_riesgo",
                "probabilidad",
                "motivos",
                "accion_sugerida",
            ]
        )
        # Solo los señalados. El JSON devuelve la poblacion completa porque otros
        # sistemas la necesitan, pero el CSV que recibe Bienestar es una lista de
        # trabajo: mandar tambien a los que no superan el umbral es ruido, y
        # ademas contradice el resumen ("N estudiantes por encima del umbral").
        senalados = [e for e in data["estudiantes"] if e["en_riesgo"]]
        for i, e in enumerate(senalados, start=desplazamiento + 1):
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
        return PlainTextResponse(
            buffer.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="alerta_temprana.csv"'
            },
        )

    return ReporteOutput(**data)
