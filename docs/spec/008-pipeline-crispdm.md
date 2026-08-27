# SPEC-008 — Pipeline CRISP-DM: integración, calidad y features sobre RISA Data V1.0

- Estado: `implementado`
- Área: 1 Salud
- Relaciona: RF-01, RF-02, RF-03, RNF-03, RNF-06, ADR-0008
- Autor: equipo
- Fecha: 2026-08-27

## Problema

Antes de detectar nada hay que poder responder, de forma auditable: ¿qué llegó?, ¿con qué calidad?, ¿cómo se integra sin mezclar `timestamp` (cuándo ocurrió) con `sync_datetime`/`result_datetime` (cuándo estuvo disponible)? `pipeline/` (fases 2 y 3 de CRISP-DM) es la respuesta a esas preguntas, separada de la fase de modelado.

## Actor y disparador

- **Actor:** `backend/app/data/loader.py` (vía `pipeline.despliegue.load_or_build`), y cualquiera que corra `python -m pipeline.run_pipeline` desde la línea de comandos.
- **Disparador:** arranque del backend, o ejecución manual del CLI para regenerar `pipeline/data/results/`.

## Comportamiento esperado

1. **Comprensión de datos** (`comprension_datos.py`): carga `patients`, `vital_signs`, `laboratory_results`, `wearable_observations`, `device_observations`, `patient_context`, `conditions` desde `pipeline/data/raw/`, y perfila cobertura de pacientes + distribución de `quality_flag` por fuente (`profile_sources`).
2. **Preparación de datos** (`preparacion_datos.py`), escribe `pipeline/data/clean/`:
   - Deduplica `(patient_id, variable_code, timestamp)` quedándose con la última lectura (una `RETRANSMITTED` reemplaza al original).
   - Normaliza unidad a la canónica del `units_catalog.csv` (p. ej. `degF → degC`) para toda variable numérica.
   - Marca (no borra) valores fuera del rango de plausibilidad del `variable_catalog.csv`; los recorta (winsoriza) solo para el cálculo de features, conservando el valor crudo en `value_raw`.
   - Pivota `vital_signs` a formato ancho por `(patient_id, timestamp)` sin `ffill` — una celda vacía es una variable que RISA no midió ahí, no un dato a inventar.
   - Ancla `laboratory_results` en `result_datetime` (disponibilidad), nunca en `sample_datetime` (ocurrencia) — cualquier consumidor de `labs_for()` respeta la regla temporal por construcción.
3. El resultado se enriquece con **Context Engine** (`motor_contexto.py`: `ACTIVITY_LEVEL` del wearable por cercanía ±2h, y `SLEEP_STATE` de `patient_context.csv` por pertenencia al intervalo) y **calidad técnica** (`SIGNAL_QUALITY_INDEX` del dispositivo, tolerancia 6 h) por `(patient_id, timestamp)`.
4. Cada paciente se recorta a una ventana móvil de `WINDOW_HOURS = 120` horas ancianda a su último dato disponible antes de pasar a la fase de modelado (`SPEC-009` / `ADR-0008`).
5. Todo el reporte de calidad (duplicados removidos, implausibles recortados, conteo de `quality_flag`) queda expuesto en `GET /api/pipeline/report` para trazabilidad ante el jurado.

## Entradas

- CSV oficiales de RISA Data V1.0 (`01_master`, `02_clinical`, `03_monitoring`, `04_context`, `05_metadata`).
- `variable_catalog.csv` (rangos de plausibilidad) y `units_catalog.csv` (factores de conversión).

## Salidas

- `PipelineResult.vitals_wide`: tabla ancha por paciente lista para graficar/analizar (`heart_rate`, `resp_rate`, `spo2`, `sbp`, `dbp`, `temp`, `context`, `signal_quality`).
- `PipelineResult.labs_long`: tabla larga de laboratorio anclada en disponibilidad.
- `PipelineResult.quality_report`: dict serializable con la comprensión de datos + el tratamiento de calidad aplicado.

## No cubierto

- Imputación de valores faltantes (se decidió no rellenar hacia adelante; ver justificación en `preparacion_datos.py`).
- Interoperabilidad con estándares externos (HL7/FHIR) — fuera de alcance de 12 h, no lo pide el reto como obligatorio.

## Criterios de aceptación

- [x] `python -m pipeline.run_pipeline` procesa los 1000 pacientes de RISA Data V1.0 sin intervención manual.
- [x] `labs_for(pid)` nunca expone un valor antes de su `result_datetime` (por construcción de `labs_long_for_dataset`).
- [x] El reporte de calidad distingue duplicados removidos de implausibles recortados, por fuente.
- [x] Si `pipeline/data/raw/` no existe, `build_dataset()` lanza `RisaDataNotFoundError` con un mensaje claro y el backend no arranca — no existe un dataset sintético de reemplazo (RF-08 se cumple fallando visiblemente, no inventando datos).

## Riesgos y fallback

- CSV grandes (154 MB + 87 MB): mitigado con `usecols` selectivo y caché en `pipeline/data/cache/dataset.pkl` (`ADR-0008`).
- `read_csv(parse_dates=...)` puede degradar en silencio a texto plano combinado con `usecols` en archivos grandes (observado durante el desarrollo): se fuerza `pd.to_datetime` explícito por columna en `comprension_datos._read`.
