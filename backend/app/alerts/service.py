from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from app.data.loader import Dataset
from pipeline.modelado import LEVEL_ORDER
from pipeline.fusion_evidencia import assign_evidence_roles

PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_evidence_list(d) -> list[dict]:
    fused = assign_evidence_roles(d)
    evidence_list = []
    for fe in fused:
        e = fe.item
        source_file = "vital_signs.csv" if e.source.startswith("vital") else ("laboratory_results.csv" if e.source == "laboratory" else e.source + ".csv")
        record_id = f"{d.patient_id}:{e.variable}"
        contribution = round(d.score / max(1, len(d.evidence)) / 100.0, 3)
        evidence_list.append({
            **asdict(e),
            "evidence_role": fe.role,
            "record_id": record_id,
            "source_file": source_file,
            "contribution": contribution
        })
    return evidence_list


def build_alerts(dataset: Dataset) -> list[dict]:
    """Adapta los `AlertDraft` ya calculados por el pipeline (fase de Modelado,
    Anomaly/Pattern/Risk/Priority Engine) al feed de la API."""
    alerts = []
    provenance = getattr(dataset, "model_provenance", {})
    for i, d in enumerate(dataset.alert_drafts, start=1):
        alerts.append(
            {
                "id": f"A-{i:03d}",
                "patient_id": d.patient_id,
                "score": d.score,
                "level": d.level,
                "pattern": d.pattern,
                "title": d.title,
                "evidence": _build_evidence_list(d),
                "missing_sources": d.missing_sources,
                "features": d.features,
                "anomaly_score": round(dataset.anomaly_scores.get(d.patient_id, 0.0), 3),
                "pattern_score": round(dataset.pattern_scores.get(d.patient_id, 0.0), 3),
                "risk_score": dataset.risk_scores.get(d.patient_id, 0.0),
                "priority_level": dataset.priority_levels.get(d.patient_id, "LOW"),
                "model_provenance": {
                    "source": provenance.get("source"),
                    "fingerprint": provenance.get("fingerprint"),
                    "anomaly_model": (provenance.get("anomaly") or {}).get("chosen_model"),
                    "pattern_model": (provenance.get("pattern") or {}).get("chosen_model"),
                },
                "review_status": "abierta",
                "created_at": _now(),
            }
        )
    alerts.sort(
        key=lambda a: (
            PRIORITY_ORDER.get(a["priority_level"], 9),
            -float(a["risk_score"]),
            LEVEL_ORDER.get(a["level"], 9),
            -float(a["score"]),
        )
    )
    return alerts


def counts_by_level(alerts: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for a in alerts:
        out[a["level"]] = out.get(a["level"], 0) + 1
    return out
