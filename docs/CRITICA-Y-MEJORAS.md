# Crítica y mejoras del backoffice (8 de agosto de 2026)

Análisis crítico de `api/static/index.html` — el panel que usaría Bienestar Universitario en producción, no solo en la demo del 13 — hecho leyendo el código real, no una lista genérica de buenas prácticas de UI. Cada hallazgo cita archivo y línea, y dice qué se hizo con él: **arreglado**, **documentado como decisión** o **fuera de alcance**.

Un hallazgo del análisis inicial se descartó al verificar el código: la mención de "UTEPSA" en el comentario de la línea 8 del CSS es una nota interna sobre el origen de la paleta de colores, no una inconsistencia visible — el `<h1>`, el subtítulo y el placeholder de correo dicen consistentemente "Universidad Nacional (UNAL)" en toda la pantalla.

## Hallazgos, de mayor a menor severidad

### 1. El CSV y el adjunto de correo no respetan la capacidad — ✅ arreglado

`armar_csv()` (`api/routers/reportes.py:32`) recibía la lista completa de `senalados` sin recortar. Ni el botón de descarga (`index.html:483`) ni `_componer()` (`reportes.py:108`, usado tanto por la vista previa como por el envío real) pasaban un límite de capacidad. Un operador veía "sin cupo" marcado en gris en la tabla, pero descargaba o enviaba por correo **la lista completa** de estudiantes por encima del umbral — no solo los que caben en la capacidad declarada de tutorías.

Es el hallazgo más serio porque afecta al correo que de verdad sale, no solo a lo que se ve en pantalla.

**Fix:** parámetro `capacidad` opcional en `/reporte` (formato CSV), `/reporte/correo` y `/reporte/enviar`. Recorta la lista de señalados antes de armar el CSV/adjunto. El cuerpo del correo (`resumen_correo`) sigue contando el total real de señalados — la capacidad solo afecta a qué tan larga es la lista accionable adjunta, no a la cifra de riesgo reportada.

### 2. "Enviar ahora" podía mandar a una lista de destinatarios vieja — ✅ arreglado

Si el operador editaba el campo de destinatarios y apretaba "Enviar ahora" sin apretar "Guardar" antes, el correo se enviaba a la lista guardada previamente. Había un aviso de texto dentro del `confirm()` (`index.html:505`), pero nada lo impedía estructuralmente — dependía de que alguien leyera el diálogo.

**Fix:** el frontend ahora recuerda la última lista efectivamente guardada. Si el campo de texto difiere de esa lista, "Enviar ahora" se deshabilita con una nota inline hasta que se guarde.

### 3. Sin validación de formato de correo del lado del cliente — ✅ arreglado

`guardarDestino()` (`index.html:434`) solo separaba por comas y filtraba vacíos; el error de formato recién aparecía después de la ida y vuelta al servidor (que sí valida, con el mismo patrón de `destino.py:36`).

**Fix:** el mismo patrón se valida en el navegador antes de la llamada de red, listando qué entradas están mal escritas.

### 4. El campo de capacidad absorbía valores inválidos en silencio — ✅ arreglado

`parseInt($('capacidad').value, 10) || 0` (`index.html:333`): un valor no numérico o fuera de rango se convertía en `0` sin ningún aviso, y la tabla entera se marcaba "sin cupo" sin que quedara claro por qué.

**Fix:** el valor se ajusta visiblemente al rango válido (5-500) y se muestra una nota corta cuando eso ocurre, en vez de fallar en silencio.

### 5. "Evaluar riesgo" no se deshabilitaba durante la consulta — ✅ arreglado

A diferencia de "Guardar" y "Enviar ahora", que sí siguen el patrón de deshabilitar el botón durante el pedido (`index.html:435`, `510`), "Evaluar riesgo" no lo hacía — un doble clic dispara pedidos duplicados.

**Fix:** mismo patrón aplicado a `evaluar()`.

### 6. El estado de salud del servicio se consultaba una sola vez — ✅ arreglado

`salud()` corría solo al cargar la página (`index.html:537`). Si el modelo se caía a mitad de una sesión larga, el punto verde seguía mostrando "activo" hasta que alguien recargara manualmente.

**Fix:** re-consulta periódica cada 30 segundos.

### 7. El remitente del correo reutiliza el usuario de login SMTP — ✅ arreglado

`envio.py:47` usaba `REPORTE_SMTP_USER` tanto para autenticarse como para el campo `From` visible. Con un proveedor transaccional (Brevo, Resend) el remitente visible casi siempre tiene que ser una dirección de correo verificada aparte, que puede no coincidir con el usuario de login — si no coinciden, el envío puede rechazarse.

**Fix:** nueva variable opcional `REPORTE_EMAIL_FROM`, que si no está seteada cae de vuelta a `REPORTE_SMTP_USER` como hasta ahora (compatible con cualquier configuración ya hecha).

### 8. Sin favicon ni meta description — ✅ arreglado

Detalle menor de pulido: se agregó un favicon inline (mismo círculo rojo "U" que la marca de cabecera) y una meta description.

## Descartado por alcance — el filtro de `carrera`

El backend soporta filtrar por `carrera` (`reportes.py:206`, código UCI numérico de la columna `Course`), pero la interfaz no tiene ningún control para usarlo. Construir un selector real requeriría un mapeo código → nombre de carrera que **no existe en el repositorio** (`config.py` solo tiene los códigos crudos de la Course UCI). Armar ese mapeo implicaría inventar nombres de carrera que no están documentados en ningún lado del proyecto — se deja registrado como gap conocido, sin implementar, en vez de fabricar datos.

## Poner a andar el envío real de correo

El código ya envía correo de verdad (`api/logica/envio.py`, `smtplib`) — solo falta que el servicio tenga credenciales SMTP. Se decidió usar un proveedor transaccional gratuito (Brevo o Resend) en vez de una cuenta personal de Gmail, para mejor entregabilidad. **La cuenta y las credenciales las creás vos**, no yo — nunca escribo contraseñas ni API keys en ningún campo, ni siquiera vía herramienta.

### Con Brevo (recomendado, SMTP relay clásico — combina directo con el código actual)

1. Creá una cuenta gratis en [brevo.com](https://www.brevo.com) (plan gratuito: 300 correos/día).
2. Verificá un remitente: **Settings → Senders & IP → Add a sender**, con el correo que quieras que aparezca como remitente (ej. `alertas@tudominio` o tu propio correo si no tenés dominio).
3. Anda a **SMTP & API → SMTP** y copiá: el host (`smtp-relay.brevo.com`), el puerto (`587`), tu **login SMTP** y tu **clave SMTP** (se genera ahí, no es tu contraseña de Brevo).
4. En el dashboard de Render (`defenza-grado-api` → **Environment**), agregá:
   - `REPORTE_SMTP_HOST` = `smtp-relay.brevo.com`
   - `REPORTE_SMTP_PORT` = `587`
   - `REPORTE_SMTP_USER` = tu login SMTP de Brevo
   - `REPORTE_SMTP_PASS` = tu clave SMTP de Brevo
   - `REPORTE_EMAIL_FROM` = el remitente que verificaste en el paso 2 (importante: tiene que ser ese, no cualquier dirección — si no coincide con un remitente verificado, Brevo rechaza el envío)
5. Guardá — Render redespliega solo al cambiar variables de entorno.

### Con Resend (la que finalmente se usó en producción — actualizado 9 de agosto)

Esquema distinto al de Brevo: **no es SMTP**, es la API REST de Resend directamente (`api/logica/envio.py`, función `_enviar_resend`). Solo hace falta una variable:

1. Creá una cuenta gratis en [resend.com](https://resend.com) y sacá una API key desde su panel.
2. En el dashboard de Render, agregá una sola variable:
   - `RESEND_API_KEY` = la API key de Resend
   - Opcional: `REPORTE_EMAIL_FROM` = remitente verificado propio. Sin esta variable, usa el remitente de sandbox de Resend (`onboarding@resend.dev`), que no requiere verificar un dominio.
3. Guardá — Render redespliega solo al cambiar variables de entorno.

`envio.py` prioriza `RESEND_API_KEY` si está presente; si no, cae al esquema SMTP clásico (`REPORTE_SMTP_*`) como respaldo. No hacen falta las 5 variables de Brevo si se usa este camino.

### Cómo se prueba sin exponer nada

Con las variables cargadas, `GET /reporte/destino` en la interfaz muestra `envio_disponible: true` y aparece el botón "Enviar ahora". Probá primero con tu propio correo como único destinatario antes de apuntar a `bienestar@utepsa.edu`.

## Fuera de alcance de esta pasada

- **Tabla en mobile**: hoy escala con scroll horizontal dentro de su propia caja (`#tablaBox`, `index.html:67`), correcto para tablet mas no ideal en un teléfono angosto. Un fallback de tarjetas apiladas es un cambio de diseño más grande, no un fix puntual.
- **Vínculo del Blueprint de Render** para auto-deploy: sigue sin conectarse (ver `render.yaml`), decisión ya tomada de dejarlo para después del 13 de agosto por el riesgo de tocar la gobernanza del servicio 5 días antes de la defensa.

## Actualización posterior (9 de agosto)

Después de esta pasada del 8 de agosto se hicieron dos cambios más, no cubiertos arriba: se conectó **Resend** en producción (reemplazando la sección de Resend de arriba, que describía un esquema SMTP que finalmente no se usó) y se agregó un **panel de "Confiabilidad del modelo"** (`config.py`, `main.py`, `schemas.py`, `salud.py`) que expone recall/precisión/ROC-AUC reales serializados junto con el modelo, ocultándose solo si el modelo desplegado no las trae. Ambos verificados con tests (`tests/test_api.py`: `test_enviar_con_resend`, `test_salud_expone_metricas_del_modelo_real`) y con un envío real de correo.
