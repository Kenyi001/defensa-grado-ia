"""
Cron job del reporte: le pide a la API que envie el reporte, y si no hay
servidor de correo lo imprime en el log.

En Render se configura como Cron Job aparte del Web Service
(https://render.com/docs/cronjobs). Sin disco persistente: generar y entregar
en la misma corrida.

Por que este script casi no hace nada: el envio vive en la API
(POST /reporte/enviar), que es el mismo camino que usa el boton "Enviar ahora"
de la interfaz. Si el cron armara y enviara su propio mensaje, el correo
programado podria diferir del que el operador reviso en pantalla. El cron es un
disparador, no una segunda implementacion.

Uso local:
  python scripts/cron_reporte.py
  python scripts/cron_reporte.py --sede cochabamba --umbral 0.4

Los destinatarios y la frecuencia se configuran desde la interfaz. Las
credenciales SMTP son variables de entorno del Web Service.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _url(base: str, ruta: str, params: dict[str, str]) -> str:
    return f"{base.rstrip('/')}{ruta}?{urllib.parse.urlencode(params)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispara el envio del reporte")
    parser.add_argument(
        "--base-url",
        default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"),
        help="URL base del Web Service",
    )
    parser.add_argument("--sede", default=os.getenv("REPORTE_SEDE_ID"))
    parser.add_argument("--umbral", type=float, default=float(os.getenv("REPORTE_UMBRAL", "0.5")))
    args = parser.parse_args()

    params: dict[str, str] = {"umbral": str(args.umbral)}
    if args.sede:
        params["sede_id"] = args.sede

    url = _url(args.base_url, "/reporte/enviar", params)
    print(f"POST {url}", file=sys.stderr)

    peticion = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        print(
            f"Enviado a {', '.join(data['destinatarios'])} "
            f"({data['adjunto']['filas']} estudiantes)",
            file=sys.stderr,
        )
        return 0
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", "replace")
        if exc.code != 503:
            print(f"Fallo el envio ({exc.code}): {detalle}", file=sys.stderr)
            return 1
        # 503 = el servicio anda pero no tiene SMTP. No es un fallo del cron:
        # se entrega el reporte por stdout, que es lo que queda en el log del
        # Cron Job de Render y sirve igual para verificar la corrida.
        print("(sin SMTP configurado — se imprime el reporte)", file=sys.stderr)
    except urllib.error.URLError as exc:
        print(f"No se pudo contactar a la API: {exc}", file=sys.stderr)
        return 1

    respaldo = _url(args.base_url, "/reporte", {**params, "formato": "csv", "limite": "1000"})
    try:
        with urllib.request.urlopen(respaldo, timeout=120) as resp:
            csv_texto = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        print(f"Fallo al pedir el reporte: {exc}", file=sys.stderr)
        return 1

    sys.stdout.write(csv_texto)
    if not csv_texto.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
