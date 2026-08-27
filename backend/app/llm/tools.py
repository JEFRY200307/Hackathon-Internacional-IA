from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.adapters.pretrained import predict_risk
from app.charts import build_chart, hydrate_risa_ui, turno_risa_ui
from app.risa_ui.protocol import (
    ALERT_LEVELS,
    RISA_UI_METRICS,
    RISA_UI_VARIABLES,
    EmitRisaUiArgs,
    emit_risa_ui_schema,
)

if TYPE_CHECKING:
    from app.state import AppState

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_context",
            "description": "Describe los datos, métricas, variables y filtros permitidos antes de componer un dashboard.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_alerts",
            "description": "Lista alertas priorizadas. Filtra por nivel opcional.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["CRITICO", "ALTO", "MEDIO", "BAJO", "DESCARTADO"],
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_alert",
            "description": "Detalle de una alerta por id (A-001) o patient_id.",
            "parameters": {
                "type": "object",
                "properties": {"alert_id": {"type": "string"}, "patient_id": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_series",
            "description": "Devuelve resumen estadístico de una variable de un paciente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "variable": {"type": "string"},
                },
                "required": ["patient_id", "variable"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_evidence",
            "description": "RAG: recupera fragmentos de evidencia, reglas y diccionario.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "k": {"type": "integer"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_pretrained_model",
            "description": "Consulta el modelo preentrenado (HTTP) o el fallback local.",
            "parameters": {
                "type": "object",
                "properties": {"patient_id": {"type": "string"}},
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "emit_risa_ui",
            "description": (
                "Emite un dashboard RISA UI Protocol v1.0. La interfaz es declarativa: "
                "el backend calcula e hidrata todos los datos."
            ),
            "parameters": emit_risa_ui_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "emit_chart",
            "description": "Construye un gráfico interactivo Plotly con datos reales.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "variables": {"type": "array", "items": {"type": "string"}},
                    "kind": {"type": "string", "enum": ["line", "bar", "scatter"]},
                    "title": {"type": "string"},
                },
                "required": ["variables"],
            },
        },
    },
]


async def run_tool(name: str, args: dict[str, Any], app: AppState) -> Any:
    if name == "get_dashboard_context":
        counts = {level: sum(1 for alert in app.alerts if alert["level"] == level) for level in ALERT_LEVELS}
        return {
            "protocol": "risa-ui",
            "version": "1.0",
            "dataset": app.dataset.origin,
            "patient_count": int(len(app.dataset.patients)),
            "allowed_widgets": ["kpi", "chart", "table", "alert_list", "evidence", "markdown"],
            "allowed_metrics": sorted(RISA_UI_METRICS),
            "allowed_variables": sorted(RISA_UI_VARIABLES),
            "allowed_levels": list(ALERT_LEVELS),
            "counts": counts,
            "top_alerts": [
                {
                    "id": alert["id"],
                    "patient_id": alert["patient_id"],
                    "level": alert["level"],
                    "pattern": alert["pattern"],
                    "score": alert["score"],
                }
                for alert in app.alerts[:10]
            ],
        }
    if name == "list_alerts":
        level = args.get("level")
        items = app.alerts if not level else [a for a in app.alerts if a["level"] == level]
        return [
            {
                "id": a["id"],
                "patient_id": a["patient_id"],
                "level": a["level"],
                "pattern": a["pattern"],
                "title": a["title"],
                "score": a["score"],
            }
            for a in items
        ]
    if name == "get_alert":
        if args.get("alert_id"):
            found = app.alert_by_id(args["alert_id"])
            return found or {"error": "alerta no encontrada"}
        pid = args.get("patient_id")
        found_list = app.alerts_for_patient(pid) if pid else []
        return found_list[0] if found_list else {"error": "sin alerta para ese paciente"}
    if name == "query_series":
        from app.charts import _series

        series = _series(app.dataset, args["patient_id"], args["variable"])
        if series is None or series.empty:
            return {"error": "serie vacía o variable desconocida", "variable": args["variable"]}
        return {
            "patient_id": args["patient_id"],
            "variable": args["variable"],
            "n": int(len(series)),
            "first": round(float(series.iloc[0]), 3),
            "last": round(float(series.iloc[-1]), 3),
            "min": round(float(series.min()), 3),
            "max": round(float(series.max()), 3),
            "mean": round(float(series.mean()), 3),
            "source": app.dataset.origin,
        }
    if name == "retrieve_evidence":
        return app.rag.search(args.get("query") or "", k=int(args.get("k") or 4))
    if name == "call_pretrained_model":
        pid = args["patient_id"]
        alert = next((a for a in app.alerts if a["patient_id"] == pid), None)
        features = alert["features"] if alert else {}
        return await predict_risk(pid, features)
    if name == "emit_risa_ui":
        parsed = EmitRisaUiArgs.model_validate(args)
        if parsed.use_turno_template or not parsed.widgets:
            return {"risa_ui": turno_risa_ui(app)}
        doc = {
            "title": parsed.title,
            "subtitle": parsed.subtitle,
            "widgets": [widget.model_dump(exclude_none=True) for widget in parsed.widgets],
        }
        return {"risa_ui": hydrate_risa_ui(doc, app)}
    if name == "emit_chart":
        return {
            "chart": build_chart(
                app.dataset,
                kind=args.get("kind") or "line",
                patient_id=args.get("patient_id"),
                variables=args.get("variables") or ["heart_rate"],
                title=args.get("title"),
            )
        }
    return {"error": f"tool desconocida: {name}"}
