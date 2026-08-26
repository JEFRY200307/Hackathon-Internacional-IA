# SPEC-001 — Detección y priorización de señales de riesgo sobre datos heterogéneos de RISA

- Estado: `borrador`
- Área: 1 Salud
- Relaciona: RF-01, RF-02, RF-03, RF-04, RF-05, RF-06, RF-08, RNF-04, RNF-07, RN-01, RN-02, RN-06
- Autor: equipo
- Fecha: 2026-08-26

## Problema

Un profesional de salud (o analista) de una institución de RISA monitorea a varios pacientes a la vez. Ninguna fuente aislada (un signo vital, un resultado de laboratorio) le dice por sí sola qué caso revisar primero. Necesita una lista priorizada de situaciones que combinan varias fuentes y su evolución en el tiempo, cada una con evidencia clara de por qué se marcó así — sin que el sistema le diga qué diagnóstico tiene el paciente.

## Actor y disparador

- **Actor primario:** profesional de salud / analista clínico. Dispara al abrir el dashboard (no hay una acción de "consulta" activa en el MVP: el ranking ya está calculado).
- **Actor secundario (upstream, human-in-the-loop del pipeline):** curador de datos (ingeniero o profesional con conocimiento de datos), que aprueba o ajusta el tratamiento de calidad sugerido por el agente de datos antes de que el pipeline calcule alertas. Ver `ADR-0002`.

## Comportamiento esperado

1. El sistema ingiere ≥2 fuentes heterogéneas de RISA para una ventana temporal común (p. ej. signos vitales + laboratorio de los mismos pacientes), vinculadas por el ID sintético del paciente.
2. El sistema alinea los registros en el tiempo y aplica el tratamiento de calidad aprobado por el curador (faltantes, duplicados, outliers, desalineación) — decisión visible, no silenciosa.
3. Para cada paciente/ventana, el sistema analiza la evolución conjunta de las variables (tendencia, cambios, combinación entre fuentes), no solo el último valor de cada una.
4. El sistema asigna un score/nivel de prioridad a cada situación detectada y arma un ranking de casos.
5. El sistema construye, por cada alerta, un bundle de evidencia: variables involucradas, ventana temporal, fuente(s), patrón identificado.
6. El agente de explicación redacta una explicación en lenguaje natural a partir del bundle (nunca al revés: el texto no puede introducir variables que no estén en la evidencia).
7. El dashboard muestra el ranking; al abrir una alerta, se ve la tarjeta con evidencia (datos) y explicación (texto generado) claramente separadas.
8. **Resultado observable:** el profesional puede, en menos de 2 minutos, identificar el caso de mayor prioridad, ver qué lo generó, y distinguir un caso real de un caso de baja relevancia (p. ej. un TRANSIENT descartado) con su motivo.

## Entradas

- Fuentes RISA seleccionadas para el MVP (a confirmar con el esquema real de Data V1.0; candidatas: `vital_signs`, `laboratory`, opcionalmente `wearables`).
- ID sintético de paciente como clave de unión.
- Ventana temporal de trabajo (definida por el equipo, no prescrita por el reto).
- Reglas/umbrales dinámicos y/o el modelo simple elegido en `ADR-0002`.

## Salidas

- Ranking de alertas ordenado por prioridad, consultable en el dashboard.
- Por alerta: nivel/score de prioridad, variables relevantes, ventana temporal, fuente(s), patrón detectado, evidencia y explicación.
- Registro de la decisión humana si se usa RF-09 (revisada/confirmada/descartada).
- Nada de esto se presenta como diagnóstico, prescripción o decisión clínica autónoma (RN-03 en `definicion.md`).

## No cubierto

- Selección automática de modelo entre múltiples candidatos (ver ADR-0002: se comparan 1–2 a mano).
- Cruce de datos entre instituciones distintas de RISA.
- Ingesta de imágenes médicas o texto libre de historia clínica.
- Búsqueda en lenguaje natural sobre el dashboard (stretch, no P0).
- Reentrenamiento o mejora automática del modelo a partir de las decisiones humanas (RF-09 solo registra, no realimenta en vivo).

## Criterios de aceptación

- [ ] El pipeline corre de punta a punta sobre ≥2 fuentes reales de Data V1.0 (o el sample propio si V1.0 no llega a tiempo, SUP-01).
- [ ] Al menos 1 alerta mostrada corresponde a un patrón que solo es visible combinando fuentes/tiempo (no un umbral de una sola variable) — evidencia de OBJ-01.
- [ ] Al menos 1 caso de baja relevancia (variación esperada, outlier transitorio) aparece con prioridad baja y motivo visible, no oculto — evidencia de OBJ-03 / RN-02.
- [ ] Toda alerta abierta muestra evidencia (datos) y explicación (texto generado) en secciones visualmente distintas — RN-06.
- [ ] Si falta una fuente para un paciente, el sistema lo indica explícitamente en vez de omitir el caso silenciosamente — RF-08.
- [ ] El README documenta qué tratamiento de calidad se aplicó y por qué (trazabilidad de la decisión del curador).

## Riesgos y fallback

- Si el modelo/analítica elegido no produce señal útil sobre los datos reales: cae a la regla dinámica (combinación de variables + tendencia), que sigue produciendo score y evidencia (R-05 en `definicion.md`).
- Si el agente de explicación (LLM) no está disponible o da texto incoherente: fallback a una plantilla de texto fija que arma la explicación directamente desde el bundle de evidencia (sin IA generativa) — la demo no depende de que la API esté arriba.
- Si Data V1.0 no llega o llega incompleto: usar el sample sintético propio del mismo esquema (SUP-01) y decirlo explícitamente en la demo (RN-05).
