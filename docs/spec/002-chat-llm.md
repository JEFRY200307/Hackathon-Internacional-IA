# SPEC-002 — Chat para conversar con el LLM sobre el dataset RISA

- Estado: `aceptada`
- Área: 1 Salud
- Relaciona: RF-10, RF-11, RNF-02, RNF-07, RN-03, RN-06
- Autor: equipo
- Fecha: 2026-08-26

## Problema

El profesional de salud no quiere aprender un dashboard fijo: quiere preguntar en lenguaje natural *qué está pasando* sobre los pacientes de RISA y recibir una respuesta anclada a datos, no a alucinaciones clínicas.

## Actor y disparador

Profesional de salud / analista. Dispara al enviar un mensaje en el panel de chat.

## Comportamiento esperado

1. El usuario escribe una pregunta en español (p. ej. “¿quién debo revisar primero?”).
2. El backend arma el historial de la sesión, inyecta el system prompt de RISA Signal y llama al LLM (ADR-0004) con herramientas.
3. El LLM puede invocar herramientas de datos, alertas, RAG, modelo remoto, UCP o gráficos. El loop de tools no supera 4 vueltas.
4. La respuesta visible mezcla texto (explicación) con bloques estructurados (citas, widgets). El texto nunca se presenta como diagnóstico.
5. Si no hay API key o el proveedor cae, un proveedor *mock* responde con plantillas ancladas al dataset local (RNF-07).
6. **Resultado observable:** el usuario ve una respuesta en < 15 s (o progreso visible), con al menos una cita o traza de herramienta cuando la pregunta es sobre pacientes/datos.

## Entradas

- Historial de mensajes `{role, content}` de la sesión.
- Dataset alineado en memoria / sample (SPEC-001).
- `OPENAI_API_KEY` opcional; `LLM_MODEL` configurable.

## Salidas

- Mensaje del asistente: texto, `citations[]`, `tool_trace[]`.
- Opcionalmente bloques UCP y/o charts (SPEC-003, SPEC-004).
- Nada se persiste como historia clínica; la sesión vive en memoria del proceso (P1: localStorage en el cliente).

## No cubierto

- Auth, multi-usuario, historial en base de datos.
- Chat de propósito general fuera de RISA.
- Voz, adjuntos de PDF, streaming token a token (stretch).

## Criterios de aceptación

- [ ] Una pregunta sobre el ranking de alertas produce una respuesta en español que menciona al menos un `patient_id` existente.
- [ ] El system prompt prohíbe diagnóstico/prescripción y la UI muestra el disclaimer.
- [ ] Sin API key, el mock no tumba la demo y declara que está en modo degradado.
- [ ] La traza de tools queda visible en un detalle plegable (trazabilidad de la conversación).

## Riesgos y fallback

- Cuota/red del LLM: `MockLLM` + tools reales sobre el sample.
- El modelo ignora tools: el backend, si la pregunta matchea intenciones (`alerta`, `dashboard`, `gráfico`), ejecuta tools deterministas y adjunta el resultado.
