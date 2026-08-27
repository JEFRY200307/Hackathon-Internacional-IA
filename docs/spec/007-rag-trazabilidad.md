# SPEC-007 — RAG para trazabilidad y explicación

- Estado: `aceptada`
- Área: 1 Salud
- Relaciona: RF-16, RNF-04, RN-01, RN-06
- Autor: equipo
- Fecha: 2026-08-26

## Problema

El LLM no debe “recordar” por qué existe una alerta. Debe recuperar el bundle de evidencia, el diccionario de variables y las reglas que la originaron, y citarlos.

## Actor y disparador

El chat (SPEC-002) y el agente de explicación. Dispara en cada turno que hable de un paciente, alerta o patrón, o cuando el usuario pide “¿por qué?”.

## Comportamiento esperado

1. Al arrancar, el backend indexa documentos: cada alerta (evidencia JSON), diccionario de variables, resumen por paciente, texto de reglas.
2. Recuperación: embeddings `text-embedding-3-small` si hay API key; si no, TF-IDF/cosine (sigue siendo RAG, offline).
3. Tool `retrieve_evidence(query, k=4)` devuelve fragmentos con `source_id`, `kind`, `snippet`.
4. El system prompt obliga a citar `source_id` en la respuesta. La UI pinta chips de cita distintos del texto generado (RN-06).
5. **Resultado observable:** “¿por qué P001 está en ALTO?” muestra explicación + ≥1 cita que contiene variables/ventana reales.

## Entradas

- Corpus generado del propio pipeline (no la web abierta).
- Query del usuario o del propio LLM.

## Salidas

- `citations[]` en el mensaje del asistente.
- `GET /api/rag/search?q=` para depurar el índice.

## No cubierto

- RAG sobre PDFs de historia clínica ni internet.
- Re-ranker cross-encoder.
- Actualización incremental del índice si cambian alertas HITL (se reindexa en el mismo proceso al marcar review, best-effort).

## Criterios de aceptación

- [ ] La búsqueda “creatinina progresiva” recupera la alerta de P001 (o el paciente equivalente del sample).
- [ ] Toda respuesta sobre una alerta concreta incluye al menos una cita con `source_id` de tipo `alert` o `rule`.
- [ ] Sin embeddings (sin API), TF-IDF sigue recuperando el documento correcto en el sample.

## Riesgos y fallback

- Embeddings caídos: TF-IDF.
- El modelo ignora citas: el backend adjunta igual los top-k del retrieval al mensaje (la UI no depende de que el LLM los copie).
