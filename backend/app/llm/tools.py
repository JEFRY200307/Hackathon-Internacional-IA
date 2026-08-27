from __future__ import annotations

from typing import Any

from app.adapters.pretrained import predict_risk
from app.charts import build_chart, turno_dashboard
from app.state import AppState
from app.ucp.protocol import validate_ucp

TOOLS = [
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
            "name": "emit_ucp",
            "description": "Emite un dashboard UCP v1.0. Si widgets está vacío, se usa la plantilla del turno.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "widgets": {"type": "array", "items": {"type": "object"}},
                    "use_turno_template": {"type": "boolean"},
                },
            },
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
    if name == "emit_ucp":
        if args.get("use_turno_template") or not args.get("widgets"):
            return {"ucp": turno_dashboard(app)}
        doc = validate_ucp({"title": args.get("title"), "widgets": args.get("widgets")})
        from app.charts import hydrate_ucp

        return {"ucp": hydrate_ucp(doc, app)}
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
