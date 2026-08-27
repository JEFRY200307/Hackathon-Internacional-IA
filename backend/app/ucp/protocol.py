from __future__ import annotations

from typing import Any

UCP_WIDGET_TYPES = {"kpi", "chart", "table", "alert_list", "evidence", "markdown"}


def validate_ucp(doc: dict[str, Any]) -> dict[str, Any]:
    widgets = []
    for raw in doc.get("widgets") or []:
        wtype = raw.get("type")
        if wtype not in UCP_WIDGET_TYPES:
            continue
        widgets.append(raw)
    return {
        "protocol": "ucp",
        "version": "1.0",
        "title": doc.get("title") or "Dashboard RISA Signal",
        "subtitle": doc.get("subtitle") or "",
        "widgets": widgets,
    }


def template_turno(alerts: list[dict], origin: str) -> dict[str, Any]:
    active = [a for a in alerts if a["level"] != "DESCARTADO"]
    discarded = [a for a in alerts if a["level"] == "DESCARTADO"]
    top = active[0] if active else alerts[0]
    crit = sum(1 for a in alerts if a["level"] == "CRITICO")
    alto = sum(1 for a in alerts if a["level"] == "ALTO")
    return validate_ucp(
        {
            "title": "Turno actual — RISA Signal",
            "subtitle": f"Dataset {origin}. Apoyo a la revisión, no diagnóstico.",
            "widgets": [
                {"type": "kpi", "id": "kpi-crit", "title": "Críticos", "value": str(crit), "hint": "Revisar ahora"},
                {"type": "kpi", "id": "kpi-alto", "title": "Altos", "value": str(alto), "hint": "Prioridad alta"},
                {
                    "type": "kpi",
                    "id": "kpi-desc",
                    "title": "Descartados",
                    "value": str(len(discarded)),
                    "hint": "Visibles con motivo (RN-02)",
                },
                {
                    "type": "kpi",
                    "id": "kpi-top",
                    "title": "Caso a revisar primero",
                    "value": top["patient_id"],
                    "hint": f"{top['level']} · {top['pattern']}",
                },
                {"type": "alert_list", "id": "alerts", "title": "Cola priorizada", "limit": 8},
                {
                    "type": "evidence",
                    "id": "ev-top",
                    "title": f"Evidencia {top['id']}",
                    "alert_id": top["id"],
                },
                {
                    "type": "markdown",
                    "id": "note",
                    "title": "Nota",
                    "text": "Los KPIs salen del motor de alertas. El texto del chat se separa de esta evidencia.",
                },
            ],
        }
    )
