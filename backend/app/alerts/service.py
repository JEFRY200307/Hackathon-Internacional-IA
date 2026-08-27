from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from app.data.loader import Dataset
from pipeline.modelado import LEVEL_ORDER


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_alerts(dataset: Dataset) -> list[dict]:
    """Adapta los `AlertDraft` ya calculados por el pipeline (fase de Modelado,
    Anomaly/Pattern/Risk/Priority Engine) al feed de la API."""
    alerts = []
    for i, d in enumerate(dataset.alert_drafts, start=1):
        alerts.append(
            {
                "id": f"A-{i:03d}",
                "patient_id": d.patient_id,
                "score": d.score,
                "level": d.level,
                "pattern": d.pattern,
                "title": d.title,
                "evidence": [asdict(e) for e in d.evidence],
                "missing_sources": d.missing_sources,
                "features": d.features,
                "anomaly_score": round(dataset.anomaly_scores.get(d.patient_id, 0.0), 3),
                "pattern_score": round(dataset.pattern_scores.get(d.patient_id, 0.0), 3),
                "local_model_score": round(dataset.pattern_scores.get(d.patient_id, 0.0), 3),
                "risk_score": dataset.risk_scores.get(d.patient_id, 0.0),
                "priority_level": dataset.priority_levels.get(d.patient_id, "LOW"),
                "review_status": "abierta",
                "created_at": _now(),
            }
        )
    alerts.sort(key=lambda a: (LEVEL_ORDER.get(a["level"], 9), -a["score"]))
    return alerts


def counts_by_level(alerts: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for a in alerts:
        out[a["level"]] = out.get(a["level"], 0) + 1
    return out
