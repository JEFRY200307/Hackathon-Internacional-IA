from __future__ import annotations

import unittest

import pandas as pd

from app.llm.guards import ScopeViolation, apply_tool_scope, guard_citations, text_is_scoped
from app.llm.planning import (
    CohortQueryService,
    DashboardQueryPlan,
    ResolvedCohort,
    ResolvedScope,
    _inherit_follow_up,
    deterministic_plan,
)


class GroundingApp:
    def __init__(self) -> None:
        self.dataset = type(
            "Dataset",
            (),
            {
                "patients": pd.DataFrame(
                    [
                        {
                            "patient_id": "PAT-0724",
                            "age_years": 64,
                            "sex_at_birth": "F",
                            "region_type": "URBAN",
                            "care_program": "HOME_MONITORING",
                        },
                        {
                            "patient_id": "PAT-0290",
                            "age_years": 35,
                            "sex_at_birth": "M",
                            "region_type": "RURAL",
                            "care_program": "AMBULATORY",
                        },
                    ]
                )
            },
        )()
        self.alerts = [
            {
                "id": "A-724",
                "patient_id": "PAT-0724",
                "level": "CRITICO",
                "priority_level": "CRITICAL",
                "score": 91,
                "risk_score": 0.91,
            },
            {
                "id": "A-290",
                "patient_id": "PAT-0290",
                "level": "BAJO",
                "priority_level": "LOW",
                "score": 20,
                "risk_score": 0.2,
            },
        ]


def scope_724() -> ResolvedScope:
    return ResolvedScope(
        scope_id="scope-test",
        intent="detail",
        cohorts=[
            ResolvedCohort(
                name="principal",
                patient_ids=["PAT-0724"],
                filters={},
                total=1,
            )
        ],
        patient_ids=["PAT-0724"],
    )


class GroundingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = GroundingApp()
        self.service = CohortQueryService(self.app)

    def test_explicit_patient_scope_never_expands(self) -> None:
        plan = deterministic_plan("Dashboard para PAT-0724 con SpO2", self.service.catalog())
        scope = self.service.resolve(plan)
        self.assertEqual(scope.patient_ids, ["PAT-0724"])
        self.assertEqual(plan.variables, ["spo2"])

    def test_follow_up_inherits_patient_and_chart_constraints(self) -> None:
        messages = [
            "Realiza un gráfico de barras comparando los niveles de alerta para PAT-0724",
            "Dame únicamente el último mes registrado",
        ]
        current = deterministic_plan(messages[-1], self.service.catalog())
        plan = _inherit_follow_up(current, messages, self.service.catalog())
        scope = self.service.resolve(plan)
        self.assertEqual(scope.patient_ids, ["PAT-0724"])
        self.assertEqual(plan.chart_analysis, "alert_breakdown")
        self.assertEqual(plan.preferred_chart_kind, "bar")
        self.assertEqual(plan.time_window_hours, 720)

    def test_ranges_and_categories_resolve_deterministically(self) -> None:
        plan = deterministic_plan(
            "Panel de pacientes mayores de 60, URBAN, con riesgo entre 0.8 y 1.0",
            self.service.catalog(),
        )
        scope = self.service.resolve(plan)
        self.assertEqual(scope.patient_ids, ["PAT-0724"])

    def test_level_comparison_builds_separate_cohorts(self) -> None:
        plan = deterministic_plan(
            "Compara en dashboard pacientes críticos y bajos",
            self.service.catalog(),
        )
        scope = self.service.resolve(plan)
        self.assertEqual(plan.intent, "compare")
        self.assertEqual([cohort.name for cohort in scope.cohorts], ["CRITICO", "BAJO"])
        self.assertEqual([cohort.total for cohort in scope.cohorts], [1, 1])

    def test_tool_policy_rejects_cross_patient_argument(self) -> None:
        with self.assertRaises(ScopeViolation):
            apply_tool_scope("query_series", {"patient_id": "PAT-0290", "variable": "spo2"}, scope_724())

    def test_tool_policy_injects_scope_into_rag(self) -> None:
        args = apply_tool_scope("retrieve_evidence", {"query": "evidencia", "k": 4}, scope_724())
        self.assertEqual(args["patient_ids"], ["PAT-0724"])

    def test_citation_gate_filters_and_deduplicates(self) -> None:
        citations = [
            {"source_id": "patient:PAT-0724", "kind": "patient", "patient_id": "PAT-0724"},
            {"source_id": "patient:PAT-0724", "kind": "patient", "patient_id": "PAT-0724"},
            {"source_id": "patient:PAT-0290", "kind": "patient", "patient_id": "PAT-0290"},
            {"source_id": "rule:R-01", "kind": "rule", "patient_id": None},
        ]
        clean, warnings = guard_citations(citations, scope_724())
        self.assertEqual([item["source_id"] for item in clean], ["patient:PAT-0724", "rule:R-01"])
        self.assertTrue(any("PAT-0290" in warning for warning in warnings))

    def test_text_gate_detects_patient_leakage(self) -> None:
        self.assertTrue(text_is_scoped("Panel verificado para PAT-0724", scope_724()))
        self.assertFalse(text_is_scoped("También revisar PAT-0290", scope_724()))

    def test_zero_result_scope_is_explicit(self) -> None:
        plan = DashboardQueryPlan.model_validate(
            {
                "intent": "cohort",
                "cohorts": [{"name": "vacía", "filters": {"age_min": 100}}],
            }
        )
        scope = self.service.resolve(plan)
        self.assertEqual(scope.patient_ids, [])
        self.assertTrue(scope.warnings)


if __name__ == "__main__":
    unittest.main()
