from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from app.risa_ui.protocol import template_turno, validate_risa_ui

if TYPE_CHECKING:
    from app.data.loader import Dataset
    from app.llm.planning import ResolvedScope
    from app.state import AppState

VITAL_KEYS = {"heart_rate", "spo2", "resp_rate", "sbp", "dbp", "temp"}
LAB_KEYS = {"LAB_A", "LAB_B", "LAB_C", "LAB_D"}


def hydrate_risa_ui(
    doc: dict[str, Any],
    app: AppState,
    scope: ResolvedScope | None = None,
) -> dict[str, Any]:
    clean = validate_risa_ui(doc)
    hydrated = []
    for widget in clean["widgets"]:
        wtype = widget["type"]
        ids = _scope_ids(scope, widget.get("cohort"))
        if wtype == "alert_list":
            limit = int(widget.get("limit") or 8)
            level = widget.get("level")
            alerts = _selected_alerts(app, ids)
            if level:
                alerts = [a for a in alerts if a["level"] == level]
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
                        "risk_score": a.get("risk_score"),
                        "priority_level": a.get("priority_level"),
                    }
                    for a in alerts[:limit]
                ],
                "empty_message": "No hay alertas para este filtro." if not alerts else None,
                "provenance": _provenance(app, scope, widget, len(alerts)),
            }
        elif wtype == "evidence":
            alert = app.alert_by_id(widget.get("alert_id") or "")
            if not alert and widget.get("patient_id"):
                patient_alerts = app.alerts_for_patient(widget["patient_id"])
                alert = patient_alerts[0] if patient_alerts else None
            if alert and ids is not None and alert["patient_id"] not in ids:
                alert = None
            widget = {
                **widget,
                "alert": alert,
                "empty_message": "No se encontró evidencia para la referencia solicitada." if not alert else None,
                "provenance": _provenance(app, scope, widget),
            }
        elif wtype == "kpi":
            value, detail = _kpi_value(app, widget, ids)
            widget = {
                **widget,
                "value": value,
                "detail": detail,
                "provenance": {
                    **_provenance(app, scope, widget),
                    "metric": widget["metric"],
                },
            }
        elif wtype == "chart":
            spec = widget.get("chart") or {}
            analysis = spec.get("analysis") or "patient_series"
            if analysis == "patient_series":
                plotly = build_chart(
                    app.dataset,
                    kind=spec.get("kind") or "line",
                    patient_id=spec.get("patient_id"),
                    variables=spec.get("variables") or ["heart_rate"],
                    title=widget.get("title") or spec.get("title"),
                    time_window_hours=spec.get("time_window_hours"),
                )
            else:
                plotly = build_scope_chart(app, scope, widget)
            widget = {
                **widget,
                "plotly": plotly,
            }
        elif wtype == "table":
            rows = _table_rows(app, widget, ids)
            widget = {
                **widget,
                "rows": rows,
                "empty_message": "No hay filas para los filtros solicitados." if not rows else None,
                "provenance": _provenance(app, scope, widget, len(rows)),
            }
        hydrated.append({key: value for key, value in widget.items() if value is not None})
    clean["widgets"] = hydrated
    return clean


def turno_risa_ui(app: AppState) -> dict[str, Any]:
    return hydrate_risa_ui(template_turno(app.alerts, app.dataset.origin), app)


def _scope_ids(scope: ResolvedScope | None, cohort: str | None = None) -> set[str] | None:
    return scope.cohort_ids(cohort) if scope else None


def _selected_alerts(app: AppState, ids: set[str] | None) -> list[dict]:
    return app.alerts if ids is None else [alert for alert in app.alerts if alert["patient_id"] in ids]


def _provenance(
    app: AppState,
    scope: ResolvedScope | None,
    widget: dict,
    count: int | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {"source": app.dataset.origin}
    if count is not None:
        value["count"] = count
    if scope:
        value["scope_id"] = scope.scope_id
        value["cohort"] = widget.get("cohort")
    return value


def _table_rows(app: AppState, widget: dict, ids: set[str] | None = None) -> list[dict]:
    source = widget.get("source") or "alerts"
    limit = int(widget.get("limit") or 20)
    columns = widget.get("columns")
    if source == "patients":
        frame = app.dataset.patients
        if ids is not None:
            frame = frame[frame["patient_id"].isin(ids)]
        rows = frame.to_dict(orient="records")
    else:
        level = (widget.get("filters") or {}).get("level")
        alerts = _selected_alerts(app, ids)
        if level:
            alerts = [a for a in alerts if a["level"] == level]
        rows = [
            {
                "id": a["id"],
                "patient_id": a["patient_id"],
                "level": a["level"],
                "pattern": a["pattern"],
                "score": a["score"],
                "title": a.get("title"),
                "review_status": a.get("review_status"),
                "risk_score": a.get("risk_score"),
                "priority_level": a.get("priority_level"),
                "anomaly_score": a.get("anomaly_score"),
                "pattern_score": a.get("pattern_score"),
            }
            for a in alerts
        ]
    rows = rows[:limit]
    if columns:
        rows = [{column: row.get(column) for column in columns if column in row} for row in rows]
    return rows


def _kpi_value(
    app: AppState,
    widget: dict[str, Any],
    ids: set[str] | None = None,
) -> tuple[str, str]:
    metric = widget["metric"]
    level = (widget.get("filters") or {}).get("level")
    alerts = _selected_alerts(app, ids)
    if level:
        alerts = [a for a in alerts if a["level"] == level]
    if metric == "alert_count":
        detail = f"Alertas nivel {level}" if level else "Todas las alertas"
        return str(len(alerts)), detail
    if metric == "patient_count":
        count = len(ids) if ids is not None else len(app.dataset.patients)
        return str(count), "Pacientes en el alcance"
    if metric == "discarded_count":
        return str(sum(1 for a in alerts if a["level"] == "DESCARTADO")), "Descartados con motivo visible"
    if metric == "average_risk_score":
        if not alerts:
            return "—", "Sin alertas para calcular el promedio"
        average = sum(float(a.get("risk_score") or 0) for a in alerts) / len(alerts)
        return f"{average:.3f}", f"Promedio de {len(alerts)} alertas"
    if metric == "top_priority_patient":
        top = alerts[0] if alerts else None
        return (str(top["patient_id"]), f"{top['level']} · {top['pattern']}") if top else ("—", "Sin alertas")
    return "—", "Métrica no disponible"


def build_scope_chart(
    app: AppState,
    scope: ResolvedScope | None,
    widget: dict[str, Any],
) -> dict[str, Any]:
    spec = widget.get("chart") or {}
    analysis = spec.get("analysis")
    ids = _scope_ids(scope, widget.get("cohort"))
    if scope is None or ids is None:
        return {"error": "El gráfico agregado requiere un alcance resuelto.", "data": [], "layout": {}}
    if not ids:
        return {"error": "El alcance no contiene pacientes.", "data": [], "layout": {}}
    title = widget.get("title") or "Análisis de cohorte"
    provenance = {
        "scope_id": scope.scope_id,
        "cohort": widget.get("cohort"),
        "patient_count": len(ids),
        "source": app.dataset.origin,
    }
    if analysis == "alert_breakdown":
        group_by = spec.get("group_by") or "level"
        alerts = _selected_alerts(app, ids)
        counts: dict[str, int] = {}
        for alert in alerts:
            key = str(alert.get(group_by) or "SIN_DATO")
            counts[key] = counts.get(key, 0) + 1
        return {
            "data": [{"type": "bar", "name": "alertas", "x": list(counts), "y": list(counts.values())}],
            "layout": {"title": title, "xaxis": {"title": group_by}, "yaxis": {"title": "alertas"}},
            "provenance": [provenance],
            "origin": app.dataset.origin,
        }
    if analysis == "distribution":
        field = spec.get("field")
        if field == "age_years":
            frame = app.dataset.patients
            values = frame[frame["patient_id"].isin(ids)][field].dropna().astype(float).tolist()
        else:
            values = [
                float(alert.get(field) or 0)
                for alert in _selected_alerts(app, ids)
                if alert.get(field) is not None
            ]
        return {
            "data": [{"type": "histogram", "name": field, "x": values}],
            "layout": {"title": title, "xaxis": {"title": field}, "yaxis": {"title": "frecuencia"}},
            "provenance": [provenance],
            "origin": app.dataset.origin,
        }
    if analysis == "cohort_comparison":
        field = spec.get("field")
        names, values = [], []
        for cohort in scope.cohorts:
            cohort_ids = set(cohort.patient_ids)
            names.append(cohort.name)
            if field == "age_years":
                frame = app.dataset.patients
                series = frame[frame["patient_id"].isin(cohort_ids)][field].dropna().astype(float)
                values.append(round(float(series.mean()), 3) if len(series) else 0)
            elif field:
                samples = [
                    float(alert.get(field) or 0)
                    for alert in _selected_alerts(app, cohort_ids)
                    if alert.get(field) is not None
                ]
                values.append(round(sum(samples) / len(samples), 3) if samples else 0)
            else:
                values.append(len(cohort_ids))
        return {
            "data": [{"type": "bar", "name": field or "pacientes", "x": names, "y": values}],
            "layout": {"title": title, "xaxis": {"title": "cohorte"}, "yaxis": {"title": field or "pacientes"}},
            "provenance": [provenance],
            "origin": app.dataset.origin,
        }
    if analysis == "cohort_timeseries":
        traces = []
        missing = []
        time_window_hours = spec.get("time_window_hours")
        for variable in spec.get("variables") or []:
            points = []
            for patient_id in ids:
                series = _series(app.dataset, patient_id, variable)
                if series is not None and not series.empty:
                    points.append(series)
            if not points:
                missing.append(variable)
                continue
            combined = pd.concat(points).sort_index()
            combined = _within_latest_window(combined, time_window_hours)
            daily = combined.groupby(combined.index.floor("D")).mean()
            traces.append(
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "name": variable,
                    "x": [timestamp.isoformat() for timestamp in daily.index],
                    "y": [round(float(value), 3) for value in daily.values],
                }
            )
        return {
            "data": traces,
            "layout": {"title": title, "xaxis": {"title": "tiempo"}, "yaxis": {"title": "media de cohorte"}},
            "provenance": [provenance],
            "missing": missing,
            "origin": app.dataset.origin,
            **({"error": "No hay series para el alcance solicitado."} if not traces else {}),
        }
    return {"error": f"Análisis agregado desconocido: {analysis}", "data": [], "layout": {"title": title}}


def build_chart(
    dataset: Dataset,
    kind: str = "line",
    patient_id: str | None = None,
    variables: list[str] | None = None,
    title: str | None = None,
    time_window_hours: int | None = None,
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
        series = _within_latest_window(series, time_window_hours)
        if series.empty:
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


def _within_latest_window(series: pd.Series, hours: int | None) -> pd.Series:
    if not hours or series.empty:
        return series
    cutoff = series.index.max() - pd.Timedelta(hours=int(hours))
    return series[series.index >= cutoff]


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
