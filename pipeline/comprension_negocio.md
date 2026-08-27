# CRISP-DM · Fase 1 — Comprensión del negocio

El documento completo y autoritativo es [`docs/Negocio.md`](../docs/Negocio.md) — este archivo no lo duplica, lo **mapea a código**: cada componente de su arquitectura (Anomaly Model, Pattern Model, Context Engine, Evidence Fusion, Risk Engine, Priority Engine, Explanation) apunta al módulo exacto que lo implementa, y cada objetivo específico (OE1-OE12) apunta a dónde se cumple. Se escribe esto **antes** de tocar un CSV — si algo cambia después de ver los datos, se anota aquí por qué, no se calla el cambio.

## 1. Objetivo de negocio (Negocio.md 1.1-1.3)

RISA (Red Integrada de Salud Avanzada) monitorea pacientes desde fuentes que no comparten frecuencia, formato ni momento de disponibilidad. El objetivo no es "predecir riesgo con Machine Learning": es **transformar información fragmentada en señales de riesgo priorizadas, trazables y explicables que apoyen —sin sustituir— la revisión de un profesional de salud**, sin usar en ningún momento información que no estuviera disponible en el instante de la decisión (`T_available <= T_decision`, Negocio.md 1.1.3).

## 2. Arquitectura de Negocio.md → módulos del pipeline

| Componente (Negocio.md) | Pregunta que responde | Módulo | Candidatos evaluados |
| --- | --- | --- | --- |
| **Anomaly Model** (1.4.2) | ¿Es esta observación inusual respecto a la población? | [`deteccion_anomalias.py`](deteccion_anomalias.py) | Estadística (Z-score, MAD, IQR) + ML (`IsolationForest`, `LocalOutlierFactor`) + DL ligero (autoencoder `MLPRegressor`) |
| **Pattern Model** (1.4.3) | ¿Existe un patrón temporal/multivariable que justifique una señal? | [`modelado_patrones.py`](modelado_patrones.py) | Baseline (regresión logística) + ML (Random Forest, XGBoost, LightGBM) — GRU/LSTM/Transformer evaluados y descartados sin entrenar, justificación en el docstring del módulo |
| **Context Engine** (1.4.4) | ¿Qué contexto (actividad, sueño) modifica la interpretación? | [`motor_contexto.py`](motor_contexto.py) | Reglas sobre `ACTIVITY_LEVEL` (wearable) y `SLEEP_STATE` (`patient_context.csv`, intervalos) |
| **Evidence Fusion** (1.4.5) | ¿Qué evidencia sustenta, contextualiza o cuestiona la calidad de la señal? | [`fusion_evidencia.py`](fusion_evidencia.py) | Asigna `PRIMARY`/`SUPPORTING`/`CONTEXT`/`QUALITY` a cada `EvidenceItem` según el patrón detectado |
| **Risk Engine** (1.4.6) | ¿Qué tan prioritaria es esta situación, en una escala 0-1? | [`motor_riesgo.py`](motor_riesgo.py) | Combina score de reglas + Anomaly Model + Pattern Model; nunca escala un `DESCARTADO` |
| **Priority Engine** (1.4.6) | ¿`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`? | [`motor_prioridad.py`](motor_prioridad.py) | Mapea el nivel del motor de reglas, con el `risk_score` como red de seguridad de escalamiento |
| **Explanation** (1.4.7) | ¿Por qué se considera relevante esta señal? | [`explicacion.py`](explicacion.py) | Redacta desde la evidencia ya fusionada — nunca inventa una variable |

El motor de reglas (`modelado.py`) es el hilo que conecta todo: extrae features, calibra umbrales por percentil poblacional (no constantes clínicas fijas) y decide el patrón consultando al Context Engine — es la pieza que genera la evidencia trazable de cada alerta, y la razón por la que ningún modelo de ML "compite" contra ella (compiten Anomaly Model vs. Anomaly Model, y Pattern Model vs. Pattern Model, cada familia entre sí — ver `evaluacion.py`).

## 3. Objetivos específicos (Negocio.md 1.3.2) → dónde se cumplen

| # | Objetivo | Dónde |
| --- | --- | --- |
| OE1 | Integrar las fuentes de RISA conservando IDs | `comprension_datos.py`, `preparacion_datos.py` |
| OE2 | Representación temporal del paciente | `preparacion_datos.pivot_vitals_wide` + ventana móvil (`despliegue.WINDOW_HOURS`) |
| OE3 | Gestionar calidad de los datos | `preparacion_datos.clean_vital_signs/clean_laboratory_results` (dedupe, unidades, implausibles) |
| OE4 | Detectar comportamientos anómalos, comparando enfoques | `deteccion_anomalias.py` |
| OE5 | Identificar patrones relevantes, comparando modelos | `modelado_patrones.py` |
| OE6 | Incorporar contexto | `motor_contexto.py` |
| OE7 | Fusionar evidencias | `fusion_evidencia.py` |
| OE8 | `risk_score` + prioridad | `motor_riesgo.py`, `motor_prioridad.py` |
| OE9 | Explicaciones verificables | `explicacion.py` |
| OE10 | Trazabilidad hasta el registro fuente | `despliegue.export_submission` (`evidence.csv`: `source_file`, `record_id`) |
| OE11 | Evaluar bajo distintos escenarios | Patrones `STABLE`/`CONTEXTUAL`/`TRANSIENT`/`PROGRESSIVE_MULTISOURCE`/`EARLY_SIGNAL`/`LOW_QUALITY`/`MISSING_SOURCE` — todos alcanzables sobre RISA Data V1.0 real |
| OE12 | Reproducibilidad | `pipeline/run_pipeline.py`, caché en `pipeline/data/cache/` |

## 4. Por qué no hay GRU/LSTM/Transformer ni NLP/LLM dentro del pipeline

Negocio.md 1.4.3 y 1.4.4 los listan como candidatos posibles, no obligatorios ("la selección no está predeterminada... según disponibilidad y características de los datos"). Decisión tomada, no omisión:

- **GRU/LSTM/Transformer** (Pattern Model): con ~1000 pacientes y ~30 positivos en la etiqueta débil, un modelo secuencial profundo no tiene datos suficientes para aprender señal por encima del ruido — y el vector de entrada ya es un resumen por ventana (pendientes, medias), no una secuencia cruda. Ver `modelado_patrones.py`.
- **Autoencoder** (Anomaly Model): sí se implementa, pero como `MLPRegressor` de scikit-learn (cuello de botella, error de reconstrucción) en vez de una red en PyTorch/TensorFlow — cubre la familia "DL" sin la sobrecarga de un framework de deep learning completo para un vector de 13 features. Ver `deteccion_anomalias.py`.
- **NLP/LLM en el Context Engine**: el LLM sí existe en el sistema (`backend/app/llm/`), pero como capa conversacional sobre la evidencia ya calculada por el pipeline (chat, RAG), nunca como parte del cálculo de contexto/riesgo — mantiene la separación evidencia/explicación que exige RN-06 y Negocio.md 1.4.7 ("un LLM... no podrá generar hechos que no estén presentes en los datos").

## 5. Restricciones conocidas antes de empezar

- RISA Data V1.0 (`pipeline/data/raw/`) es la única fuente permitida — no hay dataset sintético de reemplazo ([`ADR-0008`](../docs/adr/0008-pipeline-crispdm-datos-reales.md)).
- No hay Gold Standard ni casos ocultos — toda evaluación cuantitativa es sobre una etiqueta débil, declarada como tal ([`ADR-0009`](../docs/adr/0009-evaluacion-etiqueta-debil.md)).
- Los archivos originales de `pipeline/data/raw/` nunca se modifican; todo lo derivado vive en `pipeline/data/{clean,features,model,results}/` (Documento Técnico Maestro V2, sección 12).
- El sistema apoya la decisión; no diagnostica, no prescribe, no decide de forma autónoma.
