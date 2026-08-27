from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from app.risa_ui.protocol import template_turno, validate_risa_ui

if TYPE_CHECKING:
    from app.data.loader import Dataset
    from app.state import AppState

VITAL_KEYS = {"heart_rate", "spo2", "resp_rate", "sbp", "dbp", "temp"}
LAB_KEYS = {"LAB_A", "LAB_B", "LAB_C", "LAB_D"}


def hydrate_risa_ui(doc: dict[str, Any], app: AppState) -> dict[str, Any]:
    clean = validate_risa_ui(doc)
    hydrated = []
    for widget in clean["widgets"]:
        wtype = widget["type"]
        if wtype == "alert_list":
            limit = int(widget.get("limit") or 8)
            level = widget.get("level")
            alerts = app.alerts if not level else [a for a in app.alerts if a["level"] == level]
            widget = {
                **widget,
                "items": [
                    {
                        "id": a["id"],
                        "patient_id": a["patient_id"],
                        "level": a["level"],
                        "pattern": a["pattern"],
                        "title": a["title"],
                        "score": a["score"],
                    }
                    for a in alerts[:limit]
                ],
                "empty_message": "No hay alertas para este filtro." if not alerts else None,
                "provenance": {"source": app.dataset.origin, "count": len(alerts)},
            }
        elif wtype == "evidence":
            alert = app.alert_by_id(widget.get("alert_id") or "")
            if not alert and widget.get("patient_id"):
                patient_alerts = app.alerts_for_patient(widget["patient_id"])
                alert = patient_alerts[0] if patient_alerts else None
            widget = {
                **widget,
                "alert": alert,
                "empty_message": "No se encontró evidencia para la referencia solicitada." if not alert else None,
                "provenance": {"source": app.dataset.origin},
            }
        elif wtype == "kpi":
            value, detail = _kpi_value(app, widget)
            widget = {
                **widget,
                "value": value,
                "detail": detail,
                "provenance": {"source": app.dataset.origin, "metric": widget["metric"]},
            }
        elif wtype == "chart":
            spec = widget.get("chart") or {}
            widget = {
                **widget,
                "plotly": build_chart(
                    app.dataset,
                    kind=spec.get("kind") or "line",
                    patient_id=spec.get("patient_id"),
                    variables=spec.get("variables") or ["heart_rate"],
                    title=widget.get("title") or spec.get("title"),
                ),
            }
        elif wtype == "table":
            rows = _table_rows(app, widget)
            widget = {
                **widget,
                "rows": rows,
                "empty_message": "No hay filas para los filtros solicitados." if not rows else None,
                "provenance": {"source": app.dataset.origin, "count": len(rows)},
            }
        hydrated.append({key: value for key, value in widget.items() if value is not None})
    clean["widgets"] = hydrated
    return clean


def turno_risa_ui(app: AppState) -> dict[str, Any]:
    return hydrate_risa_ui(template_turno(app.alerts, app.dataset.origin), app)


def _table_rows(app: AppState, widget: dict) -> list[dict]:
    source = widget.get("source") or "alerts"
    limit = int(widget.get("limit") or 20)
    columns = widget.get("columns")
    if source == "patients":
        rows = app.dataset.patients.to_dict(orient="records")
    else:
        level = (widget.get("filters") or {}).get("level")
        alerts = app.alerts if not level else [a for a in app.alerts if a["level"] == level]
        rows = [
            {
                "id": a["id"],
                "patient_id": a["patient_id"],
                "level": a["level"],
                "pattern": a["pattern"],
                "score": a["score"],
                "title": a.get("title"),
                "review_status": a.get("review_status"),
            }
            for a in alerts
        ]
    rows = rows[:limit]
    if columns:
        rows = [{column: row.get(column) for column in columns if column in row} for row in rows]
    return rows


def _kpi_value(app: AppState, widget: dict[str, Any]) -> tuple[str, str]:
    metric = widget["metric"]
    level = (widget.get("filters") or {}).get("level")
    alerts = app.alerts if not level else [a for a in app.alerts if a["level"] == level]
    if metric == "alert_count":
        detail = f"Alertas nivel {level}" if level else "Todas las alertas"
        return str(len(alerts)), detail
    if metric == "patient_count":
        return str(len(app.dataset.patients)), "Pacientes en el dataset"
    if metric == "discarded_count":
        return str(sum(1 for a in app.alerts if a["level"] == "DESCARTADO")), "Descartados con motivo visible"
    if metric == "average_risk_score":
        if not alerts:
            return "—", "Sin alertas para calcular el promedio"
        average = sum(float(a.get("score") or 0) for a in alerts) / len(alerts)
        return f"{average:.3f}", f"Promedio de {len(alerts)} alertas"
    if metric == "top_priority_patient":
        top = alerts[0] if alerts else None
        return (str(top["patient_id"]), f"{top['level']} · {top['pattern']}") if top else ("—", "Sin alertas")
    return "—", "Métrica no disponible"


def build_chart(
    dataset: Dataset,
    kind: str = "line",
    patient_id: str | None = None,
    variables: list[str] | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    variables = variables or ["heart_rate"]
    kind = kind if kind in {"line", "bar", "scatter"} else "line"
    if not patient_id:
        patient_id = dataset.patients["patient_id"].iloc[0]
    if patient_id not in set(dataset.patients["patient_id"]):
        return {
            "error": f"Paciente {patient_id} no existe en el dataset {dataset.origin}.",
            "data": [],
            "layout": {"title": "Sin datos"},
        }

    traces = []
    provenance = []
    missing = []
    for var in variables:
        series = _series(dataset, patient_id, var)
        if series is None or series.empty:
            missing.append(var)
            continue
        trace: dict = {
            "type": "bar" if kind == "bar" else "scatter",
            "name": var,
            "x": [t.isoformat() for t in series.index],
            "y": [round(float(v), 3) for v in series.values],
        }
        if kind != "bar":
            trace["mode"] = "lines+markers"
        traces.append(trace)
        provenance.append(
            {
                "variable": var,
                "source": "laboratory" if var in LAB_KEYS else "vital_signs",
                "n": int(len(series)),
                "patient_id": patient_id,
            }
        )
    layout = {
        "title": title or f"{patient_id}: {', '.join(variables)}",
        "xaxis": {"title": "tiempo"},
        "yaxis": {"title": "valor"},
        "margin": {"t": 48, "l": 48, "r": 16, "b": 48},
        "legend": {"orientation": "h"},
        "hovermode": "x unified",
    }
    if missing and not traces:
        return {
            "error": f"No hay datos de {', '.join(missing)} para {patient_id}.",
            "missing": missing,
            "data": [],
            "layout": layout,
            "provenance": provenance,
        }
    return {
        "kind": kind,
        "patient_id": patient_id,
        "data": traces,
        "layout": layout,
        "provenance": provenance,
        "missing": missing,
        "origin": dataset.origin,
    }


def _series(dataset: Dataset, patient_id: str, var: str) -> pd.Series | None:
    if var in VITAL_KEYS:
        df = dataset.vitals_for(patient_id)
        if df.empty or var not in df.columns:
            return None
        return df.set_index("timestamp")[var].astype(float)
    if var in LAB_KEYS:
        df = dataset.labs_for(patient_id)
        if df.empty:
            return None
        sub = df[df["analyte"] == var]
        if sub.empty:
            return None
        return sub.set_index("timestamp")["value"].astype(float)
    return None
