# SPEC-003 — Chat que genera dashboards vía UCP (UI Composition Protocol)

- Estado: `aceptada`
- Área: 1 Salud
- Relaciona: RF-12, RNF-08, RN-01, RN-06
- Autor: equipo
- Fecha: 2026-08-26

## Problema

Un dashboard fijo no responde a “muéstrame saturación y creatinina del caso más urgente”. El LLM debe componer una pantalla a partir de un catálogo cerrado de widgets, no inventar HTML.

## Actor y disparador

El mismo actor del chat. Dispara con una consigna de composición (“arma un dashboard del turno”, “KPIs + ranking + el caso P001”).

## Comportamiento esperado

1. El LLM (o el fallback determinista) llama a la herramienta `emit_ucp` con un documento UCP v1.0 válido (ADR-0005).
2. El backend valida el documento contra el catálogo: `kpi`, `chart`, `table`, `alert_list`, `evidence`, `markdown`. Widgets desconocidos se descartan, no se ejecutan.
3. Los widgets de datos se hidratan en el servidor (series, ranking, evidencia) para que el cliente no consulte SQL.
4. El frontend pinta el documento en el lienzo de dashboard (y un resumen en el hilo del chat).
5. **Resultado observable:** aparece un tablero con ≥2 widgets distintos alimentados por el dataset, no un JSON crudo.

## Entradas

- Intención de dashboard en el mensaje.
- Catálogo UCP v1.0 y datos ya alineados.

## Salidas

- Documento `{ protocol: "ucp", version: "1.0", title, widgets[] }` hidratado.
- Render nativo en React (KPIs, lista de alertas, charts Plotly, tablas).

## No cubierto

- Universal Commerce Protocol de Google (homónimo; no aplica a salud).
- A2UI completo, HTML/JS arbitrario generado por el modelo.
- Dashboards persistidos por institución (multi-tenant).

## Criterios de aceptación

- [ ] La consigna “dashboard del turno” produce un UCP con al menos un `kpi` y un `alert_list`.
- [ ] Un widget con `type` no catalogado no se renderiza y no rompe el resto.
- [ ] Los números de los KPI salen del dataset/alertas, no los inventa el modelo en texto suelto.

## Riesgos y fallback

- JSON inválido del LLM: el backend responde un UCP plantilla `turno-actual` construido en código.
- Confusión de sigla UCP (commerce vs UI): ADR-0005 deja el alcance explícito.
