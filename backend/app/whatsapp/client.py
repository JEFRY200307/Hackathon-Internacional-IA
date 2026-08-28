from __future__ import annotations

import hashlib
import hmac
import uuid
from typing import Any

import httpx

from app.config import Settings


class WhatsAppClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.dry_run = settings.whatsapp_dry_run or not settings.whatsapp_live_ready
        self.http = httpx.AsyncClient(timeout=30, transport=transport)

    @property
    def base_url(self) -> str:
        return (
            f"https://graph.facebook.com/{self.settings.whatsapp_graph_version}/"
            f"{self.settings.whatsapp_phone_number_id}"
        )

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.whatsapp_access_token}"}

    def verify_signature(self, body: bytes, signature: str | None) -> bool:
        if not self.settings.whatsapp_app_secret:
            return self.dry_run
        if not signature or not signature.startswith("sha256="):
            return False
        expected = hmac.new(
            self.settings.whatsapp_app_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature.removeprefix("sha256="), expected)

    async def close(self) -> None:
        await self.http.aclose()

    async def send_text(self, to: str, text: str) -> str:
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"preview_url": False, "body": text[:4096]},
            }
        )

    async def send_template(self, to: str, count: int, priority: str) -> str:
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {
                    "name": self.settings.whatsapp_template_name,
                    "language": {"code": self.settings.whatsapp_template_language},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": str(count)},
                                {"type": "text", "text": priority},
                            ],
                        }
                    ],
                },
            }
        )

    async def upload_image(self, content: bytes, filename: str = "risa-chart.png") -> str:
        if self.dry_run:
            return f"dry-media-{uuid.uuid4().hex}"
        response = await self.http.post(
            f"{self.base_url}/media",
            headers=self.headers,
            data={"messaging_product": "whatsapp", "type": "image/png"},
            files={"file": (filename, content, "image/png")},
        )
        response.raise_for_status()
        return str(response.json()["id"])

    async def send_image(self, to: str, content: bytes, caption: str) -> str:
        media_id = await self.upload_image(content)
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "image",
                "image": {"id": media_id, "caption": caption[:1024]},
            }
        )

    async def _send(self, payload: dict[str, Any]) -> str:
        if self.dry_run:
            return f"dry-message-{uuid.uuid4().hex}"
        response = await self.http.post(
            f"{self.base_url}/messages",
            headers={**self.headers, "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return str(data["messages"][0]["id"])
