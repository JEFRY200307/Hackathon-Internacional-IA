from __future__ import annotations

import asyncio
import re
import uuid
from contextlib import suppress
from typing import Any

from app.config import Settings, settings
from app.llm.orchestrator import handle_chat
from app.state import AppState, state
from app.whatsapp.charts import render_chart_png, response_charts
from app.whatsapp.client import WhatsAppClient
from app.whatsapp.policy import NotificationPolicy
from app.whatsapp.store import WhatsAppStore, normalize_phone

_PATIENT_ID = re.compile(r"PAT-[\dA-Z]{2,8}", re.I)


class WhatsAppRuntime:
    def __init__(
        self,
        config: Settings,
        app_state: AppState,
        store: WhatsAppStore | None = None,
        client: WhatsAppClient | None = None,
    ) -> None:
        self.settings = config
        self.state = app_state
        self.store = store or WhatsAppStore(config.whatsapp_db_path)
        self.client = client or WhatsAppClient(config)
        self.policy = NotificationPolicy(self.store, config)
        self.owner = uuid.uuid4().hex
        self.task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self.settings.whatsapp_enabled and self.task is None:
            self.task = asyncio.create_task(self._notification_loop(), name="risa-whatsapp")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        await self.client.close()

    async def _notification_loop(self) -> None:
        while True:
            try:
                lease_seconds = max(30, self.settings.whatsapp_scan_seconds + 15)
                if self.store.acquire_lease("notification-scan", self.owner, lease_seconds):
                    await self.scan_notifications()
                    await self.dispatch_outbox()
            except Exception as exc:  # noqa: BLE001
                self.store.add_message(
                    "00000000",
                    "system",
                    "Fallo del ciclo de notificaciones",
                    trace={"error": str(exc)},
                )
            await asyncio.sleep(max(10, self.settings.whatsapp_scan_seconds))

    async def scan_notifications(self, allow_baseline: bool = False) -> int:
        queued = 0
        for contact in self.store.list_contacts(opted_in_only=True):
            decisions = self.policy.evaluate_contact(contact, self.state.alerts, allow_baseline)
            if self.policy.queue_digest(contact, decisions):
                queued += 1
        return queued

    async def dispatch_outbox(self) -> int:
        sent = 0
        for item in self.store.due_outbox():
            try:
                payload = item["payload"]
                message_id = await self.client.send_template(
                    item["phone"],
                    int(payload["count"]),
                    str(payload["priority"]),
                )
                self.store.mark_outbox(item["id"], "sent", wa_message_id=message_id)
                self.store.add_message(
                    item["phone"],
                    "notification",
                    f"Actualización RISA: {payload['count']} caso(s), prioridad {payload['priority']}",
                    wa_message_id=message_id,
                    status="sent",
                    trace={"outbox_id": item["id"], "patients": payload.get("patients", [])},
                )
                sent += 1
            except Exception as exc:  # noqa: BLE001
                status = "failed" if int(item["attempts"]) >= 2 else "retry"
                self.store.mark_outbox(item["id"], status, error=str(exc))
        return sent

    async def process_webhook(self, payload: dict[str, Any]) -> None:
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                for status in value.get("statuses") or []:
                    if status.get("id") and status.get("status"):
                        self.store.update_message_status(status["id"], status["status"])
                for message in value.get("messages") or []:
                    try:
                        await self.process_message(message)
                    except Exception as exc:  # noqa: BLE001
                        self.store.add_message(
                            "00000000",
                            "system",
                            "Fallo al procesar webhook entrante",
                            trace={"message_id": message.get("id"), "error": str(exc)},
                        )

    async def process_message(self, message: dict[str, Any]) -> None:
        message_id = str(message.get("id") or "")
        if not message_id or not self.store.event_once(message_id):
            return
        phone = normalize_phone(str(message.get("from") or ""))
        text = self._message_text(message).strip()
        if not text:
            await self._send_and_store(phone, "Solo puedo procesar texto y comandos RISA por ahora.")
            return
        self.store.add_message(phone, "inbound", text, wa_message_id=message_id, status="received")
        contact = self.store.get_contact(phone)
        if not contact or not contact["active"]:
            command = text.strip().upper()
            if command.startswith("REGISTRAR "):
                parts = command.split()
                if len(parts) != 2:
                    await self._send_and_store(phone, "Usa el formato REGISTRAR CODIGO.")
                    return
                try:
                    self.store.begin_enrollment(phone, parts[1])
                except ValueError:
                    await self._send_and_store(
                        phone,
                        "El código de registro es inválido, venció o ya fue utilizado.",
                    )
                    return
                await self._send_and_store(
                    phone,
                    "Código verificado. Al responder ACEPTO autorizas vincular este número con tu registro, "
                    "recibir notificaciones RISA y procesar tus mensajes según la política de privacidad. "
                    "Puedes cancelar después con BAJA.",
                )
                return
            if command == "ACEPTO":
                try:
                    contact = self.store.complete_enrollment(phone, _timezone_for_phone(phone))
                except ValueError:
                    await self._send_and_store(
                        phone,
                        "No existe un registro pendiente. Solicita un código y envía REGISTRAR CODIGO.",
                    )
                    return
                self.store.open_session(phone)
                await self._send_and_store(
                    phone,
                    "Registro y consentimiento confirmados. Tu sesión RISA está activa y solo permite consultar tus propios datos.",
                )
                return
            await self._send_and_store(
                phone,
                "Este número no está registrado. Solicita tu código personal y envía REGISTRAR CODIGO.",
            )
            return
        command = text.strip().upper()
        if command == "BAJA":
            self.store.set_opt_in(phone, False)
            self.store.close_session(phone)
            await self._send_and_store(phone, "Notificaciones desactivadas. Contacta al equipo para reactivarlas.")
            return
        if command == "RISA":
            self.store.open_session(phone)
            await self._send_and_store(
                phone,
                "Sesión RISA iniciada por 24 horas. Escribe AYUDA, realiza una consulta o usa GRAFICO seguido de tu solicitud.",
            )
            return
        if command == "SALIR":
            self.store.close_session(phone)
            await self._send_and_store(phone, "Sesión cerrada. Las notificaciones autorizadas continúan activas.")
            return
        if command == "AYUDA":
            await self._send_and_store(
                phone,
                "Comandos: RISA inicia sesión, GRAFICO crea una imagen, SALIR cierra el chat y BAJA desactiva notificaciones.",
            )
            return
        if not self.store.session_active(phone):
            await self._send_and_store(phone, "Escribe RISA para iniciar una conversación segura.")
            return
        allowed = {patient_id.upper() for patient_id in contact["patient_ids"]}
        requested = {match.group(0).upper() for match in _PATIENT_ID.finditer(text)}
        denied = requested - allowed
        if denied:
            await self._send_and_store(phone, "La consulta contiene pacientes fuera de tu alcance autorizado.")
            return
        query = text
        if command.startswith("GRAFICO"):
            query = "Genera un gráfico " + text[len("GRAFICO") :].strip()
        if contact["role"] == "patient" and not requested:
            query += f"\nAlcance solicitado: {next(iter(allowed))}"
        history = self.store.conversation(phone)
        if history and history[-1]["role"] == "user":
            history[-1]["content"] = query
        else:
            history.append({"role": "user", "content": query})
        try:
            response = await handle_chat(history, self.state, authorized_patient_ids=allowed)
        except Exception as exc:  # noqa: BLE001
            await self._send_and_store(
                phone,
                "No pude completar la consulta. Intenta nuevamente; si persiste, contacta al equipo responsable.",
                trace={"agent_error": str(exc)},
            )
            return
        trace = {
            key: response.get(key)
            for key in ("model", "degraded", "query_plan", "resolved_scope", "citations", "warnings", "tool_trace")
        }
        content = str(response.get("content") or "No fue posible completar la consulta.")
        for chunk in _chunks(content):
            await self._send_and_store(phone, chunk, trace=trace)
        for index, chart in enumerate(response_charts(response)):
            try:
                image = render_chart_png(chart)
                message_id = await self.client.send_image(
                    phone,
                    image,
                    f"Gráfico RISA {index + 1}. Apoyo a revisión; no constituye diagnóstico.",
                )
                self.store.add_message(
                    phone,
                    "media",
                    f"Gráfico RISA {index + 1}",
                    wa_message_id=message_id,
                    status="sent",
                    trace={"provenance": chart.get("provenance"), **trace},
                )
            except Exception as exc:  # noqa: BLE001
                await self._send_and_store(
                    phone,
                    "El gráfico no pudo renderizarse; la respuesta textual conserva la trazabilidad.",
                    trace={"chart_error": str(exc), **trace},
                )

    async def _send_and_store(
        self,
        phone: str,
        text: str,
        trace: dict[str, Any] | None = None,
    ) -> str:
        message_id = await self.client.send_text(phone, text)
        self.store.add_message(
            phone,
            "outbound",
            text,
            wa_message_id=message_id,
            status="sent",
            trace=trace,
        )
        return message_id

    @staticmethod
    def _message_text(message: dict[str, Any]) -> str:
        if message.get("type") == "text":
            return str((message.get("text") or {}).get("body") or "")
        interactive = message.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return str(reply.get("title") or reply.get("id") or "")


def _chunks(text: str, size: int = 3500) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)] or [""]


def _timezone_for_phone(phone: str) -> str:
    if phone.startswith("51"):
        return "America/Lima"
    if phone.startswith("593"):
        return "America/Guayaquil"
    return "UTC"


runtime = WhatsAppRuntime(settings, state)
