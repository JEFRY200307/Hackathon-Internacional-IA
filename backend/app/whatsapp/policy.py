from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.config import Settings
from app.whatsapp.store import WhatsAppStore, utc_now

PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


class NotificationPolicy:
    def __init__(self, store: WhatsAppStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    def eligible(self, alert: dict[str, Any]) -> bool:
        priority = str(alert.get("priority_level") or "LOW")
        if priority in {"CRITICAL", "HIGH"}:
            return True
        if priority != "MEDIUM":
            return False
        risk = float(alert.get("risk_score") or 0)
        anomaly = float(alert.get("anomaly_score") or 0)
        pattern = float(alert.get("pattern_score") or 0)
        return (
            risk >= self.settings.whatsapp_medium_risk_threshold
            and anomaly >= 0.55
            and pattern >= 0.55
        )

    def fingerprint(self, alert: dict[str, Any]) -> str:
        provenance = alert.get("model_provenance") or {}
        payload = {
            "patient_id": alert.get("patient_id"),
            "priority": alert.get("priority_level"),
            "level": alert.get("level"),
            "pattern": alert.get("pattern"),
            "risk": round(float(alert.get("risk_score") or 0), 2),
            "model": provenance.get("fingerprint"),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20]

    def quiet_now(self, timezone_name: str) -> bool:
        try:
            hour = utc_now().astimezone(ZoneInfo(timezone_name)).hour
        except Exception:
            hour = utc_now().hour
        start = self.settings.whatsapp_quiet_start_hour
        end = self.settings.whatsapp_quiet_end_hour
        return hour >= start or hour < end if start > end else start <= hour < end

    def evaluate_contact(
        self,
        contact: dict[str, Any],
        alerts: list[dict[str, Any]],
        allow_baseline: bool = False,
    ) -> list[dict[str, Any]]:
        allowed = set(contact["patient_ids"])
        candidates = [
            alert
            for alert in alerts
            if alert.get("patient_id") in allowed and self.eligible(alert)
        ]
        decisions: list[dict[str, Any]] = []
        for alert in candidates:
            patient_id = str(alert["patient_id"])
            fingerprint = self.fingerprint(alert)
            rank = PRIORITY_RANK.get(str(alert.get("priority_level")), 9)
            risk = float(alert.get("risk_score") or 0)
            previous = self.store.alert_state(contact["phone"], patient_id)
            if previous is None:
                self.store.save_alert_state(contact["phone"], patient_id, fingerprint, rank, risk)
                if allow_baseline:
                    decisions.append(alert)
                continue
            changed = previous["fingerprint"] != fingerprint
            escalated = rank < int(previous["priority_rank"]) or risk >= float(previous["risk_score"]) + 0.1
            if not changed:
                self.store.save_alert_state(contact["phone"], patient_id, fingerprint, rank, risk)
                continue
            count = int(previous.get("notification_count") or 0)
            if previous.get("notification_day") != utc_now().date().isoformat():
                count = 0
            last_notified = previous.get("last_notified_at")
            cooling_down = bool(
                last_notified
                and datetime.fromisoformat(last_notified)
                > utc_now() - timedelta(hours=self.settings.whatsapp_cooldown_hours)
            )
            if count >= self.settings.whatsapp_max_notifications_day or (cooling_down and not escalated):
                continue
            if self.quiet_now(contact["timezone"]) and not escalated:
                continue
            decisions.append(alert)
        return decisions

    def queue_digest(self, contact: dict[str, Any], alerts: list[dict[str, Any]]) -> bool:
        if not alerts:
            return False
        top = min(alerts, key=lambda item: PRIORITY_RANK.get(str(item.get("priority_level")), 9))
        digest_fingerprint = hashlib.sha256(
            "|".join(sorted(self.fingerprint(alert) for alert in alerts)).encode()
        ).hexdigest()[:20]
        queued = self.store.queue(
            contact["phone"],
            "template",
            {
                "count": len(alerts),
                "priority": str(top.get("priority_level") or "MEDIUM"),
                "patients": [alert["patient_id"] for alert in alerts],
            },
            f"alert:{contact['phone']}:{digest_fingerprint}",
        )
        if queued:
            for alert in alerts:
                self.store.save_alert_state(
                    contact["phone"],
                    alert["patient_id"],
                    self.fingerprint(alert),
                    PRIORITY_RANK.get(str(alert.get("priority_level")), 9),
                    float(alert.get("risk_score") or 0),
                    notified=True,
                )
        return queued
