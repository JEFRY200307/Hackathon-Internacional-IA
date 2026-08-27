# ADR-0004 — Modelo LLM: OpenAI `gpt-4o`

- Estado: `aceptada`
- Fecha: 2026-08-26
- Decisores: equipo

## Contexto

El prototipo necesita **un** modelo que, en el mismo turno: hable español clínico-cauto, llame tools (datos, RAG, modelo remoto) y emita JSON válido de UCP y de gráficos. Hay 12 h, cupo limitado y la demo no puede depender de un único proveedor sin fallback.

Criterios: tool calling fiable, JSON estructurado, latencia, español, coste, facilidad de conseguir API key en hackathon.

## Decisión

**Modelo principal: `gpt-4o` (OpenAI).** Configurable con `LLM_MODEL`. Fallback de cupo: `gpt-4o-mini`. Si no hay `OPENAI_API_KEY`, `MockLLM` (plantillas + las mismas tools reales).

Embeddings RAG: `text-embedding-3-small` cuando hay key; si no, TF-IDF.

## Alternativas consideradas

| Opción | Por qué no (o por qué sí) |
| --- | --- |
| **gpt-4o** | Elegida: mejor equilibrio tool calling + JSON de dashboards + español + ecosistema. Un `LLM_MODEL` cambia el string. |
| gpt-4o-mini | Más barato y rápido; peor en UCP complejo. Queda como fallback de cupo, no como default. |
| Claude Sonnet 4 / 4.5 | Excelente siguiendo esquemas JSON (UCP). Segunda opción si el equipo tiene `ANTHROPIC_API_KEY`; el cliente está preparado para añadir provider, no es el default para no forzar dos SDKs el día 1. |
| Gemini 2.5 Flash | Cupo generoso; tool calling menos predecible para JSON de UI. Candidato si OpenAI no está disponible. |
| Llama / Qwen vía Groq | Baja latencia, cero vendor OpenAI. Calidad de JSON UCP y de “no diagnostiques” menos fiable en 12 h. |
| Local (Ollama) | Demo portátil, pero GPU/RAM y calidad desigual en laptops del equipo. |

## Consecuencias

- Positivas: una key, function calling maduro, fácil de explicar al jurado.
- Negativas / deuda: coste y dependencia de red (mitigado por MockLLM + tools locales).
- Impacto: RF-10, RNF-07, R-03.

## Reversibilidad

Fácil. `LLM_PROVIDER` / `LLM_MODEL` en `.env`. El contrato de tools no cambia.
