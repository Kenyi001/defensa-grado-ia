"""Envio del reporte por correo.

Una sola implementacion, usada por el boton "Enviar ahora" de la interfaz y por
el trabajo programado. Si cada uno armara y enviara su propio mensaje, lo que
prueba el operador en pantalla no seria lo que llega el lunes a las 7.

Las credenciales salen SIEMPRE de variables de entorno del servicio. No hay
ningun camino por el que una contrasena o API key entre por HTTP: la interfaz
no las pide y esta funcion no las recibe como argumento.

Dos proveedores posibles, en este orden de prioridad:
  1. Resend (RESEND_API_KEY) — API REST directa, sin SMTP.
  2. SMTP generico (REPORTE_SMTP_HOST/USER/PASS) — Brevo u otro relay.
Si ninguno esta configurado, ProveedorNoConfigurado explica exactamente que
variable falta, en vez de que el boton simplemente no aparezca sin decir por
que (la interfaz ya lo oculta con envio_disponible, pero el error tiene que
seguir siendo claro si alguien llama al endpoint directo).
"""

from __future__ import annotations

import base64
import os
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx

RESEND_URL = "https://api.resend.com/emails"
RESEND_FROM_DEFAULT = "onboarding@resend.dev"  # remitente de sandbox: no requiere dominio verificado


class ProveedorNoConfigurado(RuntimeError):
    """El servicio no tiene un proveedor de correo. No es un error del operador."""


def hay_proveedor_correo() -> bool:
    return bool(os.getenv("RESEND_API_KEY")) or bool(os.getenv("REPORTE_SMTP_HOST"))


def _remitente() -> str:
    # REPORTE_EMAIL_FROM es el remitente visible en ambos proveedores. Con
    # Resend, sin esa variable cae al sandbox (onboarding@resend.dev); con SMTP
    # cae al usuario de login, como antes.
    explicito = os.getenv("REPORTE_EMAIL_FROM")
    if explicito:
        return explicito
    return os.getenv("REPORTE_SMTP_USER") or RESEND_FROM_DEFAULT


def _enviar_resend(correo: dict[str, Any], adjunto_datos: bytes, api_key: str) -> dict[str, Any]:
    payload = {
        "from": _remitente(),
        "to": correo["destinatarios"],
        "subject": correo["asunto"],
        "text": correo["cuerpo"],
        "attachments": [
            {
                "filename": correo["adjunto"]["nombre"],
                "content": base64.b64encode(adjunto_datos).decode("ascii"),
            }
        ],
    }
    r = httpx.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if r.status_code >= 300:
        # OSError: el router ya lo traduce a 502 ("no se pudo contactar al
        # servidor de correo") — no hace falta un tipo de excepcion nuevo.
        raise OSError(f"Resend respondio {r.status_code}: {r.text[:300]}")


def _enviar_smtp(correo: dict[str, Any], adjunto_datos: bytes, host: str) -> dict[str, Any]:
    msg = EmailMessage()
    msg["Subject"] = correo["asunto"]
    msg["From"] = _remitente()
    msg["To"] = ", ".join(correo["destinatarios"])
    msg.set_content(correo["cuerpo"])
    mimetype = correo["adjunto"].get("mimetype", "text/csv")
    maintype, _, subtype = mimetype.partition("/")
    msg.add_attachment(
        adjunto_datos,
        maintype=maintype or "application",
        subtype=subtype or "octet-stream",
        filename=correo["adjunto"]["nombre"],
    )

    usuario = os.getenv("REPORTE_SMTP_USER")
    clave = os.getenv("REPORTE_SMTP_PASS")
    puerto = int(os.getenv("REPORTE_SMTP_PORT", "587"))
    with smtplib.SMTP(host, puerto, timeout=60) as smtp:
        smtp.starttls()
        if usuario and clave:
            smtp.login(usuario, clave)
        smtp.send_message(msg)


def enviar(correo: dict[str, Any], adjunto_datos: bytes | str) -> dict[str, Any]:
    """Envia el correo ya armado. `correo` es la respuesta de /reporte/correo
    (o del equivalente para el reporte ejecutivo).

    `adjunto_datos` acepta texto (el CSV de siempre, se codifica a UTF-8 aca
    mismo) o bytes ya listos (el PDF del reporte ejecutivo) -- un solo camino
    de envio para los dos tipos de adjunto, en vez de duplicar la logica de
    Resend/SMTP por cada formato.

    Devuelve un resumen de lo enviado — nunca las credenciales.
    """
    destinatarios = correo.get("destinatarios") or []
    if not destinatarios:
        raise ValueError("No hay destinatarios configurados.")

    contenido = adjunto_datos.encode("utf-8") if isinstance(adjunto_datos, str) else adjunto_datos

    resend_key = os.getenv("RESEND_API_KEY")
    smtp_host = os.getenv("REPORTE_SMTP_HOST")

    if resend_key:
        _enviar_resend(correo, contenido, resend_key)
    elif smtp_host:
        _enviar_smtp(correo, contenido, smtp_host)
    else:
        raise ProveedorNoConfigurado(
            "El servicio no tiene un proveedor de correo configurado. Se configura "
            "con RESEND_API_KEY (recomendado), o con REPORTE_SMTP_HOST, "
            "REPORTE_SMTP_USER y REPORTE_SMTP_PASS del servicio; no se piden "
            "desde esta pantalla."
        )

    return {
        "enviado": True,
        "destinatarios": destinatarios,
        "asunto": correo["asunto"],
        "adjunto": correo["adjunto"],
    }
