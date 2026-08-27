# ADR-0010 — Grounding estructurado para consultas y dashboards RISA UI

- Estado: `aceptada`
- Fecha: 2026-08-27
- Decisores: equipo

## Contexto

Un gráfico puede estar correctamente ligado a PAT-0724 mientras una búsqueda RAG global devuelve citas de otros pacientes. Pedir al LLM que “piense mejor” no garantiza aislamiento y exponer cadena de pensamiento no aporta una propiedad verificable.

El sistema también debe responder preguntas sobre cohortes, rangos y comparaciones, no únicamente un paciente.

## Decisión

Separar el flujo en cuatro componentes:

1. **Planner:** produce `DashboardQueryPlan` bajo JSON Schema.
2. **Resolver:** aplica filtros permitidos y materializa un `ResolvedScope`.
3. **Composer:** emite RISA UI usando `scope_id`.
4. **Verifier:** bloquea texto, tools, citas y widgets fuera del scope.

Los filtros son declarativos y cerrados: IDs, nivel, prioridad, edad, sexo, región, programa y rangos de score/riesgo. El backend calcula resultados; no se ejecuta SQL generado.

RAG permite documentos de paciente/alerta solo dentro del scope. Reglas y variables pueden ser globales. Los fallbacks se seleccionan por intención (`detail`, `cohort`, `compare`, `trend`, `distribution`, `quality`) y compilan el mismo plan, en lugar de usar una plantilla única.

## Consecuencias

- La evidencia cruzada se rechaza de forma determinista.
- RISA UI conserva flexibilidad para preguntas sobre pacientes y cohortes.
- El frontend puede mostrar filtros y alcance efectivos.
- Las consultas quedan limitadas al catálogo; una dimensión nueva exige ampliar schema, resolver, hidratador y pruebas.
- No se almacena ni se muestra razonamiento privado del modelo.

## Relación con modelos

Anomaly Model y Pattern Model siguen una arquitectura batch. Los `.joblib` ganadores se recargan para producir los scores del `PipelineResult`; su fingerprint se guarda en caché y se expone como procedencia. `PRETRAINED_MODEL_URL` continúa siendo un enriquecimiento externo independiente.
