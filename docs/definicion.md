# Definición del proyecto

Documento vivo. Aquí se acuerda **qué** vamos a construir, **para quién** y **con qué límites**. Las specs detallan flujos. Los ADR fijan decisiones técnicas.

- Estado: `aceptado — app conversacional en construcción`
- Área de desafío: `1 Salud e inteligencia de datos` — HealthSignal LATAM: Anticiparse al riesgo (Talento TECH, Hackathon Perú 2026), escenario ficticio RISA (Red Integrada de Salud Andina)
- Horizonte: **12 horas** de desarrollo (1 día y medio)
- Equipo: 3 personas (capacidades complementarias)
- Última actualización: 2026-08-26

> El reto ya se reveló. RISA es una red de salud **ficticia** (~1.000 pacientes sintéticos) con datos heterogéneos (historia clínica, laboratorio, signos vitales, wearables, dispositivos, medicamentos, contexto), deliberadamente sucios e irregulares. La solución no diagnostica: prioriza y explica señales para apoyar la revisión de un profesional. Ver [`ADR-0002`](adr/0002-arquitectura-pipeline-agentico-crispdm.md) para el porqué de la arquitectura y el recorte de alcance.

---

## 1. Identificación

| Campo | Valor |
| --- | --- |
| Nombre del prototipo | **RISA Signal** |
| Tagline (una frase) | Convierte datos fragmentados de RISA en alertas priorizadas, explicables y trazables — sin sustituir el criterio clínico. |
| Área | 1 Salud e inteligencia de datos |
| Usuarios primarios | (a) Profesional de salud / analista clínico que revisa el ranking de alertas; (b) rol interno de curación de datos (ingeniero de datos o profesional con conocimiento de datos) que aprueba limpieza y enfoque de análisis antes de correr el pipeline |
| Decisión que el prototipo apoya | Qué paciente/caso revisar primero, y con qué evidencia, dentro de una ventana de monitoreo |

---

## 2. Visión y objetivos

### Visión (1 párrafo)

Un profesional de salud en una institución de RISA no necesita más dashboards de variables sueltas: necesita saber, de entre decenas de pacientes monitoreados, cuáles merecen atención ahora y por qué. RISA Signal integra fuentes heterogéneas (vitales, laboratorio, wearables, contexto), analiza su evolución conjunta en el tiempo y entrega una lista priorizada de señales con evidencia trazable — reduciendo el ruido de alertas por umbral sin ocultar información al profesional responsable.

### Objetivos del prototipo

Objetivos de producto (no de proceso). Deben ser demostrables en la demo.

| ID | Objetivo | Métrica de éxito en 12 h | Prioridad |
| --- | --- | --- | --- |
| OBJ-01 | Detectar señales de riesgo a partir de la evolución temporal y la combinación de ≥2 fuentes heterogéneas (p. ej. vitales + laboratorio), no de umbrales estáticos por variable | Demo end-to-end con ≥1 caso tipo EARLY_SIGNAL/PROGRESSIVE detectado y explicado sobre datos de RISA | P0 |
| OBJ-02 | Presentar cada alerta priorizada con evidencia trazable (variables, ventana temporal, fuente, score) consultable en un dashboard | 100 % de las alertas mostradas en la demo abren una tarjeta de evidencia | P0 |
| OBJ-03 | Distinguir variación esperada de señal relevante para reducir alertas irrelevantes (p. ej. FC alta con contexto de actividad, outlier aislado que se normaliza) | ≥1 caso tipo TRANSIENT/CONTEXTUAL mostrado como descartado o de baja prioridad, con justificación visible | P1 |

### No-objetivos (explícitos)

Lo que **no** vamos a construir aunque sea "bonito". Sirve para defender recortes. Razón: el reto no puntúa funcionalidad no demostrada, y cada una de estas piezas es esfuerzo de plataforma, no de flujo P0.

- Selección automática de modelo por un agente autónomo entre muchas alternativas — en su lugar, comparar 1–2 enfoques (regla dinámica vs. un modelo simple) y justificar cuál queda.
- Cruce/federación de datos entre instituciones RISA y modelos adaptados por institución — se documenta como visión de escalamiento (pitch), no se construye.
- Agente conversacional de propósito general fuera de RISA (el chat SÍ está en el MVP, pero solo anclado a dataset, alertas, UCP, gráficos, modelo remoto y RAG; ver RF-10…RF-16).
- Emisión de diagnóstico, prescripción o decisión clínica autónoma — el reto lo prohíbe explícitamente; la salida siempre es señal + prioridad + evidencia.
- Reentrenamiento automático o loop de mejora continua de modelos en producción.
- Dashboards personalizados por institución o multi-tenant real; un dashboard único que filtra por paciente/institución alcanza.

---

## 3. Alcance

### Dentro

- Flujo feliz: ingesta de 2–3 fuentes heterogéneas de RISA → alineación → detección → ranking de alertas → chat que consulta el dataset, compone dashboards UCP, gráficos interactivos y citas RAG.
- 1 insight útil: ranking de pacientes/casos por prioridad de revisión, con motivo visible.
- Integración HTTP con un modelo preentrenado de otro proyecto, con fallback local.
- Fallback: si el LLM o el modelo remoto fallan, tools + reglas + MockLLM siguen demostrando el flujo.

### Fuera

- Entrenamiento pesado / GPU / MLOps
- Producto multi-tenant, auth completa, billing
- Apps nativas, IoT hardware, despliegue productivo endurecido
- Cobertura exhaustiva del dominio (el prototipo es una franja, no la plataforma)
- Selección automática multi-modelo por agente autónomo, federación entre instituciones, chat NL de propósito general fuera de RISA (ver no-objetivos, sección 2)
- Ingesta de imágenes médicas o texto libre de historia clínica (posible fuente del reto, pero fuera de la ventana de 12 h salvo que sobre tiempo)

### Recorte de las 12 h

Orden de sacrificio si el tiempo se acaba: comparación de 2 enfoques de detección → queda 1 (la regla dinámica); gestión fina de falsas alertas (OBJ-03) → queda un solo caso de ejemplo; buscador NL → se cae primero; pulido visual → cae después. Lo que **no puede caer**: ingesta + alineación de ≥2 fuentes, un mecanismo de score con evidencia, y la tarjeta de explicación (OBJ-01/OBJ-02 son P0 irrenunciables).

---

## 4. Supuestos

Cosas que damos por ciertas hasta que el reto las desmienta.

| ID | Supuesto | Si es falso, qué hacemos |
| --- | --- | --- |
| SUP-01 | ~~HealthSignal LATAM - Data V1.0 llega usable el día 1, sin etiquetas de riesgo~~ **Resuelto:** RISA Data V1.0 completo (1000 pacientes) está en `docs/Participantes Salud/` y es la **única** fuente de datos permitida, vía `pipeline/` ([ADR-0008](adr/0008-pipeline-crispdm-datos-reales.md)); no trae Gold Standard, tal como se anticipó | No hay dataset sintético de reemplazo: si el dataset no está presente, `pipeline.despliegue.build_dataset()` lanza `RisaDataNotFoundError` y el backend no arranca — RF-08 se cumple fallando con mensaje claro, no inventando datos |
| SUP-02 | Hay red e (si aplica) cupo de API | Modo offline / cache / fixture |
| SUP-03 | El jurado valora demo clara + trazabilidad más que SOTA (confirmado: la rúbrica pesa 30 pts en integración/priorización/explicabilidad y penaliza alertas sin evidencia) | Priorizar explicación del resultado sobre accuracy |
| SUP-04 | Con 2–3 fuentes heterogéneas alineadas basta para demostrar el flujo completo (no hace falta consumir todas las fuentes de RISA) | Reducir aún más a 2 fuentes y documentar cuáles quedaron fuera |

---

## 5. Requisitos funcionales (RF)

Comportamiento observable. Cada RF debe poder señalarse en la demo. Estados: `propuesto` · `aceptado` · `implementado` · `descartado`.

| ID | Enunciado | Actor | Prioridad | Spec | Estado |
| --- | --- | --- | --- | --- | --- |
| RF-01 | El sistema ingiere e integra ≥2 fuentes heterogéneas de RISA (p. ej. vitales + laboratorio) preservando procedencia, unidades y timestamp original, vinculadas por el ID sintético de paciente | Sistema | P0 | SPEC-001 | propuesto |
| RF-02 | El sistema alinea temporalmente los registros y trata condiciones de calidad presentes (faltantes, duplicados, outliers, desalineación) con una estrategia visible en el resultado | Sistema | P0 | SPEC-001 | propuesto |
| RF-03 | El sistema analiza la evolución temporal y las relaciones entre variables (no solo valores/umbrales aislados) para identificar patrones o combinaciones potencialmente relevantes por paciente/ventana | Sistema | P0 | SPEC-001 | propuesto |
| RF-04 | El sistema asigna un nivel de riesgo/score/prioridad a cada situación identificada y produce un ranking de casos | Sistema | P0 | SPEC-001 | propuesto |
| RF-05 | El usuario abre una alerta y ve su evidencia: variables involucradas, evolución temporal, fuente(s), patrón identificado y motivo de la prioridad asignada | Usuario | P0 | SPEC-001 | propuesto |
| RF-06 | El sistema diferencia variación esperada de señal relevante para al menos un caso, evitando presentarlo como alerta de alta prioridad sin justificación | Sistema | P1 | SPEC-001 | propuesto |
| RF-07 | El usuario filtra/ordena el listado de alertas (por prioridad, paciente, ventana de tiempo) | Usuario | P1 | SPEC-006 | propuesto |
| RF-08 | El sistema degrada con mensaje claro si una fuente falta o el análisis no produce señal para un caso, sin romper la demo | Sistema | P0 | | propuesto |
| RF-09 | El usuario marca una alerta como revisada/confirmada/descartada; la acción queda registrada como parte de la trazabilidad (human-in-the-loop) | Usuario | P1 | SPEC-006 | propuesto |
| RF-10 | El usuario conversa en lenguaje natural con un LLM sobre pacientes, alertas y el dataset de RISA | Usuario | P0 | SPEC-002 | propuesto |
| RF-11 | El LLM consulta el dataset mediante herramientas (no inventa series); el usuario puede ver la traza de tools | Sistema | P0 | SPEC-002 | propuesto |
| RF-12 | El usuario pide un dashboard y el sistema lo compone con UCP v1.0 (catálogo cerrado de widgets hidratados) | Usuario | P0 | SPEC-003 | propuesto |
| RF-13 | El usuario pide un gráfico y ve una visualización interactiva (Plotly) con datos reales y procedencia | Usuario | P0 | SPEC-004 | propuesto |
| RF-14 | El sistema consulta un modelo preentrenado expuesto por otro proyecto vía HTTP; si no responde, usa fallback local etiquetado | Sistema | P0 | SPEC-005 | propuesto |
| RF-15 | El usuario ve y filtra la cola de alertas por nivel de riesgo (CRITICO…DESCARTADO) con evidencia | Usuario | P0 | SPEC-006 | propuesto |
| RF-16 | Toda explicación de alerta o paciente recupera fragmentos RAG (evidencia/reglas) y los muestra como citas | Sistema | P0 | SPEC-007 | propuesto |

---

## 6. Requisitos no funcionales (RNF)

Calidad del prototipo, no features. Ajustar números cuando exista stack.

| ID | Categoría | Enunciado | Meta (12 h) | Estado |
| --- | --- | --- | --- | --- |
| RNF-01 | Tiempo de ciclo | Un flujo feliz de demo completa en menos de 2 minutos | Demo guiada ≤ 2 min | propuesto |
| RNF-02 | Latencia percibida | Una consulta o refresh no deja la UI “muerta” | Feedback < 2 s; si el job es largo, progreso visible | propuesto |
| RNF-03 | Volumen | Aguanta el sample oficial del reto, no petabytes | Dataset de trabajo + nota de escala | propuesto |
| RNF-04 | Explicabilidad | Todo hallazgo muestra evidencia o trazas | 100 % de ítems P0 con “por qué” | propuesto |
| RNF-05 | Operabilidad | Alguien del equipo levanta el prototipo con un comando documentado | README de arranque ≤ 10 pasos | propuesto |
| RNF-06 | Privacidad | No se suben secretos ni PII real a git | `.env` fuera de git; datos sample | propuesto |
| RNF-07 | Robustez | Fallo de API/dato no tumba la demo | Fallback visible (RNF + RF-06) | propuesto |
| RNF-08 | Claridad visual | La pantalla principal se entiende sin narración larga | 1 pregunta → 1 respuesta visual | propuesto |
| RNF-09 | Seguridad de datos | Los IDs sintéticos de RISA se tratan como si fueran sensibles: no aparecen en logs, commits ni URLs sin necesidad | Ningún ID de paciente en texto plano fuera de la app | propuesto |

Fuera de alcance como RNF de producto real: HA, SSO, auditoría legal, 99.9 % uptime, i18n completa, a11y AAA.

---

## 7. Reglas de negocio (RN)

Invariantes del dominio. Hasta el reto, son reglas de *prototipo de hackathon*; se reemplazan por las del problema real.

| ID | Enunciado | Si se viola |
| --- | --- | --- |
| RN-01 | Un resultado mostrado debe poder rastrearse a evidencia (dato de origen, regla o score) | No se muestra; o se marca como “sin evidencia” |
| RN-02 | Lo no priorizado no se oculta del todo: queda accesible como detalle o lista secundaria | Evitar “caja negra” que esconde el resto |
| RN-03 | El prototipo no afirma certeza médica, legal ni de amenaza si el modelo es probabilístico | Lenguaje de apoyo a la decisión, no de veredicto |
| RN-04 | Ante conflicto entre tiempo y sofisticación, gana un flujo P0 completo | Se recorta modelo, no la demo |
| RN-05 | Datos de ejemplo no se presentan como datos reales del organizador | Etiqueta `sample` / `oficial` visible |
| RN-06 | Si se usa un componente generativo para redactar la explicación de una alerta, el texto generado debe quedar visualmente separado de la evidencia extraída de los datos | La UI distingue "evidencia" (dato) de "explicación" (texto generado) |
| RN-07 | Una mayor cantidad de alertas generadas no se presenta como mejor desempeño; el pitch reporta también qué se descartó y por qué | No usar "número de alertas" como métrica de éxito en la demo |

---

## 8. Usuarios y decisión apoyada

| Actor | Qué necesita decidir | Qué le muestra el prototipo |
| --- | --- | --- |
| Profesional de salud / analista clínico (institución RISA) | Qué paciente/caso revisar primero, y si la señal amerita atención | Ranking de alertas priorizadas + tarjeta de evidencia y explicación por alerta |
| Rol interno de curación de datos — ingeniero de datos o profesional con conocimiento de datos (human-in-the-loop del pipeline, no del dashboard final) | Qué tratamiento de calidad aplicar y qué enfoque de detección usar antes de correr el análisis | Panel de perfilado/calidad con hallazgos y sugerencias, para aprobar o ajustar antes de generar alertas |

---

## 9. Restricciones

- Tiempo de desarrollo: **12 h**.
- Equipo: 3 personas.
- Reto, datos y condiciones: revelados al inicio.
- Entregable: prototipo funcional, no paper ni plataforma.
- Stack: se fija por ADR cuando se conozca el área y el dataset.

---

## 10. Criterios de éxito (demo)

La demo se considera exitosa si, en ≤ 2 minutos:

1. Se entiende el problema en una frase.
2. Se ejecuta el flujo P0 de extremo a extremo.
3. Se muestra un resultado útil para decidir (prioridad, patrón, respuesta o relación).
4. Se enseña la evidencia (RNF-04 / RN-01).
5. Se nombra el recorte y el siguiente paso (honestidad > teatro).

---

## 11. Riesgos (pre-reto)

| ID | Riesgo | Prob. | Impacto | Mitigación / fallback |
| --- | --- | --- | --- | --- |
| R-01 | El dataset llega tarde, sucio o vacío | alta | alto | Sample propio + script de carga; demo con fixture |
| R-02 | El alcance “completo” no cabe en 12 h | alta | alto | P0/P1/P2 y orden de sacrificio (sección 3) |
| R-03 | Dependencia de API externa (LLM, cloud) | media | alto | Cache, fixture, modo offline |
| R-04 | El equipo se reparte mal (3 personas, 1 cuello de botella) | media | alto | 1 persona flujo, 1 persona dato/modelo, 1 persona UI/narración; integración cada 90 min |
| R-05 | El modelo no da señal útil | media | medio | Heurística + ranking; el “por qué” sigue en pie |
| R-06 | Sobre-diseño de docs/arquitectura | baja | medio | Esta ficha + specs solo P0 + ADRs de stack |
| R-07 | Sobre-agentificar: construir agentes autónomos separados por etapa en vez de un pipeline modular con puntos de asistencia puntuales | media | alto | Ver [`ADR-0002`](adr/0002-arquitectura-pipeline-agentico-crispdm.md); un solo pipeline orquestado, "agente" = rol conceptual, no microservicio |
| R-08 | Perseguir el alcance completo del boceto original (multi-institución, selección de modelo autónoma, chat NL abierto) y no llegar a un flujo P0 demostrable | alta | alto | No-objetivos de sección 2; esas piezas van al pitch (impacto/escalabilidad), no al código |

Instanciar riesgos nuevos con [`archetypes/riesgo.md`](archetypes/riesgo.md) y volcarlos aquí.

---

## 12. Stack (se cierra con ADR)

| Capa | Elección | ADR |
| --- | --- | --- |
| Backend | FastAPI + pandas | [0003](adr/0003-backend-fastapi-frontend-react.md) |
| Frontend | React + Vite + Plotly | [0003](adr/0003-backend-fastapi-frontend-react.md) |
| LLM | `gpt-4o` (fallback `gpt-4o-mini` / MockLLM) | [0004](adr/0004-modelo-llm-gpt-4o.md) |
| Dashboards generados | UCP v1.0 (UI Composition Protocol) | [0005](adr/0005-ucp-ui-composition-protocol.md) |
| RAG | Embeddings OpenAI o TF-IDF | [0006](adr/0006-rag-hibrido.md) |
| Modelo preentrenado | HTTP remoto + fallback local | [0007](adr/0007-modelo-preentrenado-http.md) |
| Detección | Reglas dinámicas (umbrales calibrados por percentil, generan evidencia) + el mejor de 4 modelos entrenados y comparados (IsolationForest, LOF, regresión logística, Random Forest) | [0002](adr/0002-arquitectura-pipeline-agentico-crispdm.md), [0009](adr/0009-evaluacion-etiqueta-debil.md) |
| Datos + pipeline | `pipeline/` (CRISP-DM) sobre RISA Data V1.0 real, componente propio consumido por el backend | [0008](adr/0008-pipeline-crispdm-datos-reales.md) |

---

## 13. Plan de las 12 h (esqueleto)

| Bloque | Horas | Salida |
| --- | --- | --- |
| 0. Reto + recorte | 0.5 | Área confirmada, P0 escrito, 1 ADR de stack |
| 1. Datos / corpus mínimo | 2 | Sample cargado y un hallazgo crudo |
| 2. Flujo P0 extremo a extremo | 4 | UI fea pero completa |
| 3. Señal (modelo o ranking) + evidencia | 3 | RF-03 y RF-04 |
| 4. Pulido demo + fallback | 2 | Script de demo, RNF-01/07 |
| 5. Buffer | 0.5 | Lo que se rompió |

Integración cada ~90 min. Nada de rama eterna: el `main` tiene que poder demostrarse desde la hora 3.

---

## 14. Glosario

| Término | Significado aquí |
| --- | --- |
| P0 | Debe verse en la demo sí o sí |
| Evidencia | Dato, regla o score que justifica un resultado |
| Fallback | Camino degradado que todavía demuestra el flujo |
| Sample | Datos de trabajo, no necesariamente los oficiales |
| RISA | Red Integrada de Salud Andina — red de salud ficticia del reto, ~1.000 pacientes sintéticos |
| Señal de riesgo | Combinación/evolución de variables que amerita revisión; no es un diagnóstico |
| Alerta | Instancia de una señal priorizada, con evidencia y explicación asociadas |
| Alerta irrelevante / falsa alerta | Variación que parece anómala pero se explica por contexto, ruido o calidad del dato |
| Trazabilidad | Capacidad de regresar de una alerta a los datos exactos (fuente, variable, ventana) que la originaron |

---

## 15. Pendientes para decidir juntos

- [x] Área de desafío → 1 Salud e inteligencia de datos (HealthSignal LATAM / RISA)
- [x] Nombre definitivo: RISA Signal
- [x] Actor primario y decisión que apoyamos (sección 8)
- [x] Reescribir RF/RNF/RN en lenguaje del reto
- [x] Specs de flujo y de app: SPEC-001 … SPEC-007
- [x] `ADR-0002` … `ADR-0007` (pipeline, stack, LLM, UCP, RAG, modelo remoto)
- [ ] Qué persona cubre ingesta+calidad / detección+scoring / dashboard+narración
