from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.llm.planning import DashboardQueryPlan, ResolvedScope
    from app.state import AppState

_PID = re.compile(r"PAT-[\dA-Z]{2,8}", re.I)


class ScopeViolation(ValueError):
    pass


def apply_tool_scope(name: str, args: dict[str, Any], scope: ResolvedScope) -> dict[str, Any]:
    scoped = dict(args)
    allowed = scope.cohort_ids()
    for key in ("patient_id",):
        patient_id = scoped.get(key)
        if patient_id and patient_id.upper() not in allowed:
            raise ScopeViolation(f"{name}: {patient_id} está fuera de {scope.scope_id}")
        if patient_id:
            scoped[key] = patient_id.upper()
    if name == "retrieve_evidence":
        requested = {pid.upper() for pid in scoped.get("patient_ids") or []}
        if requested and not requested.issubset(allowed):
            raise ScopeViolation("retrieve_evidence intentó ampliar el alcance")
        scoped["patient_ids"] = sorted(requested or allowed)
    if name == "emit_risa_ui":
        widgets = []
        only_patient = next(iter(allowed)) if len(allowed) == 1 else None
        for raw in scoped.get("widgets") or []:
            widget = {**raw, "scope_id": scope.scope_id}
            if widget.get("cohort") and not scope.cohort_ids(widget["cohort"]):
                raise ScopeViolation(f"cohorte desconocida: {widget['cohort']}")
            if widget.get("type") == "chart":
                chart = dict(widget.get("chart") or {})
                patient_id = chart.get("patient_id")
                if patient_id and patient_id.upper() not in allowed:
                    raise ScopeViolation(f"chart fuera del alcance: {patient_id}")
                if (chart.get("analysis") or "patient_series") == "patient_series" and not patient_id:
                    if not only_patient:
                        raise ScopeViolation("patient_series requiere un único paciente explícito")
                    chart["patient_id"] = only_patient
                widget["chart"] = chart
            if widget.get("type") == "evidence":
                patient_id = widget.get("patient_id")
                if patient_id and patient_id.upper() not in allowed:
                    raise ScopeViolation(f"evidence fuera del alcance: {patient_id}")
                if not patient_id and not widget.get("alert_id") and only_patient:
                    widget["patient_id"] = only_patient
            widgets.append(widget)
        scoped["widgets"] = widgets
    return scoped


def guard_citations(
    citations: list[dict[str, Any]],
    scope: ResolvedScope,
) -> tuple[list[dict[str, Any]], list[str]]:
    allowed = scope.cohort_ids()
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    warnings: list[str] = []
    for citation in citations:
        source_id = str(citation.get("source_id") or "")
        if not source_id or source_id in seen:
            continue
        patient_id = citation.get("patient_id")
        if citation.get("kind") in {"alert", "patient"} and patient_id not in allowed:
            warnings.append(f"Cita {source_id} descartada por estar fuera de {scope.scope_id}")
            continue
        seen.add(source_id)
        clean.append(citation)
    if allowed and not any(citation.get("patient_id") in allowed for citation in clean):
        warnings.append("No se recuperó evidencia específica del alcance; solo se muestran reglas o variables globales.")
    return clean, warnings


def guard_risa_ui(
    document: dict[str, Any] | None,
    scope: ResolvedScope,
) -> tuple[dict[str, Any] | None, list[str]]:
    if not document:
        return document, []
    allowed = scope.cohort_ids()
    clean_widgets = []
    warnings: list[str] = []
    for widget in document.get("widgets") or []:
        patients: set[str] = set()
        if widget.get("patient_id"):
            patients.add(widget["patient_id"])
        if widget.get("alert"):
            patients.add(widget["alert"].get("patient_id"))
        patients.update(
            str(row.get("patient_id"))
            for row in widget.get("rows") or []
            if row.get("patient_id")
        )
        patients.update(
            str(item.get("patient_id"))
            for item in widget.get("items") or []
            if item.get("patient_id")
        )
        plotly = widget.get("plotly") or {}
        if plotly.get("patient_id"):
            patients.add(plotly["patient_id"])
        for provenance in plotly.get("provenance") or []:
            if provenance.get("patient_id"):
                patients.add(provenance["patient_id"])
            if provenance.get("scope_id") and provenance["scope_id"] != scope.scope_id:
                patients.add("__INVALID_SCOPE__")
        if patients - allowed:
            warnings.append(f"Widget {widget.get('id')} descartado por contener entidades fuera del alcance.")
            continue
        clean_widgets.append(widget)
    return {**document, "widgets": clean_widgets}, warnings


def text_is_scoped(text: str, scope: ResolvedScope) -> bool:
    mentioned = {match.group(0).upper() for match in _PID.finditer(text)}
    return mentioned.issubset(scope.cohort_ids())


def grounded_summary(plan: DashboardQueryPlan, scope: ResolvedScope, app: AppState) -> str:
    allowed = scope.cohort_ids()
    alerts = [alert for alert in app.alerts if alert["patient_id"] in allowed]
    lines = [
        f"Consulta verificada sobre {len(allowed)} paciente(s) en {scope.scope_id}.",
        "Los filtros y cálculos fueron aplicados por el backend sobre RISA Data V1.0.",
    ]
    if len(allowed) == 1:
        patient_id = next(iter(allowed))
        alert = next((item for item in alerts if item["patient_id"] == patient_id), None)
        if alert:
            lines.append(
                f"{patient_id}: prioridad {alert.get('priority_level')}, nivel {alert['level']}, "
                f"patrón {alert['pattern']} y risk_score {float(alert.get('risk_score') or 0):.3f}."
            )
        else:
            lines.append(f"{patient_id}: no se encontró una alerta asociada.")
    else:
        lines.append(
            "Cohortes: "
            + ", ".join(f"{cohort.name} ({cohort.total})" for cohort in scope.cohorts)
            + "."
        )
    if scope.warnings:
        lines.append("Advertencias: " + " ".join(scope.warnings))
    lines.append("Apoyo a la revisión; no constituye diagnóstico ni prescripción.")
    return "\n".join(lines)
