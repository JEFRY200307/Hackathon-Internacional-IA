from __future__ import annotations

from app.alerts.service import build_alerts
from app.data.loader import Dataset, load_dataset, variable_catalog
from app.rag.index import RULES_TEXT, RagIndex


class AppState:
    def __init__(self) -> None:
        self.dataset: Dataset = load_dataset()
        self.alerts: list[dict] = build_alerts(self.dataset)
        self.rag = RagIndex()
        self.rebuild_rag()

    def rebuild_rag(self) -> None:
        patients = self.dataset.patients.to_dict(orient="records")
        self.rag.build(self.alerts, patients, RULES_TEXT, variable_catalog())

    def alert_by_id(self, alert_id: str) -> dict | None:
        return next((a for a in self.alerts if a["id"] == alert_id), None)

    def alerts_for_patient(self, patient_id: str) -> list[dict]:
        return [a for a in self.alerts if a["patient_id"] == patient_id]


state = AppState()
