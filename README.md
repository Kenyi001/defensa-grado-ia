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

No hay que cambiar ni una ruta: `RAIZ`, `DIR_DATOS` y `DIR_FIGURAS` se resuelven
segun el entorno.

## Estructura

```
DefenzaGrado/
├── notebooks/
│   └── 01_desercion_estudiantil.ipynb   Analisis completo por fases CRISP-DM
├── src/
│   └── cargar_datos.py                  Descarga el dataset UCI 697 (con fallback a ZIP)
├── data/
│   └── raw/                             Dataset descargado (NO versionado)
├── outputs/
│   └── figuras/                         Figuras a 300 dpi (SI versionado -> van al Word)
├── docs/                                Documento de la defensa y notas
├── requirements.txt                     Dependencias con version fijada
└── README.md
```

`data/raw/` esta en `.gitignore` porque el dataset se regenera con un comando.
`outputs/` **si se versiona** a proposito: de ahi salen las imagenes que se
insertan en el documento Word de la defensa.

## Estado del notebook

- **Fases 1 y 2** (Comprension del Negocio y de los Datos): resueltas y
  verificadas -- carga, forma, tipos, nulos, distribucion del target y la primera
  figura.
- **Fases 3 a 6** (Preparacion, Modelado, Evaluacion, Implementacion): estan como
  comentarios `# TODO` especificos. **Es a proposito.** El codigo hay que
  escribirlo a mano: en la defensa se pregunta por que se tomo cada decision, y
  eso no se puede responder sobre codigo que uno no escribio.

Cada figura se guarda con `plt.savefig(DIR_FIGURAS / "nombre.png", dpi=300)` para
que entre con calidad de impresion en el documento.

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
