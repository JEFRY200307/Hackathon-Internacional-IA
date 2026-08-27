from __future__ import annotations

from typing import Any

import pandas as pd

from app.data.loader import Dataset
from app.state import AppState
from app.ucp.protocol import template_turno, validate_ucp

VITAL_KEYS = {"heart_rate", "spo2", "resp_rate", "sbp", "dbp", "temp"}
LAB_KEYS = {"LAB_A", "LAB_B", "LAB_C", "LAB_D"}


def hydrate_ucp(doc: dict[str, Any], app: AppState) -> dict[str, Any]:
    clean = validate_ucp(doc)
    hydrated = []
    for widget in clean["widgets"]:
        wtype = widget["type"]
        if wtype == "alert_list":
            limit = int(widget.get("limit") or 8)
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
                    for a in app.alerts[:limit]
                ],
            }
        elif wtype == "evidence":
            alert = app.alert_by_id(widget.get("alert_id") or "")
            if not alert and app.alerts:
                alert = app.alerts[0]
            widget = {**widget, "alert": alert}
        elif wtype == "kpi" and not widget.get("value"):
            widget = {**widget, "value": "—"}
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
            widget = {**widget, "rows": _table_rows(app, widget)}
        hydrated.append(widget)
    clean["widgets"] = hydrated
    return clean


def turno_dashboard(app: AppState) -> dict[str, Any]:
    return hydrate_ucp(template_turno(app.alerts, app.dataset.origin), app)


def _table_rows(app: AppState, widget: dict) -> list[dict]:
    if widget.get("of") == "patients":
        return app.dataset.patients.to_dict(orient="records")
    return [
        {"id": a["id"], "patient_id": a["patient_id"], "level": a["level"], "pattern": a["pattern"], "score": a["score"]}
        for a in app.alerts
    ]


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
