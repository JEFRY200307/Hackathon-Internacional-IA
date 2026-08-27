# Guía — Estándares de API REST

Convenciones que sigue `backend/app/main.py` y que cualquier endpoint nuevo debe respetar. No es un estándar genérico copiado de internet: describe lo que este backend efectivamente hace, para que las decisiones queden explícitas en vez de implícitas en el código.

## 1. Recursos y verbos

- Todo bajo el prefijo `/api/`.
- Sustantivos en plural para colecciones: `/api/patients`, `/api/alerts`, `/api/variables`.
- `GET` no muta estado. La única mutación expuesta hoy es `POST /api/alerts/{id}/review` (marca revisión humana — HITL, RF-09), deliberadamente un verbo de acción explícito (`review`) y no un `PUT`/`PATCH` genérico, porque lo que cambia es un evento de negocio ("un profesional revisó esto"), no un reemplazo de recurso.
- Filtros por query param, no por segmento de ruta: `GET /api/alerts?level=CRITICO`, nunca `/api/alerts/CRITICO`.

## 2. Formato de respuesta

- Siempre JSON, siempre un objeto en la raíz (nunca un array suelto) — así se puede agregar metadata (`counts`, `origin`) sin romper compatibilidad. Ejemplo real (`GET /api/alerts`):

  ```json
  { "items": [...], "counts": {"CRITICO": 1, "ALTO": 5}, "origin": "RISA_DATA_V1.0" }
  ```

- Todo payload que representa datos de RISA lleva su procedencia visible: `origin` (siempre `RISA_DATA_V1.0` — no hay dataset sintético de reemplazo), o `provenance`/`missing` en `/api/charts` (qué variable se graficó, de qué fuente, cuántos puntos, cuáles no existían). Ocultar que un dato falta viola RN-05/RN-02 de `definicion.md`. Si RISA Data V1.0 no está disponible, el backend no arranca (`RisaDataNotFoundError`) en vez de servir datos inventados.

## 3. Errores

- `HTTPException` de FastAPI con el código semánticamente correcto (`404` para alerta/paciente inexistente, `422` automático de Pydantic para body inválido). No se inventan códigos de error propios dentro del body de un `200`.
- El mensaje de error es texto plano en español, pensado para mostrarse directo en la UI (`app.error` en el frontend), no un stack trace.

## 4. Validación de entrada

- Todo body de `POST` es un modelo Pydantic (`ChatRequest`, `ReviewRequest`, `ChartRequest`, `PredictRequest` en `main.py`), nunca un `dict` suelto — el esquema queda autodocumentado en `/docs` (Swagger) sin escribirlo dos veces.
- Los valores permitidos de un campo (p. ej. `ReviewRequest.status`) se restringen con `Field(pattern=...)` en el modelo, no con un `if` en el handler.

## 5. Versionado

- No hay prefijo `/v1/` porque es un prototipo de una sola versión desplegada, no un contrato con consumidores externos estables. Si esto pasara a producción, el primer cambio breaking-compatible debería introducir `/api/v2/` en paralelo, nunca mutar `/v1/` en el lugar.

## 6. CORS y configuración

- Orígenes permitidos vienen de `Settings.cors_origins` (`.env`), nunca hardcodeados ni `allow_origins=["*"]` — ver [04-seguridad-y-datos.md](04-seguridad-y-datos.md).

## 7. Endpoints actuales (referencia rápida)

| Método | Ruta | Qué hace |
| --- | --- | --- |
| GET | `/api/health` | Estado del backend, dataset activo, modo del LLM y del modelo preentrenado |
| GET | `/api/patients` | Listado de pacientes del dataset activo |
| GET | `/api/variables` | Catálogo de variables (vitales + `LAB_A..D`) |
| GET | `/api/alerts` | Cola de alertas priorizada, filtrable por `level` |
| GET | `/api/alerts/{id}` | Detalle + evidencia de una alerta |
| POST | `/api/alerts/{id}/review` | Registra revisión humana (HITL) |
| GET | `/api/rag/search` | Búsqueda semántica sobre alertas/reglas/variables |
| GET | `/api/model/status` / POST `/api/model/predict` | Estado y consulta del modelo preentrenado remoto (`ADR-0007`) |
| POST | `/api/charts` | Serie interactiva (Plotly) de una o más variables de un paciente |
| GET | `/api/dashboards/turno` | Dashboard RISA UI precompuesto del turno actual |
| POST | `/api/chat` | Turno de conversación con el LLM (o MockLLM) + tools |
| GET | `/api/pipeline/report` | Comprensión de datos + evaluación train/val/test del pipeline CRISP-DM |
