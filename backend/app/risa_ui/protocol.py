from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

RISA_UI_WIDGET_TYPES = {"kpi", "chart", "table", "alert_list", "evidence", "markdown"}
RISA_UI_METRICS = {
    "alert_count",
    "patient_count",
    "discarded_count",
    "average_risk_score",
    "top_priority_patient",
}
RISA_UI_VARIABLES = {
    "heart_rate",
    "spo2",
    "resp_rate",
    "sbp",
    "dbp",
    "temp",
    "LAB_A",
    "LAB_B",
    "LAB_C",
    "LAB_D",
}
ALERT_LEVELS = ("CRITICO", "ALTO", "MEDIO", "BAJO", "DESCARTADO")

AlertLevel = Literal["CRITICO", "ALTO", "MEDIO", "BAJO", "DESCARTADO"]
Metric = Literal[
    "alert_count",
    "patient_count",
    "discarded_count",
    "average_risk_score",
    "top_priority_patient",
]
Variable = Literal[
    "heart_rate",
    "spo2",
    "resp_rate",
    "sbp",
    "dbp",
    "temp",
    "LAB_A",
    "LAB_B",
    "LAB_C",
    "LAB_D",
]
TableColumn = Literal[
    "id",
    "patient_id",
    "level",
    "pattern",
    "score",
    "title",
    "review_status",
    "risk_score",
    "priority_level",
    "anomaly_score",
    "pattern_score",
    "age_years",
    "age_group",
    "sex_at_birth",
    "region_type",
    "care_program",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WidgetFilters(StrictModel):
    level: AlertLevel | None = None


class WidgetAction(StrictModel):
    action: Literal["select_alert"]


class BaseWidget(StrictModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    title: str | None = Field(default=None, max_length=160)
    scope_id: str | None = Field(default=None, max_length=64)
    cohort: str | None = Field(default=None, max_length=50)


class KpiWidget(BaseWidget):
    type: Literal["kpi"]
    metric: Metric
    filters: WidgetFilters = Field(default_factory=WidgetFilters)
    hint: str | None = Field(default=None, max_length=240)


class ChartBinding(StrictModel):
    analysis: Literal[
        "patient_series",
        "cohort_timeseries",
        "distribution",
        "cohort_comparison",
        "alert_breakdown",
    ] = "patient_series"
    patient_id: str | None = Field(default=None, min_length=1, max_length=32)
    variables: list[Variable] = Field(default_factory=list, max_length=4)
    field: Literal["age_years", "score", "risk_score", "anomaly_score", "pattern_score"] | None = None
    group_by: Literal["level", "priority_level", "age_group", "sex_at_birth", "region_type", "care_program", "pattern"] | None = None
    aggregate: Literal["mean", "median", "count"] = "mean"
    kind: Literal["line", "bar", "scatter"] = "line"

    @model_validator(mode="after")
    def validate_analysis(self) -> ChartBinding:
        if self.analysis in {"patient_series", "cohort_timeseries"} and not self.variables:
            raise ValueError("las series requieren al menos una variable")
        if self.analysis == "distribution" and not self.field:
            raise ValueError("distribution requiere field")
        return self


class ChartWidget(BaseWidget):
    type: Literal["chart"]
    chart: ChartBinding


class TableWidget(BaseWidget):
    type: Literal["table"]
    source: Literal["alerts", "patients"] = "alerts"
    columns: list[TableColumn] | None = Field(default=None, min_length=1, max_length=9)
    filters: WidgetFilters = Field(default_factory=WidgetFilters)
    limit: int = Field(default=20, ge=1, le=100)
    on_select: WidgetAction | None = None

    @model_validator(mode="after")
    def validate_source_fields(self) -> TableWidget:
        alert_columns = {
            "id",
            "patient_id",
            "level",
            "pattern",
            "score",
            "title",
            "review_status",
            "risk_score",
            "priority_level",
            "anomaly_score",
            "pattern_score",
        }
        patient_columns = {
            "patient_id",
            "age_years",
            "age_group",
            "sex_at_birth",
            "region_type",
            "care_program",
        }
        allowed = alert_columns if self.source == "alerts" else patient_columns
        if self.columns and not set(self.columns).issubset(allowed):
            raise ValueError(f"columnas incompatibles con source={self.source}")
        if self.source != "alerts" and self.filters.level:
            raise ValueError("el filtro level solo aplica a tablas de alertas")
        if self.source != "alerts" and self.on_select:
            raise ValueError("select_alert solo aplica a tablas de alertas")
        return self


class AlertListWidget(BaseWidget):
    type: Literal["alert_list"]
    level: AlertLevel | None = None
    limit: int = Field(default=8, ge=1, le=100)
    on_select: WidgetAction | None = None


class EvidenceWidget(BaseWidget):
    type: Literal["evidence"]
    alert_id: str | None = Field(default=None, min_length=1, max_length=64)
    patient_id: str | None = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def require_reference(self) -> EvidenceWidget:
        if bool(self.alert_id) == bool(self.patient_id):
            raise ValueError("evidence requiere exactamente alert_id o patient_id")
        return self


class MarkdownWidget(BaseWidget):
    type: Literal["markdown"]
    text: str = Field(min_length=1, max_length=2000)


RisaUiWidget = Annotated[
    KpiWidget | ChartWidget | TableWidget | AlertListWidget | EvidenceWidget | MarkdownWidget,
    Field(discriminator="type"),
]
_WIDGET_ADAPTER = TypeAdapter(RisaUiWidget)


class RisaUiDocumentInput(StrictModel):
    title: str = Field(default="Dashboard RISA Signal", min_length=1, max_length=160)
    subtitle: str = Field(default="", max_length=300)
    widgets: list[dict[str, Any]] = Field(default_factory=list, max_length=12)


class EmitRisaUiArgs(StrictModel):
    title: str = Field(default="Dashboard RISA Signal", min_length=1, max_length=160)
    subtitle: str = Field(default="", max_length=300)
    widgets: list[RisaUiWidget] = Field(default_factory=list, max_length=12)
    use_turno_template: bool = False


def emit_risa_ui_schema() -> dict[str, Any]:
    """JSON Schema usado por el tool calling del LLM."""
    return EmitRisaUiArgs.model_json_schema()


def validate_risa_ui(doc: dict[str, Any]) -> dict[str, Any]:
    """Valida el sobre y descarta widgets inválidos de forma aislada."""
    envelope = RisaUiDocumentInput.model_validate(
        {
            "title": doc.get("title") or "Dashboard RISA Signal",
            "subtitle": doc.get("subtitle") or "",
            "widgets": doc.get("widgets") or [],
        }
    )
    widgets: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in envelope.widgets:
        try:
            widget = _WIDGET_ADAPTER.validate_python(raw)
        except (TypeError, ValueError):
            continue
        if widget.id in seen_ids:
            continue
        seen_ids.add(widget.id)
        widgets.append(widget.model_dump(exclude_none=True))
    return {
        "protocol": "risa-ui",
        "version": "1.0",
        "title": envelope.title,
        "subtitle": envelope.subtitle,
        "widgets": widgets,
    }


def template_turno(alerts: list[dict[str, Any]], origin: str) -> dict[str, Any]:
    active = [a for a in alerts if a.get("level") != "DESCARTADO"]
    top = active[0] if active else (alerts[0] if alerts else None)
    widgets: list[dict[str, Any]] = [
        {
            "type": "kpi",
            "id": "kpi-crit",
            "title": "Críticos",
            "metric": "alert_count",
            "filters": {"level": "CRITICO"},
            "hint": "Revisar ahora",
        },
        {
            "type": "kpi",
            "id": "kpi-alto",
            "title": "Altos",
            "metric": "alert_count",
            "filters": {"level": "ALTO"},
            "hint": "Prioridad alta",
        },
        {
            "type": "kpi",
            "id": "kpi-desc",
            "title": "Descartados",
            "metric": "discarded_count",
            "hint": "Visibles con motivo (RN-02)",
        },
        {
            "type": "kpi",
            "id": "kpi-top",
            "title": "Caso a revisar primero",
            "metric": "top_priority_patient",
            "hint": "Mayor prioridad calculada",
        },
        {
            "type": "alert_list",
            "id": "alerts",
            "title": "Cola priorizada",
            "limit": 8,
            "on_select": {"action": "select_alert"},
        },
    ]
    if top:
        widgets.append(
            {
                "type": "evidence",
                "id": "ev-top",
                "title": f"Evidencia {top.get('id', '')}",
                "alert_id": top.get("id"),
            }
        )
    widgets.append(
        {
            "type": "markdown",
            "id": "note",
            "title": "Nota",
            "text": "Los valores salen del motor de alertas. El texto del chat se separa de esta evidencia.",
        }
    )
    return validate_risa_ui(
        {
            "title": "Turno actual — RISA Signal",
            "subtitle": f"Dataset {origin}. Apoyo a la revisión, no diagnóstico.",
            "widgets": widgets,
        }
    )
