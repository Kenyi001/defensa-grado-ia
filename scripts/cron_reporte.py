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
import os
import smtplib
import sys
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage


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

    destino = os.getenv("REPORTE_EMAIL_TO")
    host = os.getenv("REPORTE_SMTP_HOST")
    if destino and host:
        msg = EmailMessage()
        msg["Subject"] = f"Reporte deserción — sede={args.sede or 'todas'} umbral={args.umbral}"
        msg["From"] = os.getenv("REPORTE_SMTP_USER", "noreply@local")
        msg["To"] = destino
        if args.formato == "csv":
            msg.set_content("Adjunto el reporte de alerta temprana.")
            msg.add_attachment(
                cuerpo.encode("utf-8"),
                maintype="text",
                subtype="csv",
                filename="reporte_desercion.csv",
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
        print(
            "(sin SMTP configurado — reporte impreso en stdout)",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
