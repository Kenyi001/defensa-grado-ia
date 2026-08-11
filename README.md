[![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Kenyi001/defensa-grado-ia/blob/master/notebooks/01_desercion_estudiantil.ipynb)

# Sistema de Alerta Temprana para la Desercion Estudiantil

Clasificador **Random Forest** que predice que estudiantes universitarios estan
en riesgo de desertar durante sus primeros semestres, para poder intervenir a
tiempo.

**Contexto:** Examen de Grado - Ingenieria de Sistemas (UTEPSA).
Area: Inteligencia Artificial, Caso #01. Defensa: 13 de agosto de 2026.

**Dataset:** *Predicting Student Dropout and Academic Success* -- UCI Machine
Learning Repository, id **697**.
4.424 registros x 37 columnas (36 predictoras + `Target`).
Target original de 3 clases: `Dropout` (32,1%), `Enrolled` (17,9%),
`Graduate` (49,9%) -- se simplifica a binario (desertor / no desertor).
<https://archive.ics.uci.edu/dataset/697/predicting+student+dropout+and+academic+success>

**Metodologia:** CRISP-DM, 6 fases (Comprension del Negocio -> Comprension de los
Datos -> Preparacion -> Modelado -> Evaluacion -> Implementacion).

---

## Como levantarlo en local

Requisitos: [uv](https://docs.astral.sh/uv/) y git. **No hace falta tener Python
3.12 instalado**: `uv` lo descarga solo.

```bash
git clone https://github.com/Kenyi001/defensa-grado-ia.git DefenzaGrado
cd DefenzaGrado

# 1. Crear el entorno virtual con Python 3.12
uv venv --python 3.12 .venv

# 2. Activarlo
#    PowerShell:
.venv\Scripts\Activate.ps1
#    Git Bash:
source .venv/Scripts/activate

# 3. Instalar dependencias (versiones fijadas)
uv pip install -r requirements.txt

# 4. Descargar el dataset desde UCI (queda en data/raw/, ~500 KB)
python src/cargar_datos.py

# 5. Abrir el notebook
jupyter lab notebooks/01_desercion_estudiantil.ipynb
```

> **Por que Python 3.12 y no el del sistema:** el launcher `py` de esta maquina
> apunta a Python 3.14, demasiado nuevo para que scikit-learn / imbalanced-learn /
> xgboost tengan wheels precompiladas. Con 3.12 todo instala sin compilar nada.

Al terminar el paso 4 deberia imprimirse:

```
Filas   : 4424   (esperado: 4424)
Columnas: 37     (esperado: >= 35)
```

## Como abrirlo en Google Colab

El notebook es **auto-suficiente**: la primera celda detecta el entorno.

1. Subir `notebooks/01_desercion_estudiantil.ipynb` a Colab
   (*Archivo > Subir cuaderno*), o abrirlo desde GitHub con
   *Archivo > Abrir cuaderno > GitHub*.
2. Ejecutar la primera celda. En Colab instala las dependencias y descarga el
   dataset solo; en local no hace nada.
3. Ejecutar el resto normalmente.

Si el notebook cambio en GitHub despues de que ya lo abriste en una pestana de
Colab, esa pestana **no se actualiza sola**. Antes de re-ejecutar por un error
raro, cerrala y volve a abrirla desde el link de GitHub (o *Entorno de
ejecucion > Desconectar y eliminar entorno de ejecucion* y despues *Archivo >
Abrir cuaderno > GitHub* de nuevo) para asegurarte de estar corriendo la
version mas reciente.

**Nota sobre `partial_dependence` (Fase 5.6):** esa celda usa
`method='brute'` a proposito. El metodo `'recursion'` (el que sklearn elige
por defecto para Random Forest) puede fallar en algunas versiones de
scikit-learn con `ValueError: cannot reshape array...` para variables
binarias como `Tuition fees up to date` o `Scholarship holder` — es un bug
de esa version, no del codigo ni de numpy. `brute` evita el problema porque
llama a `predict_proba()` por la API publica en vez de recorrer la
estructura interna del arbol.

No hay que cambiar ni una ruta: `RAIZ`, `DIR_DATOS` y `DIR_FIGURAS` se resuelven
segun el entorno.

## Estructura

```
DefenzaGrado/
├── notebooks/
│   └── 01_desercion_estudiantil.ipynb   Analisis completo por fases CRISP-DM
├── api/                                 Servicio FastAPI de inferencia
├── models/                              Artefacto .joblib (placeholder o real)
├── src/
│   └── cargar_datos.py                  Descarga el dataset UCI 697 (con fallback a ZIP)
├── data/
│   └── raw/                             Dataset descargado (NO versionado)
├── outputs/
│   └── figuras/                         Figuras a 300 dpi (SI versionado -> van al Word)
├── docs/                                Documento de la defensa y notas
├── render.yaml                          Blueprint Render (Web Service)
├── requirements.txt                     Dependencias con version fijada
└── README.md
```

`data/raw/` esta en `.gitignore` porque el dataset se regenera con un comando.
`outputs/` **si se versiona** a proposito: de ahi salen las imagenes que se
insertan en el documento Word de la defensa.

## Estado del notebook

Las **6 fases de CRISP-DM estan completas** (Comprension del Negocio, Comprension
de los Datos, Preparacion, Modelado, Evaluacion, Implementacion), ejecutadas de
punta a punta con `jupyter nbconvert --execute` sin errores. Incluye ademas
secciones de profundizacion agregadas despues del modelado base: sensibilidad a
los hiperparametros, curva de aprendizaje y diagnostico de sobreajuste, un modelo
de "ventana temprana" (solo variables del 1er semestre), y una comparacion
independiente contra 5 modelos alternativos (Dummy, KNN, arbol de decision
individual, regresion logistica, XGBoost) bajo los mismos pliegues de validacion
cruzada.

Cada figura se guarda con `plt.savefig(DIR_FIGURAS / "nombre.png", dpi=300)` para
que entre con calidad de impresion en el documento.

## API de prediccion (servicio de inferencia)

La carpeta `api/` sirve un modelo ya entrenado (inferencia). **No entrena**: el
analisis CRISP-DM sigue en el notebook.

El modelo real (`models/random_forest_v1.joblib`) **esta versionado en el repo**:
lo exporta la Fase 6.1 del notebook y el servicio arranca con el directamente,
sin entrenar nada. Recall 90,49% y Precision 86,82% sobre el conjunto de prueba
(ver `models/README.md`).

```bash
uvicorn api.main:app --reload
```

Abrí `http://127.0.0.1:8000/docs` (Swagger UI, generado solo por FastAPI/Pydantic).

| Metodo | Ruta | Que hace |
|---|---|---|
| GET | `/salud` | Estado del servicio + version del modelo + metricas reales (recall/precision/ROC-AUC) |
| POST | `/predecir` | Una fila (36 variables UCI 697) → clase + probabilidad |
| POST | `/predecir/lote` | Lista de estudiantes |
| GET | `/reporte` | Agregados (conteos, tasa, probabilidad promedio); filtros `sede_id`, `umbral`, `carrera`, `capacidad`; `formato=json\|csv` |
| GET | `/reporte/correo` | El correo completo (asunto, cuerpo, adjunto) que se enviaria, sin enviarlo |
| GET/PUT | `/reporte/destino` | Lee y actualiza los destinatarios del reporte |
| POST | `/reporte/enviar` | Envia el reporte real a los destinatarios configurados (Resend o SMTP) |

`sede_id` es metadata de la peticion (multi-sede del servicio). **No** es una
feature del Random Forest: el dataset UCI no tiene columna de sede.

**Envio de reportes por correo**: el servicio puede mandar el reporte priorizado
por email (`api/logica/envio.py`). Prioriza Resend vía su API REST
(`RESEND_API_KEY`, sin SMTP) y cae a SMTP clasico (`REPORTE_SMTP_*`) si esa
variable no esta presente. El remitente visible se controla con
`REPORTE_EMAIL_FROM`. El envio es manual (boton "Enviar ahora" en la interfaz),
a proposito: no hay cron job, para evitar que un aviso automatico que nadie
revisó se vuelva ruido que se ignora.

Despliegue: blueprint en `render.yaml` (conectar el repo desde el dashboard de
Render). Tests basicos: `pytest tests/test_api.py`.

## Entorno verificado

Python **3.12.13**. Paquetes clave instalados y probados el 2026-08-05:

| Paquete | Version |
|---|---|
| pandas | 3.0.5 |
| numpy | 2.5.1 |
| scikit-learn | 1.9.0 |
| imbalanced-learn | 0.14.2 |
| matplotlib | 3.11.1 |
| seaborn | 0.13.2 |
| xgboost | 3.4.0 |
| ucimlrepo | 0.0.7 |

El notebook fue ejecutado de punta a punta con `jupyter nbconvert --execute` sin
errores.
