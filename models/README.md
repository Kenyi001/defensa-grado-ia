# Modelos serializados

Este es un modelo placeholder de prueba, entrenado con datos sintéticos.
Reemplazar por el modelo real exportado desde el notebook (Fase 5) antes de la defensa.

## Generar el placeholder (demo de la API)

```bash
python models/entrenar_placeholder.py
```

Escribe `models/random_forest_v1.joblib` (gitignored).

## Modelo real

Cuando el notebook complete el entrenamiento, exportá el artefacto con la misma
ruta y el mismo contrato de paquete (`dict` con claves `model`, `feature_names`,
`version`, `threshold_default`) para que la API lo cargue sin cambios de código.
