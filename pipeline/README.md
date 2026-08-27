# `pipeline/` — CRISP-DM sobre RISA Data V1.0

Componente propio (hermano de `backend/` y `frontend/`), no un módulo interno del backend. Ver [`ADR-0008`](../docs/adr/0008-pipeline-crispdm-datos-reales.md) y [`ADR-0009`](../docs/adr/0009-evaluacion-etiqueta-debil.md) para las decisiones de fondo, [`SPEC-008`](../docs/spec/008-pipeline-crispdm.md)/[`SPEC-009`](../docs/spec/009-evaluacion-y-entregable-oficial.md) para el comportamiento exigido, y [`comprension_negocio.md`](comprension_negocio.md) para el mapeo completo contra [`docs/Negocio.md`](../docs/Negocio.md).

**No hay dataset sintético en ningún punto de este pipeline.** Solo se usa `pipeline/data/raw/`. Si no está presente, `build_dataset()` lanza `RisaDataNotFoundError` y el backend no arranca — no se degrada a datos inventados.

## Datos por capas (`pipeline/data/`)

Estructura exigida por el Documento Técnico Maestro V2 (sección 12: *"Separar RAW, CLEAN/PROCESSED, FEATURES, MODEL y RESULTS"*):

| Capa | Contenido | ¿Se versiona? |
| --- | --- | --- |
| `data/raw/` | RISA Data V1.0 oficial — **inmutable**, nunca se escribe aquí | Sí (es el dataset del reto) |
| `data/clean/` | Salida de `preparacion_datos.py`: vitales/labs limpios y normalizados (Parquet) | No (regenerable) |
| `data/features/` | Vector de features por paciente que consumen Anomaly/Pattern Model (Parquet) | No (regenerable) |
| `data/model/` | Modelos ganadores persistidos (`.joblib`) + metadata de la comparación | **Sí** (entregable pequeño) |
| `data/results/` | `signals.csv` + `evidence.csv` — el entregable oficial del reto | **Sí** |
| `data/cache/` | `PipelineResult` completo serializado, para arranques rápidos del backend | No (regenerable) |

## Mapeo CRISP-DM → módulos

| Fase CRISP-DM | Módulo | Qué hace |
| --- | --- | --- |
| 1. Comprensión del negocio | [`comprension_negocio.md`](comprension_negocio.md) | Preguntas de negocio + mapeo de la arquitectura de `docs/Negocio.md` a código |
| 2. Comprensión de los datos | [`comprension_datos.py`](comprension_datos.py) | Carga cruda de `data/raw/` + perfilado (cobertura, `quality_flag` por fuente) |
| 3. Preparación de los datos | [`preparacion_datos.py`](preparacion_datos.py) | Dedupe/`RETRANSMITTED`, normalización de unidad, recorte de implausibles, pivote temporal — escribe `data/clean/` |
| 4. Modelado | [`modelado.py`](modelado.py) (reglas) + [`motor_contexto.py`](motor_contexto.py) (Context Engine) | Features → calibración por percentil poblacional → motor de reglas que genera la evidencia — escribe `data/features/` |
| 5. Evaluación | [`deteccion_anomalias.py`](deteccion_anomalias.py) (Anomaly Model) + [`modelado_patrones.py`](modelado_patrones.py) (Pattern Model) + [`evaluacion.py`](evaluacion.py) (orquesta ambos) | Entrena y compara varios candidatos por familia, matriz de confusión + precisión/recall/F1/ROC-AUC, elige y persiste el mejor de cada una en `data/model/` |
| 6. Despliegue | [`fusion_evidencia.py`](fusion_evidencia.py) (Evidence Fusion) + [`motor_riesgo.py`](motor_riesgo.py) (Risk Engine) + [`motor_prioridad.py`](motor_prioridad.py) (Priority Engine) + [`explicacion.py`](explicacion.py) (Explanation) + [`despliegue.py`](despliegue.py) (orquesta todo) | Caché para el backend + `data/results/signals.csv`/`evidence.csv` |

El EDA y la comparación de modelos con gráficos (matrices de confusión, curvas ROC) están en [`notebooks/01_eda_y_comparacion_modelos.ipynb`](notebooks/01_eda_y_comparacion_modelos.ipynb) — mismo código que estos módulos, para lectura y presentación, no una implementación paralela.

## Uso

```bash
# desde la raíz del repo, con el mismo entorno de backend/requirements.txt
python -m pipeline.run_pipeline                    # corre (o carga de caché) y muestra el reporte
python -m pipeline.run_pipeline --rebuild           # ignora el caché, reprocesa RISA Data V1.0 y reentrena/compara todos los modelos (~2-4 min)
python -m pipeline.run_pipeline --patients 20       # debug rápido, sin caché, umbrales y modelos calibrados solo sobre esos 20
python -m pipeline.run_pipeline --export-submission # además escribe data/results/signals.csv y evidence.csv
```

El backend llama a `pipeline.despliegue.load_or_build()` en el arranque (`backend/app/data/loader.py`) — no hace falta correr el CLI a mano para levantar la API, solo para regenerar `data/results/`, forzar un reentrenamiento, o inspeccionar el reporte desde la terminal.

Los ganadores se persisten y se vuelven a cargar desde `anomaly_model_best.joblib` y `pattern_model_best.joblib` antes de puntuar los 1000 pacientes. `PipelineResult.model_provenance` registra modelo elegido, SHA-256 y fingerprint combinado con `source=persisted_artifact`. La caché solo se acepta cuando coinciden versión de schema, `MODEL_VERSION` y fingerprint; en caso contrario se reconstruye.

Este flujo batch alimenta `anomaly_score`, `pattern_score`, `risk_score` y `priority_level` de `/api/alerts`. Es distinto de `PRETRAINED_MODEL_URL`, que es un enriquecimiento HTTP opcional y no reemplaza los modelos del pipeline.

## Advertencia sobre la calibración por percentil y el entrenamiento

Tanto `modelado.calibrate_thresholds()` (umbrales de las reglas) como `deteccion_anomalias`/`modelado_patrones` (modelos entrenables) operan sobre **la población que efectivamente se cargó en esa corrida**. Correr con `--patients 20` calibra y entrena sobre 20 pacientes, no sobre 1000. La entrega oficial (`data/results/`, `data/model/*.joblib`) siempre se genera sin `--patients`.
