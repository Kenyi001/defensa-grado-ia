# Modelos serializados

`random_forest_v1.joblib` es el **modelo real del caso**, entrenado en la Fase 6.1
del notebook `notebooks/01_desercion_estudiantil.ipynb`. Está versionado en el
repositorio a propósito, para que el servicio de `api/` arranque con él sin tener
que entrenar durante el despliegue.

## Qué contiene

Un `dict` serializado con joblib:

| Clave | Contenido |
|---|---|
| `model` | El **pipeline completo**: codificación de categóricas + Random Forest. No solo el clasificador — en producción llegan datos crudos y hay que aplicarles las mismas transformaciones del entrenamiento. |
| `feature_names` | Las 36 variables predictoras, en el orden exacto del CSV. `api/logica/prediccion.py` valida que coincidan con `api/config.py::FEATURE_COLS` y falla al arrancar si no. |
| `version` | `v1` |
| `threshold_default` | `0.5` — el umbral por defecto. Es una decisión institucional, configurable por petición. |
| `placeholder` | `False` (el sintético de prueba lleva `True`) |
| `sklearn_version` | Versión con la que fue entrenado. Un pickle de scikit-learn **no es compatible entre versiones distintas**; `requirements.txt` fija `scikit-learn==1.9.0`. |
| `metricas_test` | Las métricas obtenidas sobre el conjunto de prueba. |

## Desempeño (conjunto de prueba, 726 registros)

| Métrica | Valor | Criterio del caso |
|---|---|---|
| Recall | 90,49% | ≥ 80% ✔ |
| Precision | 86,82% | ≥ 60% ✔ |
| F1 | 88,62% | — |
| ROC-AUC | 0,9677 | — |

Entrenado sobre 2.904 registros (80% de los 3.630 con desenlace confirmado).
Los 794 estudiantes con matrícula vigente quedan fuera del entrenamiento: no
tienen desenlace conocido, así que se usan como población de inferencia.

## Regenerarlo

Ejecutar el notebook completo. La Fase 6.1 lo sobrescribe:

```bash
jupyter nbconvert --to notebook --execute --inplace notebooks/01_desercion_estudiantil.ipynb
```

El resultado es determinista (`SEMILLA = 42`).

## Placeholder sintético

`entrenar_placeholder.py` genera un modelo de prueba con datos artificiales
(`make_classification`), **sin usar el dataset real**. Sirve para levantar la API
cuando no se dispone del modelo entrenado, y los tests lo usan como respaldo.
No aporta nada al análisis del caso.

```bash
python models/entrenar_placeholder.py
```
