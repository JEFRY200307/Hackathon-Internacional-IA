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

    async def send_buttons(
        self,
        to: str,
        body: str,
        buttons: list[dict[str, str]],
        footer: str = "RISA Signal · Apoyo clínico",
    ) -> str:
        if not 1 <= len(buttons) <= 3:
            raise ValueError("WhatsApp admite entre 1 y 3 botones de respuesta")
        if any(len(button["title"]) > 20 for button in buttons):
            raise ValueError("el título de un botón supera 20 caracteres")
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": body[:1024]},
                    "footer": {"text": footer[:60]},
                    "action": {
                        "buttons": [
                            {
                                "type": "reply",
                                "reply": {"id": button["id"][:256], "title": button["title"]},
                            }
                            for button in buttons
                        ]
                    },
                },
            }
        )

    async def send_list(
        self,
        to: str,
        body: str,
        rows: list[dict[str, str]],
        button_text: str = "Ver opciones",
    ) -> str:
        if not 1 <= len(rows) <= 10:
            raise ValueError("la lista debe contener entre 1 y 10 opciones")
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "body": {"text": body[:4096]},
                    "action": {
                        "button": button_text[:20],
                        "sections": [
                            {
                                "title": "Opciones RISA",
                                "rows": [
                                    {
                                        "id": row["id"][:200],
                                        "title": row["title"][:24],
                                        "description": row.get("description", "")[:72],
                                    }
                                    for row in rows
                                ],
                            }
                        ],
                    },
                },
            }
        )

    async def send_template(self, to: str, count: int, priority: str) -> str:
        components: list[dict[str, Any]] = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(count)},
                    {"type": "text", "text": priority},
                ],
            }
        ]
        if self.settings.whatsapp_template_quick_reply:
            components.append(
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": "0",
                    "parameters": [{"type": "payload", "payload": "MENU_ALERTS"}],
                }
            )
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {
                    "name": self.settings.whatsapp_template_name,
                    "language": {"code": self.settings.whatsapp_template_language},
                    "components": components,
                },
            }
        )

    async def upload_image(self, content: bytes, filename: str = "risa-chart.png") -> str:
        return await self.upload_media(content, filename, "image/png")

    async def upload_media(self, content: bytes, filename: str, mime_type: str) -> str:
        if self.dry_run:
            return f"dry-media-{uuid.uuid4().hex}"
        response = await self.http.post(
            f"{self.base_url}/media",
            headers=self.headers,
            data={"messaging_product": "whatsapp", "type": mime_type},
            files={"file": (filename, content, mime_type)},
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

    async def send_document(
        self,
        to: str,
        content: bytes,
        filename: str,
        caption: str,
    ) -> str:
        media_id = await self.upload_media(content, filename, "application/pdf")
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "document",
                "document": {
                    "id": media_id,
                    "filename": filename,
                    "caption": caption[:1024],
                },
            }
        )

    async def send_contact(self, to: str, clinical_phone: str) -> str:
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "contacts",
                "contacts": [
                    {
                        "name": {"formatted_name": "Contacto clínico RISA"},
                        "phones": [
                            {
                                "phone": f"+{clinical_phone}",
                                "type": "WORK",
                                "wa_id": clinical_phone,
                            }
                        ],
                    }
                ],
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
