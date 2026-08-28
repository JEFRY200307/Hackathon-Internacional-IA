from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class TwilioVerify:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.dry_run = settings.twilio_dry_run or not settings.twilio_live_ready
        self.http = httpx.AsyncClient(
            base_url=(
                "https://verify.twilio.com/v2/Services/"
                f"{settings.twilio_verify_service_sid}"
            ),
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=20,
            transport=transport,
        )

    async def close(self) -> None:
        await self.http.aclose()

    async def start(self, phone: str) -> dict[str, Any]:
        if self.dry_run:
            return {"sid": "VE-dry-run", "status": "pending"}
        response = await self.http.post("/Verifications", data={"To": f"+{phone}", "Channel": "sms"})
        response.raise_for_status()
        payload = response.json()
        return {"sid": payload.get("sid"), "status": payload.get("status")}

    async def check(self, phone: str, code: str) -> bool:
        if self.dry_run:
            return code == "000000"
        response = await self.http.post(
            "/VerificationCheck",
            data={"To": f"+{phone}", "Code": code},
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return response.json().get("status") == "approved"
