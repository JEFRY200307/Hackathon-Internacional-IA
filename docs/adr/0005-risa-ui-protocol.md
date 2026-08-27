# ADR-0005 — RISA UI Protocol para interfaces declarativas

- Estado: `aceptada`
- Fecha: 2026-08-27
- Decisores: equipo

## Contexto

El chat debe crear dashboards distintos según la pregunta sin permitir que el LLM ejecute HTML, JavaScript o consultas directas. Google UCP es un protocolo de comercio y no aplica al dominio; A2UI sí resuelve interfaces generadas por agentes, pero incorpora más superficie de la necesaria para este prototipo.

## Decisión

Definir **RISA UI Protocol v1.0**, un contrato propio y declarativo:

- Documento `{ protocol: "risa-ui", version: "1.0", title, subtitle, widgets[] }`.
- Catálogo cerrado: `kpi` | `chart` | `table` | `alert_list` | `evidence` | `markdown`.
- El agente decide composición y bindings, no valores finales.
- El servidor valida con un esquema estricto, calcula métricas e hidrata datos.
- El cliente mapea tipos conocidos a componentes React y acciones permitidas.
- Widgets inválidos se descartan de forma aislada y existe una plantilla determinista de fallback.

Los KPI declaran una métrica; tablas, listas y gráficos declaran fuentes y filtros. Campos como `value`, `rows`, `items`, `alert` y `plotly` solo pueden ser incorporados por el backend.

## Alternativas consideradas

| Opción | Decisión |
| --- | --- |
| HTML generado por el LLM | Rechazada por XSS, falta de control y layouts frágiles. |
| A2UI | Evolución posible cuando se necesiten streaming, múltiples renderizadores o interoperabilidad. |
| MCP solo | Complementario: ofrece herramientas, pero no describe la composición visual. |
| Google Universal Commerce Protocol | No aplica; estandariza comercio, checkout y órdenes. |
| RISA UI Protocol | Elegida por seguridad, alcance acotado y adaptación al dataset RISA. |

## Consecuencias

- Dashboards dinámicos, reproducibles y auditables.
- Los cálculos permanecen en backend y no dependen de afirmaciones del LLM.
- El catálogo es deliberadamente pequeño y específico.
- Una migración futura a A2UI puede implementarse mediante un adaptador desde los widgets RISA UI.

## Reversibilidad

Media. Agregar widgets requiere ampliar esquema, hidratador y renderer. El contrato declarativo permite traducirlo a A2UI sin cambiar el pipeline ni las fuentes de datos.
