# Guía — Uso de dashboards con RISA UI Protocol

Esta guía explica cómo pedir, probar y extender los dashboards generados por el agente. El nombre anterior del prototipo era **dashboard UCP**; desde ADR-0005 el contrato se llama **RISA UI Protocol** para no confundirlo con Google Universal Commerce Protocol.

RISA UI permite que el agente elija widgets y filtros según la pregunta. El agente no genera HTML ni calcula resultados: describe la interfaz y el backend la valida e hidrata con los datos disponibles.

## 1. Flujo general

```text
Usuario
  → chat
  → get_dashboard_context
  → tools de alertas, series o evidencia
  → emit_risa_ui
  → validación Pydantic
  → cálculos e hidratación en backend
  → RisaUiCanvas + Plotly
```

Responsabilidades:

- **Agente:** interpreta la petición y decide widgets, orden, métricas, filtros y variables.
- **Backend:** valida el contrato, calcula KPI, filtra filas, recupera evidencia y construye Plotly.
- **Frontend:** renderiza componentes conocidos y permite únicamente acciones catalogadas.

### Grounding antes de ejecutar

Cada pregunta pasa por cuatro capas:

1. **Planner:** convierte lenguaje libre en `DashboardQueryPlan`; no produce datos ni razonamiento visible.
2. **Resolver:** aplica filtros catalogados y crea un `ResolvedScope` con los pacientes reales incluidos.
3. **Composer:** genera widgets RISA UI que referencian el `scope_id`; no puede ampliar la cohorte.
4. **Verifier:** comprueba citas, filas, series, evidencias y menciones `PAT-*` antes de responder.

El plan admite detalle, cohorte, comparación, tendencia, distribución y calidad. Los filtros permitidos incluyen IDs, nivel, prioridad, edad, sexo, región, programa de atención y rangos de score/riesgo. No se aceptan SQL ni expresiones ejecutables.

Ejemplos:

```text
Crea un dashboard de pacientes mayores de 60 años, URBAN,
con risk_score entre 0.6 y 1.0.
```

```text
Compara pacientes CRITICO y ALTO agrupando por care_program.
```

```text
Muestra la tendencia de heart_rate y spo2 para PAT-0724.
```

La respuesta incluye `query_plan`, `resolved_scope` y `warnings`. Las fuentes de paciente/alerta deben pertenecer al alcance; reglas y variables pueden ser globales.

## 2. Ejecutar el sistema

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

Sin `OPENAI_API_KEY`, el chat usa `MockLLM`: mantiene las mismas herramientas y datos, pero reconoce un conjunto acotado de intenciones. Con una clave configurada, el LLM puede crear composiciones más variadas respetando el mismo esquema.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Abrir `http://localhost:5173`. Al iniciar, el canvas carga `GET /api/dashboards/turno`; cada respuesta de `POST /api/chat` que contenga `message.risa_ui` reemplaza el dashboard visible.

## 3. Pedir un dashboard desde el chat

Una solicitud útil debe indicar:

1. Objetivo o pregunta que debe responder el panel.
2. Población, nivel o paciente.
3. Métricas y variables relevantes.
4. Widgets deseados, si existe una preferencia.
5. Cómo actuar si faltan datos.

Prompt recomendado:

```text
Crea un dashboard interactivo del turno actual con RISA UI Protocol.

Primero consulta get_dashboard_context y las herramientas necesarias.
Incluye:
- KPI de alertas CRITICO, ALTO y DESCARTADO;
- lista de los 10 casos de mayor prioridad;
- evidencia del caso más prioritario;
- gráfico temporal de las variables que originaron esa alerta;
- tabla con id, patient_id, level, pattern y score.

Usa solamente pacientes, variables y valores obtenidos de las herramientas.
No inventes cálculos, no generes HTML y no envíes value, rows, items,
alert ni plotly. Si falta una serie, indícalo en un widget markdown.
Llama emit_risa_ui una sola vez y luego resume las fuentes y filtros usados.
```

Otros ejemplos:

```text
Crea un dashboard para PAT-0001 con evidencia y un gráfico de heart_rate
y spo2. Usa solo variables disponibles y explica cualquier dato faltante.
```

```text
Compara las alertas CRITICO y ALTO. Muestra un KPI y una lista por nivel,
más una tabla con id, patient_id, level, pattern y score.
```

```text
Construye un panel de alertas DESCARTADO que muestre cuántas existen,
la lista filtrada y la evidencia del primer caso. Deben seguir visibles
los motivos del descarte.
```

## 4. Contrato que emite el agente

El agente llama `emit_risa_ui` con un documento declarativo. `protocol`, `version` y los datos hidratados se incorporan en el backend.

```json
{
  "title": "Alertas críticas",
  "subtitle": "Prioridad de revisión",
  "widgets": [
    {
      "id": "critical-count",
      "type": "kpi",
      "title": "Casos críticos",
      "metric": "alert_count",
      "filters": { "level": "CRITICO" }
    },
    {
      "id": "critical-list",
      "type": "alert_list",
      "title": "Revisar ahora",
      "level": "CRITICO",
      "limit": 10,
      "on_select": { "action": "select_alert" }
    },
    {
      "id": "patient-series",
      "type": "chart",
      "title": "Evolución del caso prioritario",
      "chart": {
        "patient_id": "PAT-0001",
        "variables": ["heart_rate", "spo2"],
        "kind": "line"
      }
    }
  ]
}
```

La respuesta hidratada usa este sobre:

```json
{
  "protocol": "risa-ui",
  "version": "1.0",
  "title": "Alertas críticas",
  "subtitle": "Prioridad de revisión",
  "widgets": []
}
```

## 5. Catálogo de widgets

### `kpi`

Muestra un valor calculado por el backend.

Métricas disponibles:

- `alert_count`: total de alertas, opcionalmente filtrado por `filters.level`.
- `patient_count`: pacientes disponibles.
- `discarded_count`: alertas descartadas con motivo.
- `average_risk_score`: promedio de `score`, opcionalmente por nivel.
- `top_priority_patient`: primer paciente de la cola filtrada.

El agente envía `metric`; nunca `value`.

### `alert_list`

Lista alertas priorizadas. Admite:

- `level`: `CRITICO`, `ALTO`, `MEDIO`, `BAJO` o `DESCARTADO`.
- `limit`: entre 1 y 100.
- `on_select.action`: únicamente `select_alert`.

Al seleccionar una alerta, el frontend abre el detalle existente.

### `chart`

Genera un gráfico Plotly `line`, `bar` o `scatter`.

Análisis disponibles:

- `patient_series`: serie de un paciente explícito.
- `cohort_timeseries`: promedio temporal dentro de una cohorte.
- `distribution`: distribución de edad o scores.
- `cohort_comparison`: conteo o promedio entre cohortes.
- `alert_breakdown`: conteo por nivel, prioridad, patrón o dimensión permitida.

Variables permitidas:

- Vitales: `heart_rate`, `spo2`, `resp_rate`, `sbp`, `dbp`, `temp`.
- Laboratorio sintético: `LAB_A`, `LAB_B`, `LAB_C`, `LAB_D`.

Las series requieren entre 1 y 4 variables. Los análisis agregados referencian `scope_id` y opcionalmente `cohort`; el backend resuelve todos los puntos.

### `table`

Fuentes disponibles:

- `alerts`: columnas `id`, `patient_id`, `level`, `pattern`, `score`, `title`, `review_status`; permite filtro `level` y `select_alert`.
- `patients`: columnas `patient_id`, `age`, `sex`; no permite filtro de nivel ni selección de alerta.

`limit` debe estar entre 1 y 100. El backend selecciona columnas, filtra y limita antes de responder.

### `evidence`

Recupera la evidencia de una alerta mediante exactamente uno de estos campos:

- `alert_id`
- `patient_id`

Si no existe una alerta asociada, el widget muestra un estado vacío y no sustituye la información.

### `markdown`

Muestra texto plano para notas, alcance o datos faltantes. React no interpreta el contenido como HTML.

## 6. Límites y reglas de seguridad

- Máximo 12 widgets por documento; el prompt recomienda entre 2 y 6 para mantener legibilidad.
- IDs de widget únicos, de hasta 64 caracteres.
- Máximo 4 variables por gráfico y 100 filas por tabla o lista.
- El catálogo no admite HTML, JavaScript, SQL, componentes React ni tipos arbitrarios.
- `value`, `rows`, `items`, `alert` y `plotly` son campos exclusivos del backend.
- Un widget desconocido, duplicado o inválido se descarta sin ejecutar su contenido.
- Si falla la composición completa, se usa el dashboard determinista del turno.
- El dashboard apoya la prioridad de revisión; no diagnostica ni prescribe.

## 7. Limitaciones actuales

- No hay grids anidados, pestañas, mapas, formularios ni componentes personalizados.
- Los KPI se agrupan primero y el resto conserva el orden del documento; el agente no controla posiciones libres.
- Solo existe la acción `select_alert`; los filtros interactivos dentro del dashboard todavía no regeneran el documento.
- El protocolo devuelve un documento completo por turno; no hay streaming ni actualizaciones parciales como en A2UI.
- Los dashboards no se persisten ni se comparten entre sesiones o instituciones.
- MockLLM usa el mismo resolver seguro, pero su interpretación determinista cubre menos expresiones lingüísticas que el Planner remoto.
- Una cohorte solo puede usar filtros catalogados; preguntas que requieran joins o dimensiones no declaradas deben ampliar primero el schema.
- `LAB_A`–`LAB_D` son marcadores sintéticos sin significado clínico real.
- Anomaly/Pattern se evalúan contra etiqueta débil; sus scores son apoyo secundario y no precisión clínica.
- No existe autenticación ni autorización multiinstitucional en el alcance del prototipo.

## 8. Probar la API sin el frontend

Dashboard predeterminado:

```powershell
Invoke-RestMethod http://localhost:8000/api/dashboards/turno
```

Dashboard mediante chat:

```powershell
$body = @{
  messages = @(
    @{
      role = "user"
      content = "Crea un dashboard de alertas críticas con RISA UI"
    }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/chat `
  -ContentType "application/json" `
  -Body $body
```

Revisar:

- `message.risa_ui.protocol` debe ser `risa-ui`.
- `message.risa_ui.widgets` debe contener datos hidratados.
- `message.tool_trace` debe mostrar las herramientas ejecutadas.
- `message.degraded` indica si respondió MockLLM.

## 9. Agregar una métrica o widget

Para una métrica nueva:

1. Añadirla a `RISA_UI_METRICS` y al tipo `Metric` en `backend/app/risa_ui/protocol.py`.
2. Calcularla en `_kpi_value` dentro de `backend/app/charts.py`.
3. Documentarla en `get_dashboard_context` y en esta guía.
4. Agregar pruebas que demuestren que el agente no puede reemplazar su valor.

Para un widget nuevo:

1. Crear su modelo Pydantic y sumarlo a `RisaUiWidget`.
2. Añadir hidratación autoritativa en `hydrate_risa_ui`.
3. Incorporar el tipo discriminado en `frontend/src/types.ts`.
4. Renderizarlo explícitamente en `RisaUiCanvas.tsx`.
5. Definir acciones cerradas, límites y estados vacíos.
6. Agregar pruebas backend y verificar `npm run build`.

No basta con agregar el componente React: todo widget debe existir también en esquema, hidratador, tools, tipos y documentación.

## 10. Resolución de problemas

- **No aparece un dashboard:** confirmar que el prompt pide explícitamente un dashboard y revisar `message.tool_trace`.
- **Aparecen menos widgets:** uno puede haber sido descartado por tipo, ID, binding o columna inválidos.
- **Un gráfico dice “Sin datos”:** verificar `patient_id`, variables permitidas y el campo `missing` de Plotly.
- **El KPI muestra `—`:** no existen alertas para el filtro o no hay datos para calcular la métrica.
- **Siempre aparece el panel del turno:** la composición solicitada fue inválida o MockLLM no reconoció suficiente contexto.
- **El backend no inicia:** instalar `backend/requirements.txt` y comprobar que RISA Data V1.0 esté disponible.

La especificación formal está en [`SPEC-003`](../spec/003-dashboard-risa-ui.md) y las decisiones de arquitectura en [`ADR-0005`](../adr/0005-risa-ui-protocol.md).
