# SPEC-003 — Dashboards dinámicos con RISA UI Protocol

- Estado: `aceptada`
- Área: 1 Salud
- Relaciona: RF-12, RNF-08, RN-01, RN-06
- Autor: equipo
- Fecha: 2026-08-27

## Problema

Un dashboard fijo no responde a preguntas como “muéstrame saturación y LAB_A del caso más urgente”. El agente debe componer una pantalla distinta con un catálogo cerrado, sin inventar valores ni generar código ejecutable.

## Flujo

1. El agente llama `get_dashboard_context` para descubrir métricas, variables, niveles y casos disponibles.
2. Consulta alertas, series o evidencia necesarias.
3. Llama una vez a `emit_risa_ui` con bindings declarativos.
4. El backend valida, descarta widgets inválidos e hidrata cálculos y datos.
5. React renderiza el documento y reenvía únicamente acciones catalogadas.
6. Si la composición falla, el backend entrega la plantilla segura del turno.

## Contrato v1.0

```json
{
  "protocol": "risa-ui",
  "version": "1.0",
  "title": "Casos críticos",
  "subtitle": "RISA Data V1.0",
  "widgets": [
    {
      "id": "critical-count",
      "type": "kpi",
      "title": "Alertas críticas",
      "metric": "alert_count",
      "filters": { "level": "CRITICO" }
    },
    {
      "id": "critical-list",
      "type": "alert_list",
      "title": "Revisión inmediata",
      "level": "CRITICO",
      "limit": 10,
      "on_select": { "action": "select_alert" }
    }
  ]
}
```

### Widgets y bindings

- `kpi`: `metric`, `filters.level`, `hint`.
- `chart`: `chart.patient_id`, `chart.variables` (1–4), `chart.kind`.
- `table`: `source`, `columns`, `filters.level`, `limit` (1–100), `on_select`.
- `alert_list`: `level`, `limit` (1–100), `on_select`.
- `evidence`: exactamente una referencia útil mediante `alert_id` o `patient_id`.
- `markdown`: texto plano informativo; no HTML.

Métricas permitidas: `alert_count`, `patient_count`, `discarded_count`, `average_risk_score`, `top_priority_patient`.

Variables permitidas: `heart_rate`, `spo2`, `resp_rate`, `sbp`, `dbp`, `temp`, `LAB_A`, `LAB_B`, `LAB_C`, `LAB_D`.

## Seguridad y autoridad de datos

- El agente nunca envía `value`, `rows`, `items`, `alert` ni `plotly`.
- Los cálculos y filtros se ejecutan en backend sobre el estado de RISA.
- Máximo 12 widgets, IDs únicos y textos acotados.
- Solo se ejecuta la acción `select_alert`; nunca código arbitrario.
- Un widget inválido no impide renderizar los widgets válidos restantes.

## Criterios de aceptación

- [ ] “Dashboard del turno” produce KPI, lista y evidencia hidratados.
- [ ] Peticiones por nivel o paciente generan composiciones distintas.
- [ ] Los KPI coinciden con el dataset y no aceptan valores del LLM.
- [ ] Filtros y límites se aplican en backend.
- [ ] Variables y widgets desconocidos no se ejecutan.
- [ ] Seleccionar una alerta abre su detalle en el canvas.
- [ ] Sin API key funciona una composición determinista mediante MockLLM.

## Prompts de demo

### Turno

> Crea un dashboard del turno con KPIs por prioridad, los diez casos principales y evidencia del primero. Consulta el contexto y usa RISA UI Protocol; no inventes valores.

### Paciente

> Crea un dashboard para PAT-0001 con su evidencia y un gráfico de heart_rate y spo2. Usa solo variables disponibles y explica si falta alguna serie.

### Comparación

> Crea un dashboard comparando alertas CRITICO y ALTO con KPI, listas filtradas y una tabla de id, paciente, nivel, patrón y score.
