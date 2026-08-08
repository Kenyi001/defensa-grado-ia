"""
Cron job de reporte: llama a GET /reporte y entrega el resultado.

En Render se configura como Cron Job aparte del Web Service
(https://render.com/docs/cronjobs). Sin disco persistente: generar y
entregar en la misma corrida.

Uso local:
  python scripts/cron_reporte.py
  python scripts/cron_reporte.py --sede cochabamba --umbral 0.4 --formato csv

Email (opcional): setear REPORTE_SMTP_HOST, REPORTE_SMTP_USER,
REPORTE_SMTP_PASS, REPORTE_EMAIL_TO. Si no hay SMTP, escribe a stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import sys
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage


def correo_a_enviar(base_url: str, args) -> dict:
    """Asunto, destinatarios y cuerpo del correo, pedidos a la API.

    Se consulta /reporte/correo en vez de recalcularlo aca a proposito: es el
    mismo texto que muestra la vista previa de la interfaz. Si el cron armara
    su propia version, la vista previa podria diferir del correo real y dejaria
    de servir para revisar antes de enviar.

    Tampoco se pasan destinatarios: al no mandarlos, la API responde con los que
    quedaron configurados desde la interfaz. Asi el correo llega a quien dice la
    pantalla, no a lo que diga una variable de entorno que nadie recuerda haber
    puesto.
    """
    params = {"umbral": str(args.umbral)}
    if args.sede:
        params["sede_id"] = args.sede
    url = f"{base_url.rstrip('/')}/reporte/correo?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispara GET /reporte y entrega el resultado")
    parser.add_argument(
        "--base-url",
        default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"),
        help="URL base del Web Service",
    )
    parser.add_argument("--sede", default=os.getenv("REPORTE_SEDE_ID"))
    parser.add_argument("--umbral", type=float, default=float(os.getenv("REPORTE_UMBRAL", "0.5")))
    parser.add_argument("--carrera", type=int, default=None)
    parser.add_argument("--formato", choices=("json", "csv"), default="csv")
    parser.add_argument("--limite", type=int, default=500)
    args = parser.parse_args()

    params: dict[str, str] = {
        "umbral": str(args.umbral),
        "formato": args.formato,
        "limite": str(args.limite),
    }
    if args.sede:
        params["sede_id"] = args.sede
    if args.carrera is not None:
        params["carrera"] = str(args.carrera)

    url = f"{args.base_url.rstrip('/')}/reporte?{urllib.parse.urlencode(params)}"
    print(f"GET {url}", file=sys.stderr)

    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            cuerpo = resp.read().decode("utf-8")
            content_type = resp.headers.get_content_type()
    except urllib.error.URLError as exc:
        print(f"Fallo al llamar /reporte: {exc}", file=sys.stderr)
        return 1

    # El destino sale de la configuracion que edita la interfaz; la variable de
    # entorno queda solo como valor inicial (la API ya cae a ella si no se
    # guardo nada). El host SMTP si es del servicio y no se toca desde la web.
    host = os.getenv("REPORTE_SMTP_HOST")
    correo = correo_a_enviar(args.base_url, args) if host else None
    destino = ", ".join(correo["destinatarios"]) if correo else ""

    if destino and host:
        msg = EmailMessage()
        msg["Subject"] = correo["asunto"]
        msg["From"] = os.getenv("REPORTE_SMTP_USER", "noreply@local")
        msg["To"] = destino
        if args.formato == "csv":
            msg.set_content(correo["cuerpo"])
            msg.add_attachment(
                cuerpo.encode("utf-8"),
                maintype="text",
                subtype="csv",
                filename=correo["adjunto"]["nombre"],
            )
        else:
            msg.set_content(cuerpo)
            msg.set_type(content_type)

        user = os.getenv("REPORTE_SMTP_USER")
        password = os.getenv("REPORTE_SMTP_PASS")
        port = int(os.getenv("REPORTE_SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=60) as smtp:
            smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        print(f"Enviado a {destino}", file=sys.stderr)
    else:
        # Sin SMTP: entregar por stdout (lo que ve el log del Cron Job en Render)
        sys.stdout.write(cuerpo)
        if not cuerpo.endswith("\n"):
            sys.stdout.write("\n")
        motivo = (
            "sin SMTP configurado"
            if not host
            else "no hay destinatarios configurados — cargalos en la interfaz"
        )
        print(f"({motivo} — reporte impreso en stdout)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
