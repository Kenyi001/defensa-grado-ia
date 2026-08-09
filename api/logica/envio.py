"""Envio del reporte por correo.

Una sola implementacion, usada por el boton "Enviar ahora" de la interfaz y por
el trabajo programado. Si cada uno armara y enviara su propio mensaje, lo que
prueba el operador en pantalla no seria lo que llega el lunes a las 7.

Las credenciales salen SIEMPRE de variables de entorno del servicio. No hay
ningun camino por el que una contrasena entre por HTTP: la interfaz no las pide
y esta funcion no las recibe como argumento.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any


class SMTPNoConfigurado(RuntimeError):
    """El servicio no tiene servidor de correo. No es un error del operador."""


def hay_smtp() -> bool:
    return bool(os.getenv("REPORTE_SMTP_HOST"))


def enviar(correo: dict[str, Any], adjunto_csv: str) -> dict[str, Any]:
    """Envia el correo ya armado. `correo` es la respuesta de /reporte/correo.

    Devuelve un resumen de lo enviado — nunca las credenciales.
    """
    host = os.getenv("REPORTE_SMTP_HOST")
    if not host:
        raise SMTPNoConfigurado(
            "El servicio no tiene un servidor de correo configurado. "
            "Se configura con las variables REPORTE_SMTP_HOST, REPORTE_SMTP_USER "
            "y REPORTE_SMTP_PASS del servicio; no se piden desde esta pantalla."
        )

    destinatarios = correo.get("destinatarios") or []
    if not destinatarios:
        raise ValueError("No hay destinatarios configurados.")

    msg = EmailMessage()
    msg["Subject"] = correo["asunto"]
    # REPORTE_EMAIL_FROM es el remitente visible; REPORTE_SMTP_USER es el login
    # SMTP. Con un proveedor transaccional (Brevo, Resend) casi siempre son
    # distintos: el remitente tiene que ser una direccion verificada aparte, y
    # forzar el login como From puede hacer que el proveedor rechace el envio.
    # Sin REPORTE_EMAIL_FROM, cae al comportamiento de siempre.
    msg["From"] = os.getenv("REPORTE_EMAIL_FROM") or os.getenv("REPORTE_SMTP_USER", "noreply@local")
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(correo["cuerpo"])
    msg.add_attachment(
        adjunto_csv.encode("utf-8"),
        maintype="text",
        subtype="csv",
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

    return {
        "enviado": True,
        "destinatarios": destinatarios,
        "asunto": correo["asunto"],
        "adjunto": correo["adjunto"],
    }
