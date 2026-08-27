# ADR-0008 — `pipeline/` como componente propio: CRISP-DM sobre RISA Data V1.0 real

- Estado: `aceptada`
- Fecha: 2026-08-27
- Decisores: equipo
- Relaciona: `ADR-0002`, `ADR-0003`, `ADR-0007`, `SPEC-008`, `SPEC-009`

## Contexto

Hasta esta versión, `backend/app/data/sample.py` generaba 8 pacientes sintéticos a mano (48 h, patrones diseñados para demostrar cada caso) y el backend corría contra eso. Es razonable como punto de partida (`SUP-01` en `definicion.md` contemplaba exactamente este fallback), pero una vez que `docs/Participantes Salud/01_RISA_DATA_V1_0` está disponible en el repo, seguir demostrando sobre datos inventados deja de ser defendible frente al checklist oficial ("nuestra solución procesa realmente RISA Data V1.0") y frente al criterio de "Validación técnica con caso oficial no preparado" (5 pts).

RISA Data V1.0 es grande y real: `vital_signs.csv` (154 MB, 1 622 969 filas), `wearable_observations.csv` (87 MB, 895 551 filas), más laboratorio, contexto, dispositivos y condiciones — 1000 pacientes, formato largo (`variable_code`/`value`), con la regla temporal `sample/timestamp` (cuándo ocurrió) vs. `result/sync_datetime` (cuándo estuvo disponible) que la guía oficial marca como error eliminatorio si se ignora.

Procesar esto no es "cargar un CSV": hace falta normalizar unidades (`units_catalog.csv`), tratar `quality_flag` (`CHECK`, `RETRANSMITTED`, `UNIT_VARIANT`, `LOW_SIGNAL`), alinear temporalmente fuentes con frecuencias distintas, y —descubierto al calibrar contra los datos reales— los umbrales clínicos fijos que funcionaban sobre el sample a mano (p. ej. `hr_slope > 0.35`/hora) casi nunca se cumplen sobre series reales con ruido genuino (percentil 99 real ≈ 0.016/hora): con los umbrales del sample, **0 de 1000 pacientes** producía nada distinto de `STABLE`.

## Decisión

Crear `pipeline/` como un componente de primer nivel (hermano de `backend/` y `frontend/`, no un módulo interno del backend), organizado explícitamente por fase CRISP-DM:

```
pipeline/
├── comprension_negocio.md    # Fase 1 — preguntas de negocio que el pipeline debe responder
├── comprension_datos.py       # Fase 2 — carga cruda + perfilado (completitud, cobertura, calidad declarada)
├── preparacion_datos.py        # Fase 3 — dedupe/RETRANSMITTED, normalización de unidad, recorte de implausibles, pivote ancho
├── modelado.py                  # Fase 4 — features, calibración de umbrales por percentil poblacional, motor de reglas
├── evaluacion.py                 # Fase 5 — entrena y compara 5 modelos (train/val/test), matriz de confusión, elige y persiste el mejor
├── despliegue.py                  # Fase 6 — orquesta 2-5, cachea a pickle, exporta results/signals.csv + evidence.csv
└── run_pipeline.py                 # CLI: python -m pipeline.run_pipeline [--rebuild] [--export-submission]
```

No existe ningún dataset sintético dentro de `pipeline/`: si `pipeline/data/raw/` no está presente, `build_dataset()` lanza `RisaDataNotFoundError` (`pipeline/config.py`) y el backend no arranca. Es una decisión explícita, no un olvido — la guía oficial exige procesar RISA Data V1.0 real, y un fallback inventado (aunque estuviera etiquetado como tal) diluye esa exigencia.

**Adenda (2026-08-27):** el dataset se movió de `docs/Participantes Salud/01_RISA_DATA_V1_0` a `pipeline/data/raw/`, siguiendo la estructura por capas RAW/CLEAN/FEATURES/MODEL/RESULTS que fija el Documento Técnico Maestro V2 (sección 12) — "separar RAW, CLEAN/PROCESSED, FEATURES, MODEL y RESULTS". `docs/Participantes Salud/` conserva solo el material de referencia del reto (guías, kit de entrega); los datos viven junto al código que los procesa.

El backend **no procesa datos**: `backend/app/data/loader.py` importa `pipeline.despliegue` y expone `Dataset = PipelineResult` (mismo contrato que antes — `.patients`, `.vitals_for(pid)`, `.labs_for(pid)`, `.origin` — así que `charts.py`, `llm/tools.py` y el resto del backend no cambiaron su forma de consumir datos). El pipeline es quien decide qué es una señal; el backend solo la sirve por REST y el frontend solo la consulta.

Dos correcciones de fondo sobre `ADR-0002`, ambas documentadas aquí en vez de reabrirlo:

1. **Umbrales calibrados, no constantes clínicas.** `modelado.calibrate_thresholds()` calcula, en cada corrida, el percentil 90 (o 10 para caídas) de cada pendiente sobre la población efectivamente analizada, y las reglas comparan contra eso. Esto es literalmente lo que pide la guía oficial ("no queremos un sistema de umbrales... variación esperada → comportamiento atípico → señal relevante") y es la razón de que, sobre los 1000 pacientes reales, la distribución final sea `DESCARTADO 413 · BAJO 554 · MEDIO 27 · ALTO 5 · CRITICO 1` en vez de "todos STABLE" o "todos CRITICAL".
2. **Ventana de análisis explícita.** Cada paciente se evalúa sobre las últimas `WINDOW_HOURS = 120` horas de datos disponibles (no todo el episodio de ~9 días): es una ventana móvil ancianda al último dato, no una foto fija de todo el historial, más cercana al espíritu de "anticipar en un momento útil" (sección 4.2 de la guía oficial).

## Alternativas consideradas

| Opción | Por qué no (o por qué sí) |
| --- | --- |
| Meter la carga/limpieza dentro de `backend/app/data/` | Mezcla dos responsabilidades (servir por HTTP vs. modelar) y hace que la metodología CRISP-DM que pide el reto quede implícita en vez de ser una carpeta que se puede señalar en la demo |
| Notebook único de análisis + export manual a CSV que el backend lee | Descartado: no reproducible con un comando, no expone `/api/pipeline/report`, y "reproducibilidad" es un requisito explícito de la guía |
| **`pipeline/` como paquete propio, importado por el backend, con caché en pickle** | Elegida: separación de responsabilidades clara, reprocesa las ~250 MB de CSV una sola vez (≈70 s) y sirve desde caché (≈5 s) en arranques siguientes de `uvicorn` |

## Consecuencias

- Positivas: el mismo objeto (`PipelineResult`) alimenta la API REST, el chat/RAG, y la exportación oficial `results/signals.csv`/`results/evidence.csv` — una sola fuente de verdad. `RisaDataNotFoundError` cumple RF-08 (degradar con mensaje claro) fallando de forma visible en vez de inventar datos.
- Negativas / deuda: la calibración por percentil depende de la población que efectivamente se cargue (`--patients N` para debug da umbrales distintos a la corrida completa; documentado en `pipeline/README.md`). El caché en `pipeline/data/cache/dataset.pkl` no se invalida solo — hace falta `--rebuild` si cambian los datos o la lógica de modelado. El backend no puede levantarse sin el dataset oficial presente en el repositorio (es una decisión, no un descuido — ver `Contexto`).
- Impacto en RF/RNF/RN: reemplaza el mecanismo de `SUP-01` (RISA Data V1.0 real es el único camino, no un fallback), sostiene RF-02 (tratamiento de calidad visible en `quality_report`) y RNF-04 (evidencia con percentil poblacional citado en cada `EvidenceItem`).

## Reversibilidad

Alta: el contrato `Dataset`/`PipelineResult` es el mismo que exponía `app/data/loader.py` antes de este cambio, así que volver a un generador sintético (o apuntar a otra fuente) es cuestión de reemplazar `pipeline/despliegue.build_dataset()` sin tocar backend ni frontend.
