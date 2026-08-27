# Guía — Arquitectura y patrones de software

El diagrama completo está en `docs/arquitectura.md`; esta guía nombra los patrones que ese diagrama usa y dónde viven en el código, para que un cambio futuro respete la misma forma en vez de mezclar estilos.

## 1. Tres componentes de primer nivel, una sola dirección de dependencia

```
pipeline/  →  backend/  →  frontend/
```

`pipeline/` no importa nada de `backend/` ni `frontend/`. `backend/` importa `pipeline/` (vía `app/data/loader.py`) pero nunca al revés. `frontend/` solo habla HTTP con `backend/`. Esta dirección única es la que hace posible que `pipeline/run_pipeline.py` corra solo, sin levantar FastAPI ni React — es lo que se corre para regenerar `pipeline/data/results/signals.csv` (`SPEC-009`).

## 2. Pipeline (ETL + Pipes and Filters)

`pipeline/despliegue.build_dataset()` encadena funciones puras que reciben un DataFrame y devuelven otro: `load_raw_sources → clean_vital_signs → pivot_vitals_wide → extract_features → calibrate_thresholds → score_patient`. Cada etapa se puede probar y correr por separado (de hecho, `run_pipeline.py --patients N` corre el mismo pipeline sobre un subconjunto para depurar rápido). Ninguna etapa muta el DataFrame de la anterior in-place — cada función devuelve uno nuevo, así el orden de las etapas siempre se puede reordenar o insertar una etapa nueva sin sorpresas de estado compartido.

## 3. Facade / contrato estable (`Dataset` = `PipelineResult`)

`backend/app/data/loader.py` no tiene lógica propia — es un facade de una línea sobre `pipeline.despliegue`. El resto del backend (`charts.py`, `llm/tools.py`, `alerts/service.py`) programa contra la forma `Dataset` (`.patients`, `.vitals_for(pid)`, `.labs_for(pid)`, `.origin`), no contra cómo se construyó. Esto es lo que permitió reemplazar el generador sintético (`app/data/sample.py`) por el pipeline real (`ADR-0008`) sin tocar una sola línea de `charts.py`.

## 4. Strategy (varios enfoques de detección comparados, no encadenados)

`pipeline/modelado.py` expone `score_patient` (reglas dinámicas, explicable) como una función independiente del resto de candidatos — genera la evidencia trazable de cada alerta, no compite contra los modelos de ML. Sobre el mismo vector de features corren dos comparaciones separadas, cada una con varios candidatos que no se llaman entre sí: `pipeline/deteccion_anomalias.py` (Anomaly Model: Z-score, MAD, IQR, `IsolationForest`, `LocalOutlierFactor`, autoencoder) y `pipeline/modelado_patrones.py` (Pattern Model: regresión logística, Random Forest, XGBoost, LightGBM). `pipeline/evaluacion.py` orquesta ambas comparaciones con la misma matriz de confusión y el mismo split `dev`/`test`. `alerts/service.py` combina el resultado (`score` de reglas decide el nivel; `anomaly_score`/`pattern_score` de los ganadores viajan como dato secundario; `motor_riesgo.py` los fusiona en `risk_score`), pero cualquiera de los candidatos podría reemplazarse sin tocar los demás. Cada familia elige su ganador por un criterio documentado (F1 en validación cruzada, desempate por precisión) y lo persiste en disco; no hay selección automática sin comparar ni un solo modelo elegido a priori.

## 5. Adapter (modelo preentrenado externo)

`backend/app/adapters/pretrained.py` aísla el único punto que sabe que existe un servicio HTTP externo. Si no responde (o no está configurado), `local_predict()` calcula un score de emergencia con las mismas `features` del `AlertDraft` — el resto del sistema (`llm/tools.py`, `main.py`) llama siempre a `predict_risk()` sin saber si la respuesta vino de la red o del fallback (`ADR-0007`).

## 6. Protocolo de UI declarativo (UCP) en vez de vistas ad hoc

`backend/app/ucp/protocol.py` define un catálogo cerrado de tipos de widget (`kpi`, `chart`, `table`, `alert_list`, `evidence`, `markdown`). El backend arma el documento (`template_turno`) y lo "hidrata" con datos reales (`charts.hydrate_ucp`); el frontend (`UcpCanvas.tsx`) solo sabe renderizar esos 6 tipos, nunca ejecuta lógica de negocio. Es lo que le permite al LLM (`emit_ucp` tool) componer un dashboard nuevo con la misma superficie que el dashboard fijo del turno, sin abrir una puerta a HTML/JS arbitrario generado por el modelo (`ADR-0005`).

## 7. Separación evidencia vs. explicación (RN-06)

`EvidenceItem` (dato: variable, fuente, ventana, valores) y el texto de una alerta (`AlertDraft.title`, o la respuesta del LLM en el chat) son estructuras distintas en todo el código, nunca el mismo string. El frontend las renderiza en bloques visualmente separados (`.evidence` vs. la burbuja de chat) a propósito: lo que sale de los datos y lo que redacta un modelo generativo no deben poder confundirse.

## 8. Caché explícita, no un ORM ni una base de datos

`pipeline/despliegue.load_or_build()` serializa el `PipelineResult` completo a un único pickle (`pipeline/data/cache/dataset.pkl`) porque el dataset es de solo lectura durante la corrida y reprocesar ~250 MB de CSV en cada `uvicorn --reload` no es razonable. No se introdujo Postgres/DuckDB para esto: hubiera sido infraestructura para un problema que un archivo resuelve en un prototipo de 12 h (ver "Libertad tecnológica" de la guía oficial — la sofisticación no es el objetivo, resolver el problema sí).
