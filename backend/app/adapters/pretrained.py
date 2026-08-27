from __future__ import annotations

import httpx

from app.config import settings


async def predict_risk(patient_id: str, features: dict, window: str = "48h") -> dict:
    payload = {"patient_id": patient_id, "features": features, "window": window}
    url = (settings.pretrained_model_url or "").rstrip("/")
    if url:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.post(f"{url}/predict", json=payload)
                response.raise_for_status()
                data = response.json()
                data["source"] = "remote"
                data.setdefault("model_version", "unknown")
                return data
        except Exception as exc:  # noqa: BLE001 — fallback is the product
            return local_predict(patient_id, features, error=str(exc))
    return local_predict(patient_id, features)


def local_predict(patient_id: str, features: dict, error: str | None = None) -> dict:
    hr_slope = float(features.get("hr_slope") or 0)
    spo2_min = float(features.get("spo2_min") or 100)
    sbp_slope = float(features.get("sbp_slope") or 0)
    missing_lab = float(features.get("missing_lab") or 0)
    raw = 0.15 + min(0.55, abs(hr_slope) * 0.6) + max(0.0, (94 - spo2_min) * 0.02)
    raw += max(0.0, -sbp_slope) * 0.25 + missing_lab * 0.05
    score = max(0.0, min(1.0, raw))
    if score >= 0.75:
        label = "CRITICO"
    elif score >= 0.55:
        label = "ALTO"
    elif score >= 0.35:
        label = "MEDIO"
    else:
        label = "BAJO"
    contributing = [k for k, v in features.items() if isinstance(v, (int, float)) and abs(float(v)) > 0.2][:5]
    result = {
        "patient_id": patient_id,
        "risk_score": round(score, 3),
        "label": label,
        "model_version": "local-fallback-0.1",
        "contributing_features": contributing,
        "source": "local_fallback",
    }
    if error:
        result["remote_error"] = error
    return result


def model_status() -> dict:
    configured = bool(settings.pretrained_model_url)
    return {
        "configured_remote": configured,
        "mode": "remote_if_up" if configured else "fallback",
        "url": settings.pretrained_model_url or None,
    }
