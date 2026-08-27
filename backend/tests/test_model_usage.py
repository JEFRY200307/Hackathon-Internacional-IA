from __future__ import annotations

import unittest
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline import evaluacion
from pipeline.despliegue import CACHE_SCHEMA_VERSION, load_or_build
from app.alerts.service import PRIORITY_ORDER, build_alerts


class PersistedModelUsageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_or_build()

    def test_cache_has_current_schema_and_artifact_provenance(self) -> None:
        self.assertEqual(self.dataset.cache_schema_version, CACHE_SCHEMA_VERSION)
        provenance = self.dataset.model_provenance
        self.assertEqual(provenance["source"], "persisted_artifact")
        self.assertEqual(provenance["anomaly"]["chosen_model"], "mad")
        self.assertEqual(provenance["pattern"]["chosen_model"], "xgboost")
        self.assertEqual(len(provenance["fingerprint"]), 64)

    def test_cached_scores_equal_reloaded_joblib_scores(self) -> None:
        anomaly, pattern, provenance = evaluacion.score_from_persisted_models(self.dataset.alert_drafts)
        self.assertEqual(provenance["fingerprint"], self.dataset.model_provenance["fingerprint"])
        for patient_id in list(anomaly)[:25]:
            self.assertAlmostEqual(anomaly[patient_id], self.dataset.anomaly_scores[patient_id], places=10)
            self.assertAlmostEqual(pattern[patient_id], self.dataset.pattern_scores[patient_id], places=10)

    def test_alert_feed_uses_fused_priority_and_has_no_legacy_alias(self) -> None:
        alerts = build_alerts(self.dataset)
        ordering = [
            (PRIORITY_ORDER[alert["priority_level"]], -float(alert["risk_score"]))
            for alert in alerts
        ]
        self.assertEqual(ordering, sorted(ordering))
        self.assertTrue(all("local_model_score" not in alert for alert in alerts))
        self.assertTrue(all(alert["model_provenance"]["source"] == "persisted_artifact" for alert in alerts))


if __name__ == "__main__":
    unittest.main()
