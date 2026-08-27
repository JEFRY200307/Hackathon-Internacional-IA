from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.state import AppState

_PID = re.compile(r"PAT-[\dA-Z]{2,8}", re.I)
_AGE_RANGE = re.compile(r"(?:edad|años?)\s*(?:entre|de)?\s*(\d{1,3})\s*(?:a|y|-)\s*(\d{1,3})", re.I)
_OLDER = re.compile(r"(?:mayores?\s+de|edad\s*(?:>=|mayor(?:es)?\s+que))\s*(\d{1,3})", re.I)
_YOUNGER = re.compile(r"(?:menores?\s+de|edad\s*(?:<=|menor(?:es)?\s+que))\s*(\d{1,3})", re.I)
_RISK_RANGE = re.compile(r"(?:riesgo|risk_score)\s*(?:entre|de)?\s*(0(?:\.\d+)?|1(?:\.0+)?)\s*(?:a|y|-)\s*(0(?:\.\d+)?|1(?:\.0+)?)", re.I)

Intent = Literal["detail", "cohort", "compare", "trend", "distribution", "quality"]
Variable = Literal["heart_rate", "spo2", "resp_rate", "sbp", "dbp", "temp", "LAB_A", "LAB_B", "LAB_C", "LAB_D"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CohortFilters(StrictModel):
    levels: list[Literal["CRITICO", "ALTO", "MEDIO", "BAJO", "DESCARTADO"]] = Field(default_factory=list, max_length=5)
    priority_levels: list[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]] = Field(default_factory=list, max_length=4)
    age_min: int | None = Field(default=None, ge=0, le=120)
    age_max: int | None = Field(default=None, ge=0, le=120)
    sex: list[str] = Field(default_factory=list, max_length=4)
    region_type: list[str] = Field(default_factory=list, max_length=10)
    care_program: list[str] = Field(default_factory=list, max_length=20)
    score_min: float | None = Field(default=None, ge=0, le=100)
    score_max: float | None = Field(default=None, ge=0, le=100)
    risk_score_min: float | None = Field(default=None, ge=0, le=1)
    risk_score_max: float | None = Field(default=None, ge=0, le=1)


class CohortSpec(StrictModel):
    name: str = Field(default="principal", min_length=1, max_length=50)
    patient_ids: list[str] = Field(default_factory=list, max_length=250)
    filters: CohortFilters = Field(default_factory=CohortFilters)


class DashboardQueryPlan(StrictModel):
    intent: Intent = "cohort"
    wants_dashboard: bool = False
    cohorts: list[CohortSpec] = Field(default_factory=lambda: [CohortSpec()], min_length=1, max_length=3)
    variables: list[Variable] = Field(default_factory=list, max_length=4)
    metrics: list[str] = Field(default_factory=list, max_length=8)
    group_by: Literal["level", "priority_level", "age_group", "sex_at_birth", "region_type", "care_program", "pattern"] | None = None
    time_window_hours: int | None = Field(default=None, ge=1, le=24 * 365)


class ResolvedCohort(StrictModel):
    name: str
    patient_ids: list[str]
    filters: dict[str, Any]
    total: int


class ResolvedScope(StrictModel):
    scope_id: str
    intent: Intent
    cohorts: list[ResolvedCohort]
    patient_ids: list[str]
    warnings: list[str] = Field(default_factory=list)

    def cohort_ids(self, name: str | None = None) -> set[str]:
        if name:
            found = next((cohort for cohort in self.cohorts if cohort.name == name), None)
            return set(found.patient_ids) if found else set()
        return set(self.patient_ids)


def plan_tool_schema() -> dict[str, Any]:
    return DashboardQueryPlan.model_json_schema()


class CohortQueryService:
    """Resuelve filtros catalogados; nunca evalúa SQL ni expresiones del LLM."""

    def __init__(self, app: AppState) -> None:
        self.app = app
        self.patients = app.dataset.patients.copy()
        self.patients["patient_id"] = self.patients["patient_id"].astype(str)
        self.alert_by_patient = {alert["patient_id"]: alert for alert in app.alerts}

    def catalog(self) -> dict[str, Any]:
        def values(column: str) -> list[str]:
            if column not in self.patients:
                return []
            return sorted(str(value) for value in self.patients[column].dropna().unique())

        return {
            "patient_fields": list(self.patients.columns),
            "levels": ["CRITICO", "ALTO", "MEDIO", "BAJO", "DESCARTADO"],
            "priority_levels": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
            "sex": values("sex_at_birth"),
            "region_type": values("region_type"),
            "care_program": values("care_program"),
            "variables": ["heart_rate", "spo2", "resp_rate", "sbp", "dbp", "temp", "LAB_A", "LAB_B", "LAB_C", "LAB_D"],
        }

    def resolve(self, plan: DashboardQueryPlan) -> ResolvedScope:
        known_ids = set(self.patients["patient_id"])
        cohorts: list[ResolvedCohort] = []
        warnings: list[str] = []
        for spec in plan.cohorts:
            frame = self.patients
            explicit = [pid.upper() for pid in spec.patient_ids]
            unknown = [pid for pid in explicit if pid not in known_ids]
            if unknown:
                warnings.append(f"Pacientes inexistentes omitidos en {spec.name}: {', '.join(unknown[:5])}")
            if explicit:
                frame = frame[frame["patient_id"].isin([pid for pid in explicit if pid in known_ids])]
            filters = spec.filters
            frame = self._filter_patient_columns(frame, filters)
            ids = [pid for pid in frame["patient_id"].tolist() if self._matches_alert(pid, filters)]
            if not ids:
                warnings.append(f"{spec.name}: ningún paciente coincide con los filtros")
            cohorts.append(
                ResolvedCohort(
                    name=spec.name,
                    patient_ids=ids,
                    filters=filters.model_dump(exclude_none=True),
                    total=len(ids),
                )
            )
        all_ids = list(dict.fromkeys(pid for cohort in cohorts for pid in cohort.patient_ids))
        payload = json.dumps(
            {"intent": plan.intent, "cohorts": [cohort.model_dump() for cohort in cohorts]},
            sort_keys=True,
            ensure_ascii=True,
        )
        scope_id = "scope-" + hashlib.sha256(payload.encode()).hexdigest()[:12]
        return ResolvedScope(
            scope_id=scope_id,
            intent=plan.intent,
            cohorts=cohorts,
            patient_ids=all_ids,
            warnings=warnings,
        )

    def _filter_patient_columns(self, frame, filters: CohortFilters):
        if filters.age_min is not None and "age_years" in frame:
            frame = frame[frame["age_years"] >= filters.age_min]
        if filters.age_max is not None and "age_years" in frame:
            frame = frame[frame["age_years"] <= filters.age_max]
        for field, requested in (
            ("sex_at_birth", filters.sex),
            ("region_type", filters.region_type),
            ("care_program", filters.care_program),
        ):
            if requested and field in frame:
                wanted = {str(value).upper() for value in requested}
                frame = frame[frame[field].astype(str).str.upper().isin(wanted)]
        return frame

    def _matches_alert(self, patient_id: str, filters: CohortFilters) -> bool:
        alert = self.alert_by_patient.get(patient_id)
        if not alert:
            return not any(
                (
                    filters.levels,
                    filters.priority_levels,
                    filters.score_min is not None,
                    filters.score_max is not None,
                    filters.risk_score_min is not None,
                    filters.risk_score_max is not None,
                )
            )
        if filters.levels and alert["level"] not in filters.levels:
            return False
        if filters.priority_levels and alert.get("priority_level") not in filters.priority_levels:
            return False
        score, risk = float(alert.get("score") or 0), float(alert.get("risk_score") or 0)
        return not (
            (filters.score_min is not None and score < filters.score_min)
            or (filters.score_max is not None and score > filters.score_max)
            or (filters.risk_score_min is not None and risk < filters.risk_score_min)
            or (filters.risk_score_max is not None and risk > filters.risk_score_max)
        )


def deterministic_plan(text: str, catalog: dict[str, Any]) -> DashboardQueryPlan:
    low = text.lower()
    patient_ids = list(dict.fromkeys(match.group(0).upper() for match in _PID.finditer(text)))
    levels = [
        value
        for stems, value in (
            (("crític", "critic"), "CRITICO"),
            (("alt",), "ALTO"),
            (("medi",), "MEDIO"),
            (("baj",), "BAJO"),
            (("descart",), "DESCARTADO"),
        )
        if any(stem in low for stem in stems)
    ]
    filters = CohortFilters(levels=levels)
    age_range = _AGE_RANGE.search(text)
    older, younger = _OLDER.search(text), _YOUNGER.search(text)
    risk_range = _RISK_RANGE.search(text)
    if age_range:
        filters.age_min, filters.age_max = sorted((int(age_range.group(1)), int(age_range.group(2))))
    elif older:
        filters.age_min = int(older.group(1))
    elif younger:
        filters.age_max = int(younger.group(1))
    if risk_range:
        filters.risk_score_min, filters.risk_score_max = sorted((float(risk_range.group(1)), float(risk_range.group(2))))
    for field in ("sex", "region_type", "care_program"):
        found = [
            value
            for value in catalog.get(field, [])
            if re.search(rf"\b{re.escape(str(value).lower())}\b", low)
        ]
        if found:
            setattr(filters, field, found)
    variables = [
        variable
        for aliases, variable in (
            (("frecuencia cardíaca", "frecuencia cardiaca", "heart_rate", " fc "), "heart_rate"),
            (("spo2", "saturación", "saturacion"), "spo2"),
            (("respiratoria", "resp_rate", " fr "), "resp_rate"),
            (("sistólica", "sistolica", "sbp"), "sbp"),
            (("diastólica", "diastolica", "dbp"), "dbp"),
            (("temperatura", "temp"), "temp"),
            (("lab_a",), "LAB_A"),
            (("lab_b",), "LAB_B"),
            (("lab_c",), "LAB_C"),
            (("lab_d",), "LAB_D"),
        )
        if any(alias in f" {low} " for alias in aliases)
    ]
    wants_dashboard = any(word in low for word in ("dashboard", "tablero", "panel", "risa ui"))
    if "compar" in low and len(levels) >= 2:
        cohorts = [
            CohortSpec(name=level, filters=CohortFilters(levels=[level]))
            for level in levels[:3]
        ]
        intent: Intent = "compare"
    else:
        cohorts = [CohortSpec(name="principal", patient_ids=patient_ids, filters=filters)]
        if patient_ids:
            intent = "trend" if variables else "detail"
        elif "compar" in low:
            intent = "compare"
        elif any(word in low for word in ("tendencia", "evolución", "evolucion", "tiempo")):
            intent = "trend"
        elif any(word in low for word in ("distribución", "distribucion", "histograma")):
            intent = "distribution"
        elif any(word in low for word in ("calidad", "faltantes", "cobertura")):
            intent = "quality"
        else:
            intent = "cohort"
    return DashboardQueryPlan(
        intent=intent,
        wants_dashboard=wants_dashboard,
        cohorts=cohorts,
        variables=variables,
        group_by="level" if levels or "nivel" in low else None,
    )


async def create_query_plan(text: str, app: AppState) -> tuple[DashboardQueryPlan, CohortQueryService]:
    service = CohortQueryService(app)
    fallback = deterministic_plan(text, service.catalog())
    from app.config import settings

    if not settings.openai_api_key:
        return fallback, service
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        catalog = service.catalog()
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Convierte la petición en un plan declarativo de consulta RISA. "
                        "No calcules resultados, no inventes IDs ni escribas SQL. "
                        "Usa solo filtros y variables del schema. Para comparar, crea 2 o 3 cohorts."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"request": text, "catalog": catalog},
                        ensure_ascii=False,
                        default=str,
                    )[:12000],
                },
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "plan_dashboard_query",
                        "description": "Produce el plan estructurado de datos y visualización solicitado.",
                        "parameters": plan_tool_schema(),
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": "plan_dashboard_query"}},
            temperature=0,
        )
        calls = response.choices[0].message.tool_calls or []
        if not calls:
            return fallback, service
        plan = DashboardQueryPlan.model_validate_json(calls[0].function.arguments)
        plan.wants_dashboard = plan.wants_dashboard or fallback.wants_dashboard
        plan.variables = list(dict.fromkeys([*fallback.variables, *plan.variables]))[:4]
        explicit_ids = [pid for cohort in fallback.cohorts for pid in cohort.patient_ids]
        if explicit_ids:
            plan.cohorts = [
                CohortSpec(
                    name="principal",
                    patient_ids=explicit_ids,
                    filters=fallback.cohorts[0].filters,
                )
            ]
            plan.intent = fallback.intent
        elif fallback.intent == "compare" and len(fallback.cohorts) >= 2:
            plan.cohorts = fallback.cohorts
            plan.intent = "compare"
        else:
            hard_filters = fallback.cohorts[0].filters.model_dump(exclude_none=True)
            target = plan.cohorts[0].filters
            for field, value in hard_filters.items():
                if value not in ([], {}, ""):
                    setattr(target, field, value)
        return plan, service
    except Exception:
        return fallback, service


def compile_dashboard(
    plan: DashboardQueryPlan,
    scope: ResolvedScope,
    app: AppState,
) -> dict[str, Any]:
    """Compila estrategias seguras; sirve como fallback, no como layout único."""
    widgets: list[dict[str, Any]] = []
    first_id = scope.patient_ids[0] if scope.patient_ids else None
    variables = plan.variables or ["heart_rate"]
    for index, cohort in enumerate(scope.cohorts[:3]):
        widgets.append(
            {
                "id": f"patients-{index}",
                "type": "kpi",
                "title": f"Pacientes · {cohort.name}",
                "metric": "patient_count",
                "scope_id": scope.scope_id,
                "cohort": cohort.name,
            }
        )
    if plan.intent in {"detail", "trend"} and first_id and len(scope.patient_ids) == 1:
        widgets.append(
            {
                "id": "patient-series",
                "type": "chart",
                "title": f"Series de {first_id}",
                "scope_id": scope.scope_id,
                "cohort": scope.cohorts[0].name,
                "chart": {
                    "analysis": "patient_series",
                    "patient_id": first_id,
                    "variables": variables[:4],
                    "kind": "line",
                },
            }
        )
        alert = next((item for item in app.alerts if item["patient_id"] == first_id), None)
        if alert:
            widgets.append(
                {
                    "id": "patient-evidence",
                    "type": "evidence",
                    "title": f"Evidencia de {first_id}",
                    "scope_id": scope.scope_id,
                    "cohort": scope.cohorts[0].name,
                    "patient_id": first_id,
                }
            )
    elif plan.intent == "compare" and len(scope.cohorts) >= 2:
        widgets.append(
            {
                "id": "cohort-comparison",
                "type": "chart",
                "title": "Comparación de riesgo por cohorte",
                "scope_id": scope.scope_id,
                "chart": {
                    "analysis": "cohort_comparison",
                    "variables": [],
                    "field": "risk_score",
                    "kind": "bar",
                },
            }
        )
    elif plan.intent == "distribution":
        widgets.append(
            {
                "id": "distribution",
                "type": "chart",
                "title": "Distribución del alcance",
                "scope_id": scope.scope_id,
                "chart": {
                    "analysis": "distribution",
                    "variables": [],
                    "field": "risk_score",
                    "kind": "bar",
                },
            }
        )
    elif plan.intent == "trend" and scope.patient_ids:
        widgets.append(
            {
                "id": "cohort-trend",
                "type": "chart",
                "title": "Tendencia agregada de la cohorte",
                "scope_id": scope.scope_id,
                "chart": {
                    "analysis": "cohort_timeseries",
                    "variables": variables[:4],
                    "kind": "line",
                },
            }
        )
    else:
        widgets.append(
            {
                "id": "alert-breakdown",
                "type": "chart",
                "title": "Alertas por nivel",
                "scope_id": scope.scope_id,
                "chart": {
                    "analysis": "alert_breakdown",
                    "variables": [],
                    "group_by": plan.group_by or "level",
                    "kind": "bar",
                },
            }
        )
    widgets.extend(
        [
            {
                "id": "scope-alerts",
                "type": "alert_list",
                "title": "Alertas dentro del alcance",
                "scope_id": scope.scope_id,
                "limit": 10,
                "on_select": {"action": "select_alert"},
            },
            {
                "id": "scope-table",
                "type": "table",
                "title": "Casos incluidos",
                "scope_id": scope.scope_id,
                "source": "alerts",
                "columns": ["id", "patient_id", "level", "priority_level", "risk_score", "pattern"],
                "limit": 20,
                "on_select": {"action": "select_alert"},
            },
        ]
    )
    if scope.warnings:
        widgets.append(
            {
                "id": "scope-warning",
                "type": "markdown",
                "title": "Alcance",
                "text": " ".join(scope.warnings),
            }
        )
    return {
        "title": "Dashboard solicitado — RISA Signal",
        "subtitle": f"{len(scope.patient_ids)} pacientes · {scope.scope_id}",
        "widgets": widgets[:12],
    }
