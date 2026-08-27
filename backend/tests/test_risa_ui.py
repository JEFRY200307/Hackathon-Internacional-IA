from __future__ import annotations

import unittest

import pandas as pd
from pydantic import ValidationError

from app.charts import hydrate_risa_ui
from app.risa_ui.protocol import template_turno, validate_risa_ui


class FakeDataset:
    origin = "test-dataset"

    def __init__(self) -> None:
        self.patients = pd.DataFrame(
            [
                {"patient_id": "PAT-0001", "age": 40, "sex": "F"},
                {"patient_id": "PAT-0002", "age": 52, "sex": "M"},
            ]
        )

    def vitals_for(self, patient_id: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"timestamp": pd.Timestamp("2026-01-01"), "heart_rate": 80.0, "spo2": 97.0},
                {"timestamp": pd.Timestamp("2026-01-02"), "heart_rate": 88.0, "spo2": 95.0},
            ]
        )

    def labs_for(self, patient_id: str) -> pd.DataFrame:
        return pd.DataFrame(columns=["timestamp", "analyte", "value"])


class FakeApp:
    def __init__(self) -> None:
        self.dataset = FakeDataset()
        self.alerts = [
            {
                "id": "A-001",
                "patient_id": "PAT-0001",
                "level": "CRITICO",
                "pattern": "PROGRESSIVE",
                "title": "Caso prioritario",
                "score": 0.9,
                "evidence": [],
            },
            {
                "id": "A-002",
                "patient_id": "PAT-0002",
                "level": "DESCARTADO",
                "pattern": "CONTEXTUAL",
                "title": "Variación contextual",
                "score": 0.2,
                "evidence": [],
            },
        ]

    def alert_by_id(self, alert_id: str) -> dict | None:
        return next((alert for alert in self.alerts if alert["id"] == alert_id), None)

    def alerts_for_patient(self, patient_id: str) -> list[dict]:
        return [alert for alert in self.alerts if alert["patient_id"] == patient_id]


class RisaUiProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FakeApp()

    def test_protocol_discards_unknown_and_duplicate_widgets(self) -> None:
        result = validate_risa_ui(
            {
                "title": "Prueba",
                "widgets": [
                    {"id": "safe", "type": "markdown", "text": "Texto"},
                    {"id": "unsafe", "type": "html", "text": "<script />"},
                    {"id": "safe", "type": "markdown", "text": "Duplicado"},
                ],
            }
        )
        self.assertEqual(result["protocol"], "risa-ui")
        self.assertEqual([widget["id"] for widget in result["widgets"]], ["safe"])

    def test_agent_cannot_inject_kpi_value(self) -> None:
        result = validate_risa_ui(
            {
                "widgets": [
                    {
                        "id": "invented",
                        "type": "kpi",
                        "metric": "alert_count",
                        "value": "999",
                    }
                ]
            }
        )
        self.assertEqual(result["widgets"], [])

    def test_widget_limit_is_enforced(self) -> None:
        with self.assertRaises(ValidationError):
            validate_risa_ui(
                {
                    "widgets": [
                        {"id": f"note-{index}", "type": "markdown", "text": "ok"}
                        for index in range(13)
                    ]
                }
            )

    def test_incompatible_table_columns_are_discarded(self) -> None:
        result = validate_risa_ui(
            {
                "widgets": [
                    {
                        "id": "invalid-patients",
                        "type": "table",
                        "source": "patients",
                        "columns": ["patient_id", "score"],
                    }
                ]
            }
        )
        self.assertEqual(result["widgets"], [])

    def test_backend_calculates_kpis_and_filters_lists(self) -> None:
        result = hydrate_risa_ui(
            {
                "widgets": [
                    {
                        "id": "critical",
                        "type": "kpi",
                        "metric": "alert_count",
                        "filters": {"level": "CRITICO"},
                    },
                    {
                        "id": "discarded",
                        "type": "alert_list",
                        "level": "DESCARTADO",
                        "limit": 1,
                    },
                ]
            },
            self.app,
        )
        kpi, alert_list = result["widgets"]
        self.assertEqual(kpi["value"], "1")
        self.assertEqual([item["id"] for item in alert_list["items"]], ["A-002"])

    def test_tables_apply_columns_filters_and_limits(self) -> None:
        result = hydrate_risa_ui(
            {
                "widgets": [
                    {
                        "id": "critical-table",
                        "type": "table",
                        "source": "alerts",
                        "columns": ["id", "level"],
                        "filters": {"level": "CRITICO"},
                        "limit": 1,
                    }
                ]
            },
            self.app,
        )
        self.assertEqual(result["widgets"][0]["rows"], [{"id": "A-001", "level": "CRITICO"}])

    def test_chart_uses_allowed_dataset_series(self) -> None:
        result = hydrate_risa_ui(
            {
                "widgets": [
                    {
                        "id": "series",
                        "type": "chart",
                        "chart": {
                            "patient_id": "PAT-0001",
                            "variables": ["heart_rate", "spo2"],
                            "kind": "line",
                        },
                    }
                ]
            },
            self.app,
        )
        plotly = result["widgets"][0]["plotly"]
        self.assertEqual(len(plotly["data"]), 2)
        self.assertEqual(plotly["missing"], [])

    def test_turn_template_is_safe_without_alerts(self) -> None:
        result = template_turno([], "empty")
        self.assertEqual(result["protocol"], "risa-ui")
        self.assertFalse(any(widget["type"] == "evidence" for widget in result["widgets"]))


if __name__ == "__main__":
    unittest.main()
