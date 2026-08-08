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


def resumen_legible(csv_texto: str, args) -> str:
    """Cuerpo del correo: el resumen que lee una persona, no el volcado.

    Quien recibe esto es el area de Bienestar Universitario. El adjunto trae el
    detalle para trabajar en Excel; el cuerpo tiene que responder de un vistazo
    cuantos casos hay y de que tipo. Se cierra siempre con la aclaracion de que
    es una estimacion de riesgo y no un veredicto sobre el estudiante.
    """
    filas = [f for f in csv_texto.strip().splitlines()[1:] if f]
    total = len(filas)
    alto = sum(1 for f in filas if ",ALTO," in f)
    medio = sum(1 for f in filas if ",MEDIO," in f)

    acciones: dict[str, int] = {}
    for f in filas:
        partes = f.rsplit(",", 1)
        if len(partes) == 2:
            acciones[partes[1]] = acciones.get(partes[1], 0) + 1
    detalle = "\n".join(
        f"  - {a}: {n} estudiantes"
        for a, n in sorted(acciones.items(), key=lambda kv: -kv[1])
    )

    sede = args.sede or "todas las sedes"
    return f"""Reporte de alerta temprana - {sede}

Se identificaron {total} estudiantes por encima del umbral {args.umbral:.2f}:
  - Riesgo alto:  {alto}
  - Riesgo medio: {medio}

Acciones sugeridas:
{detalle}

El archivo adjunto trae la lista completa ordenada por prioridad, con el motivo
de cada caso y la accion que corresponde. Se atiende de arriba hacia abajo hasta
donde alcance la capacidad del periodo.

---
Este reporte estima RIESGO a partir del desempeno academico y la situacion
financiera del estudiante. No es un pronostico sobre ninguna persona en
particular ni una decision tomada: la intervencion la define Bienestar
Universitario. No se emplean genero, nacionalidad ni nivel educativo de los
padres como criterio de priorizacion.
"""


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
            msg.set_content(resumen_legible(cuerpo, args))
            msg.add_attachment(
                cuerpo.encode("utf-8"),
                maintype="text",
                subtype="csv",
                filename="alerta_temprana.csv",
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
