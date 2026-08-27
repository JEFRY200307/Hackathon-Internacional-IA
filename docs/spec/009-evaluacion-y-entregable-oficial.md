# SPEC-009 — Anomaly/Pattern Model, Evidence Fusion, Risk/Priority Engine y entregable oficial

- Estado: `implementado`
- Área: 1 Salud
- Relaciona: RF-03, RF-04, RF-06, RNF-04, ADR-0008, ADR-0009
- Autor: equipo
- Fecha: 2026-08-27

## Problema

Sobre datos reales y ruidosos, los umbrales clínicos fijos casi nunca se cumplen o se cumplen siempre — ninguno de los dos casos separa señal de ruido. Un solo modelo "elegido a priori" tampoco es defendible: `docs/Negocio.md` (1.4.2/1.4.3) exige comparar varias familias de detección (Anomaly Model, Pattern Model) antes de elegir. Además, el reto exige un entregable estructurado (`signals.csv` + `evidence.csv`) con un formato exacto, verificado por `validate_submission.py`.

## Actor y disparador

- **Actor:** `pipeline.despliegue.build_dataset()` (modelado + evaluación, corre en cada arranque o `--rebuild`); `pipeline.despliegue.export_submission()` (entregable, vía `--export-submission`).

## Comportamiento esperado

1. **Extracción de features** (`modelado.extract_features`) por paciente: pendientes por muestra de FC/SpO2/FR/PAS, medias, fracción de tiempo en actividad y en sueño, mayor variación relativa entre `LAB_A..D`, mediana de `signal_quality`.
2. **Calibración poblacional** (`modelado.calibrate_thresholds`): percentil 90 (o 10 para caídas) de cada pendiente **sobre la población efectivamente cargada en la corrida** — no una constante clínica fija.
3. **Motor de reglas + Context Engine** (`modelado.score_patient`, consulta `motor_contexto.is_activity_explained`) deciden, en este orden, patrón y nivel: `LOW_QUALITY` → `CONTEXTUAL` → `TRANSIENT` → `PROGRESSIVE_MULTISOURCE` → `EARLY_SIGNAL` → `MISSING_SOURCE` → `STABLE`. Genera la evidencia trazable de cada alerta.
4. **Anomaly Model** (`deteccion_anomalias.compare_anomaly_models`): compara Z-score, MAD, IQR, `IsolationForest`, `LocalOutlierFactor` y un autoencoder ligero (`MLPRegressor`), con matriz de confusión + precisión/recall/F1/ROC-AUC en validación cruzada (`cv`) + test (`ADR-0009`).
5. **Pattern Model** (`modelado_patrones.compare_pattern_models`): compara regresión logística, Random Forest, XGBoost y LightGBM sobre el mismo vector de features y el mismo split, con la misma metodología.
6. **Selección y persistencia** (`evaluacion.persist_best_models`): el candidato con mayor F1 en `cv` (desempate por precisión) de cada familia se guarda en `pipeline/data/model/{anomaly,pattern}_model_best.joblib` + metadata, y se aplica a los 1000 pacientes (`evaluacion.score_all`) para producir `anomaly_scores`/`pattern_scores` — sin volver a entrenar.
7. **Evidence Fusion** (`fusion_evidencia.assign_evidence_roles`): etiqueta cada `EvidenceItem` como `PRIMARY`/`SUPPORTING`/`CONTEXT`/`QUALITY` según el patrón detectado.
8. **Risk Engine** (`motor_riesgo.compute_risk_score`): combina score de reglas + `anomaly_score` + `pattern_score` en un `risk_score ∈ [0,1]`; nunca escala un `DESCARTADO`.
9. **Priority Engine** (`motor_prioridad.assign_priority`): mapea a `LOW/MEDIUM/HIGH/CRITICAL`, con el `risk_score` como red de seguridad de escalamiento.
10. **Explanation** (`explicacion.build_explanation`): redacta la explicación desde la evidencia ya fusionada, siguiendo la estructura QUÉ/VARIABLES/CONTEXTO/CALIDAD/POR QUÉ (Negocio.md 1.5.7).
11. **Exportación oficial** (`despliegue.export_submission`): un `signal_id` por paciente con `decision_datetime` = último dato disponible en su ventana, `evidence_start`/`evidence_end` acotados a esa misma ventana, `priority_level` del Priority Engine, y `evidence.csv` con un registro por cada `EvidenceItem` fusionado.

## Entradas

- `PipelineResult` ya limpio, con Context Engine aplicado (`SPEC-008`).

## Salidas

- `pipeline/data/results/signals.csv`, `evidence.csv` (1000 + 1037 filas en la corrida de referencia sobre RISA Data V1.0 completo).
- `GET /api/pipeline/report`: `data_quality` + `evaluation` (`anomaly_model` + `pattern_model`, cada uno con `cv`/`test` y matriz de confusión).
- Distribución de referencia sobre los 1000 pacientes: `DESCARTADO 413 · BAJO 554 · MEDIO 27 · ALTO 5 · CRITICO 1`.
- Modelos ganadores de referencia: Anomaly Model = `mad` (F1 `cv` 0.23); Pattern Model = `xgboost` (F1 `cv` 0.51, F1 `test` 0.67).

## No cubierto

- Búsqueda de hiperparámetros automática (grid/random search) — se usan configuraciones razonables fijas, no una optimización exhaustiva.
- GRU/LSTM/Transformer para el Pattern Model — decisión documentada en `pipeline/comprension_negocio.md` (tamaño de muestra insuficiente para deep learning secuencial).
- Reentrenamiento en producción a partir de `review_status` (RF-09 solo registra).

## Criterios de aceptación

- [x] `python "docs/Participantes Salud/02_KIT_ENTREGA/validate_submission.py" pipeline/data/results/ --risa pipeline/data/raw` imprime `VALID SUBMISSION FORMAT`.
- [x] Todo `signal_id` en `evidence.csv` existe en `signals.csv` y tiene ≥1 fila de evidencia (verificado por el mismo validador).
- [x] `evidence_start <= evidence_end <= decision_datetime` para el 100 % de las filas (regla temporal, verificado por el validador).
- [x] Al menos un caso real `CRITICO`/`ALTO` y al menos un `DESCARTADO` con motivo distinto de "sin evidencia" aparecen en la corrida completa.
- [x] El reporte de evaluación siempre incluye `labels_source` señalando que es una etiqueta proxy (RN-03).
- [x] `evidence.csv` usa los cuatro roles oficiales (`PRIMARY`/`SUPPORTING`/`CONTEXT`/`QUALITY`), no solo dos.

## Riesgos y mitigación

- Si la calibración/entrenamiento sobre una corrida parcial (`--patients N`) produce resultados poco representativos: documentado en `pipeline/README.md`; la corrida oficial de entrega siempre es sin `--patients`.
- Si el modelo ganador de `cv` generaliza peor que otro candidato en `test` (le pasó al Anomaly Model: `mad` gana `cv` pero el autoencoder tiene mejor `test`): se reporta igual, sin ocultarlo — es la razón por la que se usa validación cruzada y se documenta también el `test`.
- Si no hay RISA Data V1.0 disponible: no hay fallback — `build_dataset()` lanza `RisaDataNotFoundError` (`ADR-0008`).
