"""A quien se le envia el reporte: configuracion editable desde la interfaz.

Separado de config.py a proposito. config.py son parametros del servicio que
fija quien lo despliega; esto es una decision de gestion que cambia el area de
Bienestar sin pedirle nada a nadie. No es la misma clase de cosa.

QUE NO VIVE ACA: las credenciales SMTP. Van como variables de entorno del
servicio (REPORTE_SMTP_HOST/USER/PASS) y no se leen ni se escriben desde la
interfaz. Una pantalla que le pide a un operador la contrasena del servidor de
correo es un problema de seguridad, no una funcionalidad.

FRECUENCIA: es una preferencia declarada por Bienestar (ej. "Semanal, lunes
09:00"), editable y persistida igual que los destinatarios. NO dispara ningun
envio -- es una referencia para que el equipo sepa cada cuanto se comprometio
a revisar el reporte. El disparo real sigue siendo manual, via "Enviar ahora",
a proposito: automatizar un envio que nadie reviso antes es como un sistema de
alerta se convierte en ruido que se ignora.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from api.config import RAIZ_PROYECTO

# Ruta del archivo de configuracion. En Render el filesystem del plan gratuito
# es efimero: el archivo sobrevive mientras la instancia vive, pero se pierde
# en cada redeploy y vuelve al valor de REPORTE_EMAIL_TO. Es una limitacion
# real del plan, esta declarada en la respuesta del endpoint y en la interfaz,
# y se resuelve con un disco persistente o una tabla — no con mas codigo aca.
RUTA_DESTINO = Path(os.getenv("DESTINO_PATH", str(RAIZ_PROYECTO / "data" / "destino.json")))

# Deliberadamente permisiva: valida la forma, no la existencia del buzon. Un
# regex de correo "completo" rechaza direcciones validas y da falsa seguridad.
_CORREO = re.compile(r"^[^@\s,]+@[^@\s,]+\.[^@\s,]+$")

FRECUENCIA_LARGO_MAXIMO = 60


def _por_defecto() -> dict[str, Any]:
    crudo = os.getenv("REPORTE_EMAIL_TO", "")
    return {
        "destinatarios": [d.strip() for d in crudo.split(",") if d.strip()],
        "frecuencia": os.getenv("REPORTE_FRECUENCIA", "Semanal, lunes 09:00"),
    }


def leer_destino() -> dict[str, Any]:
    """Destinatarios y frecuencia vigentes. Si nunca se guardo nada, los de las variables de entorno."""
    if RUTA_DESTINO.is_file():
        try:
            guardado = json.loads(RUTA_DESTINO.read_text(encoding="utf-8"))
            base = _por_defecto()
            base.update({k: v for k, v in guardado.items() if k in ("destinatarios", "frecuencia")})
            return base
        except (json.JSONDecodeError, OSError):
            # Un archivo corrupto no puede dejar el servicio sin configuracion:
            # se cae al valor de entorno, que siempre existe.
            pass
    return _por_defecto()


def validar(destinatarios: list[str]) -> list[str]:
    """Devuelve la lista de errores. Vacia = la configuracion es valida."""
    errores: list[str] = []
    if not destinatarios:
        errores.append("Hay que indicar al menos un destinatario")
    for d in destinatarios:
        if not _CORREO.match(d):
            errores.append(f"'{d}' no tiene forma de correo electronico")
    return errores


def validar_frecuencia(frecuencia: str) -> list[str]:
    """Devuelve la lista de errores. Vacia = la frecuencia es valida.

    Es deliberadamente laxa (texto libre, no un cron real): es una preferencia
    declarada por una persona, no una expresion que un scheduler vaya a leer.
    """
    errores: list[str] = []
    if not frecuencia or not frecuencia.strip():
        errores.append("La frecuencia no puede estar vacia")
    elif len(frecuencia) > FRECUENCIA_LARGO_MAXIMO:
        errores.append(f"La frecuencia no puede superar los {FRECUENCIA_LARGO_MAXIMO} caracteres")
    return errores


def guardar_destino(destinatarios: list[str], frecuencia: str) -> dict[str, Any]:
    """Persiste destinatarios y frecuencia. Asume que ya pasaron por validar()/validar_frecuencia()."""
    RUTA_DESTINO.parent.mkdir(parents=True, exist_ok=True)
    datos = {"destinatarios": destinatarios, "frecuencia": frecuencia.strip()}
    RUTA_DESTINO.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return datos
