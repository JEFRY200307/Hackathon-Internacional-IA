# ADR-0005 — UCP = UI Composition Protocol (catálogo cerrado), no Universal Commerce Protocol

- Estado: `aceptada`
- Fecha: 2026-08-26
- Decisores: equipo

## Contexto

El chat debe “crear dashboards”. Si el LLM emite HTML/JS, es un riesgo de seguridad y de demo. En 2026 existen A2UI (Google) para UI generada y **UCP** como *Universal Commerce Protocol* (comercio, no salud). El equipo pidió dashboards “con UCP”: interpretamos la necesidad de un **contrato de composición de UI**, no el protocolo de checkout de Google.

## Decisión

Definir **UCP v1.0 (UI Composition Protocol)** propio del prototipo:

- Documento JSON `{ protocol: "ucp", version: "1.0", title, widgets[] }`.
- Catálogo: `kpi` | `chart` | `table` | `alert_list` | `evidence` | `markdown`.
- El servidor valida e hidrata; el cliente solo mapea tipo → componente React.
- Widgets desconocidos se ignoran.

No se implementa A2UI completo ni el UCP de comercio.

## Alternativas consideradas

| Opción | Por qué no (o por qué sí) |
| --- | --- |
| HTML generado por el LLM | XSS, layout roto, indemostrable con seguridad. |
| A2UI completo | Exceso de protocolo para 12 h (adjacency list, streaming de componentes). |
| MCP solo (tools sin UI spec) | Sirve para datos; no describe el tablero. MCP-style tools viven en el backend; UCP es la capa de *render*. |
| **UCP v1.0 de catálogo cerrado** | Elegida: una página de schema, validable, reversible. |
| Universal Commerce Protocol (Google) | Dominio comercio; no aplica. |

## Consecuencias

- Positivas: dashboards reproducibles y auditables; el modelo no “inventa” controles.
- Negativas / deuda: catálogo chico (no hay mapas ni grids anidados profundos).
- Impacto: RF-12, SPEC-003.

## Reversibilidad

Fácil. Ampliar el catálogo es agregar un tipo y un componente. Migrar a A2UI más adelante es un traductor de widgets.
