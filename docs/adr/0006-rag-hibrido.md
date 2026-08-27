# ADR-0006 — RAG híbrido (embeddings OpenAI + TF-IDF) sobre evidencia propia

- Estado: `aceptada`
- Fecha: 2026-08-26
- Decisores: equipo

## Contexto

La rúbrica premia trazabilidad. Un LLM sin recuperación inventa variables. El corpus es pequeño (alertas + diccionario + reglas), no Wikipedia.

## Decisión

Índice in-process, sin servidor vectorial:

1. Si hay API key: `text-embedding-3-small` + cosine.
2. Si no: TF-IDF + cosine sobre el mismo corpus.
3. Tool `retrieve_evidence`; la UI siempre muestra los fragmentos, aunque el modelo no los cite.

No Chroma/Pinecone en el MVP (una dependencia y un daemon menos).

## Alternativas consideradas

| Opción | Por qué no (o por qué sí) |
| --- | --- |
| Solo prompt con todas las alertas | Cabe en el sample chico, no escala ni demuestra RAG. |
| ChromaDB / FAISS | Más infra de la necesaria para < 200 docs. |
| **Híbrido embeddings / TF-IDF in-memory** | Elegida: funciona offline y “es RAG” de cara al jurado. |

## Consecuencias

- Positivas: RNF-04/RN-01 demostrables sin red.
- Negativas / deuda: no hay persistencia del índice entre reinicios (se reconstruye al boot, < 1 s).
- Impacto: RF-16, SPEC-007.

## Reversibilidad

Fácil. El corpus es una lista de `Document`; cambiar el backend de vectores no toca el chat.
