# ADR-0009 — Evaluación train/val/test con etiqueta débil (no hay Gold Standard)

- Estado: `aceptada`
- Fecha: 2026-08-27
- Decisores: equipo
- Relaciona: `ADR-0008`, `SPEC-009`, RN-03 (`definicion.md`)

## Contexto

La guía oficial y `02_KIT_ENTREGA/README_SUBMISSION_KIT.md` son explícitos: RISA Data V1.0 **no incluye Gold Standard, casos ocultos, rankings esperados ni thresholds oficiales**. `validate_submission.py` valida solo la forma de `signals.csv`/`evidence.csv`, nunca el desempeño.

Al mismo tiempo, el reto exige "resultados medibles" (sección "Resultados esperados", punto 6) y la rúbrica pesa "Validación técnica con caso oficial no preparado". Reportar precisión/recall sin decir contra qué se midieron sería presentar certeza que no existe — exactamente lo que RN-03 prohíbe ("el prototipo no afirma certeza médica... si el modelo es probabilístico").

## Decisión

Evaluar con una **etiqueta débil (proxy)**, construida a partir del propio motor de reglas, nunca presentada como verdad clínica:

- **Positivo (1):** patrón `PROGRESSIVE_MULTISOURCE` o `EARLY_SIGNAL` y no `DESCARTADO` — es decir, un patrón que el motor de reglas corroboró con ≥2 fuentes y evolución temporal, no un umbral aislado.
- **Negativo (0):** todo lo demás (`STABLE`, `CONTEXTUAL`, `TRANSIENT`, `LOW_QUALITY`, `MISSING_SOURCE`).

Split por **paciente** (no por fila), 85 % (`dev`) / 15 % (`test`) con semilla fija (`pipeline/evaluacion_comun.split_patients`), para no filtrar información entre conjuntos. `dev` se evalúa con **validación cruzada de 5 folds** (no un único split de validación pequeño y ruidoso: con ~1000 pacientes y una etiqueta positiva minoritaria, un solo split de 150 puede tener 3-4 positivos); `test` queda intocado hasta el chequeo final.

Siguiendo la arquitectura de `docs/Negocio.md` (1.4.2/1.4.3), la comparación se hace **por familia, no como una sola carrera de 5 candidatos**:

**Anomaly Model** (`pipeline/deteccion_anomalias.py`, no supervisado — ¿es esto inusual respecto a la población?): Z-score, MAD, IQR (estadística), `IsolationForest`, `LocalOutlierFactor` (ML), autoencoder `MLPRegressor` (DL ligero).

**Pattern Model** (`pipeline/modelado_patrones.py`, supervisado contra la etiqueta débil — ¿hay un patrón que justifique una señal?): regresión logística (baseline), Random Forest, XGBoost, LightGBM.

Las **reglas dinámicas** no compiten en ninguna de las dos tablas: no son un estimador que se pueda ajustar/guardar, son el motor de `modelado.py` que genera la evidencia trazable de cada alerta — se reportan aparte, como referencia.

Cada candidato se reporta con **matriz de confusión** (TP/FP/FN/TN) + precisión/recall/F1 en `cv` y `test`, y ROC-AUC cuando produce un score continuo. No se reporta solo la métrica que la guía menciona más (F1): se calculan todas y se muestran todas, para que la elección sea auditable y no una afirmación de autoridad.

**Selección (por familia):** mayor F1 promedio en `cv`, desempate por precisión. El ganador de cada familia se reentrena sobre todo `dev` y se **persiste** (`pipeline/data/model/{anomaly,pattern}_model_best.joblib` + metadata, vía `evaluacion.persist_best_models`), y se aplica a los 1000 pacientes (`evaluacion.score_all`) sin volver a entrenar — esos dos scores alimentan `anomaly_score`/`pattern_score` en cada alerta, y `motor_riesgo.compute_risk_score` los fusiona con el score de reglas en un `risk_score` único. Todo el bloque de evaluación incluye siempre `labels_source` señalando que es una etiqueta proxy — en `pipeline/run_pipeline.py` y en `GET /api/pipeline/report`.

**Resultado de referencia** (corrida completa, 1000 pacientes): Anomaly Model → `mad` (F1 `cv` 0.23, F1 `test` 0.11 — nótese que el autoencoder y Z-score generalizaron mejor a `test`, 0.42 y 0.38 respectivamente; se documenta la discrepancia, no se oculta). Pattern Model → `xgboost` (F1 `cv` 0.51, F1 `test` 0.67, precisión perfecta en `test`).

## Alternativas consideradas

| Opción | Por qué no (o por qué sí) |
| --- | --- |
| No reportar ninguna métrica cuantitativa | Descartada: el reto pide evidencia experimental explícita; "no medimos nada" pesa peor que una métrica bien acotada |
| Inventar un Gold Standard manual sobre ~30 casos revisados a mano | Descartado por tiempo y por riesgo de sesgo de confirmación (etiquetar "a ojo" justo los casos que las reglas ya marcan) |
| Comparar un solo modelo de ML contra las reglas (v1 de esta ADR) | Descartado: no permite afirmar "se entrenaron y compararon modelos" |
| Un único ranking de 5 candidatos mezclando anomalía y patrón (v2 de esta ADR) | Descartado tras alinear con `docs/Negocio.md`: mezclar familias con supuestos distintos (no supervisado vs. supervisado) en una sola tabla oculta que responden preguntas distintas — Anomaly Model y Pattern Model son comparaciones separadas en la arquitectura de negocio, no una sola |
| Elegir el ganador por F1 en un único split de validación (v1/v2 de esta ADR) | Descartado: `Random Forest` ganaba así y se desplomaba con validación cruzada real — el único split era demasiado ruidoso para decidir con confianza |
| **Etiqueta débil + split por paciente + validación cruzada de 5 folds + Anomaly Model y Pattern Model comparados por separado + ambos ganadores persistidos** | Elegida: es la única evaluación posible sin el Gold Standard real, es honesta sobre su propio límite, sigue la arquitectura de negocio documentada, y deja dos artefactos reutilizables (no solo números en un reporte) |

## Consecuencias

- Positivas: cumple el punto 6 de "Resultados esperados" sin violar RN-03; ambas comparaciones son reales, reproducibles (semilla fija) y auditables con matriz de confusión; los dos modelos ganadores son archivos `.joblib` reales que el backend carga y usa, no solo números en un reporte.
- Negativas / deuda: la métrica mide *consistencia interna* del sistema (¿el modelo elegido coincide con la etiqueta derivada de las propias reglas?), no *precisión clínica real* — hay que decirlo así en el pitch. Con ~1000 pacientes y una etiqueta positiva minoritaria (~3-4 %), los modelos supervisados entrenan sobre pocas decenas de ejemplos positivos, y el Anomaly Model muestra explícitamente que el ganador de `cv` no siempre es el más robusto en `test` — una limitación de tamaño de muestra, no de metodología, declarada tal cual.
- Impacto en RF/RNF/RN: sostiene RN-03; alimenta el criterio de "Identificación de señales de riesgo" (8 pts) con evidencia experimental comparativa en vez de una afirmación sin respaldo.

## Reversibilidad

Alta: si en una fase posterior el organizador entrega un Gold Standard real, `pipeline/evaluacion.py` (y los dos módulos que orquesta) se reemplaza sin tocar `modelado.py` ni el resto del pipeline — el contrato de entrada (`AlertDraft` + `FEATURE_KEYS`, en `evaluacion_comun.py`) no cambia, solo la fuente de `y_dev`/`y_test`.
