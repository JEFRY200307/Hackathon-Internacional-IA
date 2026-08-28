from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.whatsapp.runtime import runtime

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> str:
    if mode != "subscribe" or not challenge or token != runtime.settings.whatsapp_verify_token:
        raise HTTPException(403, "verificación de webhook rechazada")
    return challenge


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    signature: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
) -> dict[str, str]:
    body = await request.body()
    if not runtime.client.verify_signature(body, signature):
        raise HTTPException(401, "firma de webhook inválida")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "JSON inválido") from exc
    await runtime.process_webhook(payload)
    return {"status": "accepted"}


def _require_admin(token: str | None) -> None:
    expected = runtime.settings.whatsapp_admin_token
    if not expected or token != expected:
        raise HTTPException(403, "administración no autorizada")


@router.get("/status")
def whatsapp_status(
    admin_token: Annotated[str | None, Header(alias="X-RISA-Admin-Token")] = None,
) -> dict[str, Any]:
    _require_admin(admin_token)
    return {
        "enabled": runtime.settings.whatsapp_enabled,
        "dry_run": runtime.client.dry_run,
        "live_ready": runtime.settings.whatsapp_live_ready,
        "twilio_live_ready": runtime.settings.twilio_live_ready,
        "twilio_dry_run": runtime.verifier.dry_run,
        "contacts": len(runtime.store.list_contacts()),
        "clinical_store": runtime.clinical.stats(),
        "worker_running": bool(runtime.task and not runtime.task.done()),
    }


@router.post("/notifications/run")
async def run_notifications(
    admin_token: Annotated[str | None, Header(alias="X-RISA-Admin-Token")] = None,
    include_baseline: bool = False,
) -> dict[str, int]:
    _require_admin(admin_token)
    queued = await runtime.scan_notifications(allow_baseline=include_baseline)
    sent = await runtime.dispatch_outbox()
    return {"queued": queued, "sent": sent}
