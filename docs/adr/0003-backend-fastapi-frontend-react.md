# ADR-0003 — Separar backend FastAPI y frontend React (en lugar de Streamlit)

- Estado: `aceptada`
- Fecha: 2026-08-26
- Decisores: equipo

## Contexto

`ADR-0002` recortó el agente conversacional y asumió un dashboard Streamlit fijo. El equipo decidió **subir a MVP** el chat que conversa con el dataset, compone dashboards (UCP) y gráficos interactivos. Streamlit no encaja: el LLM tiene que emitir UI estructurada a un canvas, no a un script lineal.

## Decisión

Dos procesos:

- **Backend:** FastAPI + pandas (ingesta, alertas, RAG, adaptador del modelo, loop de tools del LLM).
- **Frontend:** React + Vite + Plotly (chat, canvas UCP, gráficos, cola de alertas).

El pipeline de detección sigue siendo un módulo Python importable, no un microservicio extra.

## Alternativas consideradas

| Opción | Por qué no (o por qué sí) |
| --- | --- |
| Streamlit único | Elegida antes para 12 h con dashboard fijo. No renderiza un protocolo de widgets del LLM con control. |
| Next.js fullstack | Un solo repo TS; el scoring y pandas viven mejor en Python. |
| **FastAPI + React** | Elegida: Python para datos/ML, UI rica para UCP/Plotly, contratos HTTP explícitos. |

## Consecuencias

- Positivas: el chat y el canvas pueden evolucionar sin reescribir el scoring; el modelo remoto es un HTTP más.
- Negativas / deuda: dos arranques (`uvicorn` + `npm run dev`); CORS y `.env` duplicado (`VITE_API_URL`).
- Impacto: habilita RF-10…RF-16; enmienda el recorte “sin chat NL” de ADR-0002 (el pipeline sigue único; se añade una capa conversacional).

## Reversibilidad

Media. El backend puede servir un HTML mínimo si el frontend se cae. Volver a Streamlit implicaría tirar el canvas UCP.
