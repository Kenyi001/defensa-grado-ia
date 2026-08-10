"""Renderiza el resumen ejecutivo (ver api.routers.reportes._datos_ejecutivo)
como PDF, para descarga directa y como adjunto del correo.

Una sola funcion, alimentada por el mismo dict que ya arma la pantalla del
backoffice: si el PDF tuviera su propio texto, podria dejar de decir lo mismo
que lo que se ve en pantalla o lo que ya se aprobo en el correo.

Tipografia: "Times-Roman"/"Times-Bold"/"Times-Italic" son 3 de las 14 fuentes
estandar del formato PDF (no de reportlab) -- todo lector las resuelve sin que
el PDF tenga que embeber ningun archivo, y son la sustitucion metrica de facto
de Times New Roman en todo el ecosistema PDF. Se evita a proposito embeber el
.ttf real de Windows: es una fuente propietaria de Microsoft, no se puede
redistribuir en el repo para que Render la use al generar el PDF en el
servidor.

Paleta: mismos colores exactos que api/static/index.html (rojo institucional,
tinta, y los 3 colores semanticos de riesgo alto/medio/bajo) para que el PDF
descargado se vea como parte del mismo sistema que la pantalla, no como un
documento aparte.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Mismos valores que :root en api/static/index.html
ROJO = colors.HexColor("#C4001F")
ROJO_SUAVE = colors.HexColor("#FDECEF")
TINTA = colors.HexColor("#1F2124")
GRIS = colors.HexColor("#5A5C5E")
LINEA = colors.HexColor("#E3E4E6")
ALTO = colors.HexColor("#B00020")
MEDIO = colors.HexColor("#A96A00")
BAJO = colors.HexColor("#0F6B4F")

_ESTILOS = getSampleStyleSheet()

_TITULO = ParagraphStyle(
    "TituloEjecutivo",
    parent=_ESTILOS["Title"],
    fontName="Times-Bold",
    fontSize=17,
    leading=20,
    alignment=TA_CENTER,
    textColor=ROJO,
    spaceAfter=2,
)
_SUBTITULO = ParagraphStyle(
    "SubtituloEjecutivo",
    parent=_ESTILOS["Normal"],
    fontName="Times-Italic",
    fontSize=8.5,
    alignment=TA_CENTER,
    textColor=GRIS,
    spaceAfter=12,
)
_ENCABEZADO = ParagraphStyle(
    "EncabezadoBloque",
    parent=_ESTILOS["Heading2"],
    fontName="Times-Bold",
    fontSize=11.5,
    spaceBefore=5.5,
    spaceAfter=2.5,
    textColor=TINTA,
)
_CUERPO = ParagraphStyle(
    "CuerpoEjecutivo",
    parent=_ESTILOS["BodyText"],
    fontName="Times-Roman",
    fontSize=9,
    leading=11.3,
)
_ITEM = ParagraphStyle(
    "ItemEjecutivo",
    parent=_CUERPO,
    spaceAfter=2,
)
# Celdas de las tarjetas KPI: numero grande arriba, etiqueta chica abajo --
# mismo patron visual que .kpi en index.html (.kpi .n / .kpi .l).
_KPI_NUM = ParagraphStyle(
    "KpiNumero", parent=_CUERPO, fontName="Times-Bold", fontSize=14,
    leading=16, alignment=TA_CENTER, spaceAfter=1,
)
_KPI_LABEL = ParagraphStyle(
    "KpiEtiqueta", parent=_CUERPO, fontName="Times-Roman", fontSize=7,
    leading=8.5, alignment=TA_CENTER, textColor=GRIS,
)
_PROXIMO_PASO = ParagraphStyle(
    "ProximoPaso", parent=_CUERPO, fontName="Times-Roman", fontSize=9.3,
    leading=12, textColor=TINTA,
)


def _bloque(titulo: str, texto: str) -> list:
    return [Paragraph(titulo, _ENCABEZADO), Paragraph(texto, _CUERPO)]


def _lista(titulo: str, items: list[str]) -> list:
    return [
        Paragraph(titulo, _ENCABEZADO),
        ListFlowable(
            [ListItem(Paragraph(it, _ITEM)) for it in items],
            bulletType="bullet",
            leftIndent=14,
        ),
    ]


def _kpi_cell(numero: str, etiqueta: str, color=TINTA) -> list:
    num_style = ParagraphStyle("KpiNumeroColor", parent=_KPI_NUM, textColor=color)
    return [Paragraph(numero, num_style), Paragraph(etiqueta, _KPI_LABEL)]


def _tabla_kpis(celdas: list[list]) -> Table:
    """Fila de tarjetas KPI: cada celda ya trae [numero, etiqueta] como
    Paragraphs (ver _kpi_cell). Ancho parejo entre columnas."""
    ancho_col = (letter[0] - 3.2 * cm) / len(celdas)
    t = Table([celdas], colWidths=[ancho_col] * len(celdas))
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F7F8")),
                ("BOX", (0, 0), (-1, -1), 0.6, LINEA),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, LINEA),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def renderizar_pdf_ejecutivo(datos: dict[str, Any]) -> bytes:
    """`datos` es el dict que devuelve _datos_ejecutivo(): mismo contenido,
    mismo orden que ya usa verReporteEjecutivo() en el backoffice."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        title=datos["titulo"],
    )

    s = datos["que_tan_confiable_es"]
    sit = datos["situacion_actual"]
    h = datos["que_explica_el_abandono"]

    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")

    elementos: list = [
        Paragraph(datos["titulo"], _TITULO),
        Paragraph(f"Generado el {ahora} con los datos actuales del sistema.", _SUBTITULO),
        HRFlowable(width="100%", thickness=1.4, color=ROJO, spaceAfter=10),
    ]
    elementos += _bloque("El problema", datos["el_problema"])
    elementos += _bloque("Qué hace el sistema", datos["que_hace_el_sistema"]["resumen"])
    elementos.append(
        ListFlowable(
            [ListItem(Paragraph(b, _ITEM)) for b in datos["que_hace_el_sistema"]["bullets"]],
            bulletType="bullet",
            leftIndent=14,
        )
    )

    elementos.append(Paragraph("Qué tan confiable es", _ENCABEZADO))
    elementos.append(
        _tabla_kpis(
            [
                _kpi_cell(f"{s['recall'] * 100:.1f}%".replace(".", ","), f"Recall (meta ≥{s['criterio_recall'] * 100:.0f}%)"),
                _kpi_cell(f"{s['precision'] * 100:.1f}%".replace(".", ","), f"Precisión (meta ≥{s['criterio_precision'] * 100:.0f}%)"),
                _kpi_cell(f"{s['roc_auc']:.3f}".replace(".", ","), "AUC"),
            ]
        )
    )
    elementos.append(Spacer(1, 3))
    elementos.append(Paragraph(s["resumen"], _CUERPO))

    sede_txt = f" ({sit['sede_id']})" if sit.get("sede_id") else ""
    elementos.append(Paragraph(f"Situación actual{sede_txt}", _ENCABEZADO))
    elementos.append(
        _tabla_kpis(
            [
                _kpi_cell(str(sit["total_evaluados"]), "Estudiantes evaluados"),
                _kpi_cell(str(sit["en_riesgo_alto"]), "Riesgo alto", color=ALTO),
                _kpi_cell(str(sit["en_riesgo_medio"]), "Riesgo medio", color=MEDIO),
                _kpi_cell(str(sit["en_riesgo_bajo"]), "Riesgo bajo", color=BAJO),
            ]
        )
    )
    elementos.append(Spacer(1, 3))
    elementos.append(
        Paragraph(
            f"Con el umbral operativo actual (<b>{sit['umbral_operativo']:.2f}</b>), "
            f"<b>{sit['priorizados_con_este_umbral']}</b> quedarían priorizados este período.",
            _CUERPO,
        )
    )

    elementos += _bloque(
        "Qué explica el abandono (dataset de entrenamiento)",
        h["resumen"],
    )
    elementos += _lista("Tres medidas recomendadas", datos["tres_medidas_recomendadas"])
    elementos += _lista(
        "Consideraciones antes de implementar", datos["consideraciones_antes_de_implementar"]
    )

    elementos.append(Spacer(1, 5))
    caja_proximo_paso = Table(
        [[Paragraph(f"<b>Próximo paso.</b> {datos['proximo_paso']}", _PROXIMO_PASO)]],
        colWidths=[letter[0] - 3.2 * cm],
    )
    caja_proximo_paso.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), ROJO_SUAVE),
                ("BOX", (0, 0), (-1, -1), 0.6, ROJO),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elementos.append(caja_proximo_paso)

    doc.build(elementos)
    return buffer.getvalue()
