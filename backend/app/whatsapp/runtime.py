from __future__ import annotations

import asyncio
import re
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

from app.config import Settings, settings
from app.llm.orchestrator import handle_chat
from app.state import AppState, state
from app.whatsapp.charts import render_chart_png, response_charts
from app.whatsapp.client import WhatsAppClient
from app.whatsapp.clinical_store import ClinicalStore
from app.whatsapp.formatting import agent_summary, alert_detail, alert_summary
from app.whatsapp.labels import clinical_label
from app.whatsapp.policy import NotificationPolicy
from app.whatsapp.reports import build_patient_report
from app.whatsapp.store import WhatsAppStore, normalize_phone
from app.whatsapp.twilio_verify import TwilioVerify

_PATIENT_ID = re.compile(r"PAT-[\dA-Z]{2,8}", re.I)


class WhatsAppRuntime:
    def __init__(
        self,
        config: Settings,
        app_state: AppState,
        store: WhatsAppStore | None = None,
        client: WhatsAppClient | None = None,
        clinical_store: ClinicalStore | None = None,
        verifier: TwilioVerify | None = None,
    ) -> None:
        self.settings = config
        self.state = app_state
        self.store = store or WhatsAppStore(config.whatsapp_db_path)
        self.client = client or WhatsAppClient(config)
        self.clinical = clinical_store or ClinicalStore(config.whatsapp_db_path)
        self.verifier = verifier or TwilioVerify(config)
        self.policy = NotificationPolicy(self.store, config)
        self.owner = uuid.uuid4().hex
        self.task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        contacts_path = Path(self.settings.patient_contacts_csv)
        if not contacts_path.is_absolute():
            contacts_path = Path(__file__).resolve().parents[2] / contacts_path
        if contacts_path.exists():
            known = set(self.state.dataset.patients["patient_id"].astype(str))
            self.clinical.import_contacts(contacts_path, known)
        for contact in self.store.list_contacts():
            if contact["role"] != "patient" or len(contact["patient_ids"]) != 1:
                continue
            trusted = self.clinical.trusted_contact(contact["patient_ids"][0])
            if not trusted or trusted["phone"] != contact["phone"]:
                self.store.deactivate_contact(contact["phone"])
        self.clinical.sync_alerts(self.state.alerts)
        if self.settings.whatsapp_enabled and self.task is None:
            self.task = asyncio.create_task(self._notification_loop(), name="risa-whatsapp")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        await self.client.close()
        await self.verifier.close()

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
                    clinical_label(payload["priority"]),
                )
                self.store.mark_outbox(item["id"], "sent", wa_message_id=message_id)
                self.store.add_message(
                    item["phone"],
                    "notification",
                    f"Actualización RISA: {payload['count']} caso(s), prioridad {clinical_label(payload['priority'])}",
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
            await self._process_enrollment(phone, text)
            return
        command = text.strip().upper()
        if command == "BAJA":
            self.store.set_opt_in(phone, False)
            self.store.close_session(phone)
            await self._send_and_store(phone, "🔕 Notificaciones desactivadas. Tu sesión también se cerró.")
            return
        if command == "RISA":
            self.store.open_session(phone)
            await self._send_menu(phone)
            return
        if command == "SALIR":
            self.store.close_session(phone)
            await self._send_and_store(phone, "🔒 Sesión cerrada. Las notificaciones autorizadas continúan activas.")
            return
        if command == "AYUDA":
            await self._send_help_list(phone)
            return
        if command == "MENU":
            await self._send_menu(phone)
            return
        if command == "SESSION_START":
            self.store.open_session(phone)
            await self._send_menu(phone)
            return
        if command in {"MENU_ALERTS", "MENU_VITALS", "MENU_PDF"}:
            self.store.open_session(phone)
        if not self.store.session_active(phone):
            await self._send_buttons_store(
                phone,
                "🔒 Tu sesión está cerrada. Pulsa el botón para iniciar.",
                [{"id": "SESSION_START", "title": "Iniciar RISA"}],
            )
            return
        allowed = {patient_id.upper() for patient_id in contact["patient_ids"]}
        if command == "MENU_ALERTS":
            await self._send_alerts(phone, allowed)
            return
        if command == "MENU_VITALS":
            await self._process_agent(phone, contact, "Genera un gráfico de mis constantes recientes")
            return
        if command == "MENU_PDF":
            await self._send_pdf(phone, allowed)
            return
        if command.startswith("ALERT_DETAIL:"):
            await self._send_alert_detail(phone, command.split(":", 1)[1], allowed)
            return
        if command.startswith("ALERT_CONFIRM:"):
            await self._confirm_alert(phone, command.split(":", 1)[1], allowed)
            return
        if command == "CONTACT_CLINICAL":
            await self._send_clinical_contact(phone, allowed)
            return
        requested = {match.group(0).upper() for match in _PATIENT_ID.finditer(text)}
        denied = requested - allowed
        if denied:
            await self._send_and_store(phone, "🔒 La consulta está fuera de tu alcance autorizado.")
            return
        await self._process_agent(phone, contact, text)

    async def _process_enrollment(self, phone: str, text: str) -> None:
        command = text.strip().upper()
        session = self.store.otp_session(phone)
        if command == "CONSENT_ACCEPT":
            try:
                contact = self.store.complete_otp_enrollment(phone, _timezone_for_phone(phone))
            except ValueError:
                await self._send_and_store(phone, "La verificación venció. Envía nuevamente tu código de paciente.")
                return
            self.store.open_session(phone)
            await self._send_and_store(
                phone,
                "✅ *Registro confirmado*\nTu número quedó vinculado y solo podrás consultar tus propios datos.",
            )
            await self._send_menu(phone)
            return
        if command == "CONSENT_DECLINE":
            self.store.cancel_otp(phone)
            await self._send_and_store(phone, "Registro cancelado. No se activaron consultas ni notificaciones.")
            return
        if session and session["status"] == "pending" and re.fullmatch(r"\d{4,10}", command):
            try:
                self.store.register_otp_check(phone, self.settings.otp_max_checks)
                approved = await self.verifier.check(phone, command)
            except Exception:  # noqa: BLE001
                approved = False
            if not approved:
                await self._send_and_store(phone, "Código incorrecto o vencido. Revisa el SMS e intenta nuevamente.")
                return
            self.store.mark_otp_verified(phone)
            await self._send_buttons_store(
                phone,
                "✅ SMS verificado.\n\nAl continuar autorizas vincular este número, procesar tus consultas "
                "y recibir notificaciones de seguimiento. Puedes usar BAJA cuando quieras.",
                [
                    {"id": "CONSENT_ACCEPT", "title": "Acepto"},
                    {"id": "CONSENT_DECLINE", "title": "Cancelar"},
                ],
            )
            return
        patient_match = _PATIENT_ID.fullmatch(command.removeprefix("REGISTRAR ").strip())
        if patient_match:
            patient_id = patient_match.group(0).upper()
            trusted = self.clinical.trusted_contact(patient_id)
            if not trusted or trusted["phone"] != phone:
                await self._generic_enrollment_failure(phone)
                return
            try:
                self.store.start_otp_session(
                    phone,
                    patient_id,
                    self.settings.otp_max_starts_hour,
                    self.settings.otp_session_minutes,
                )
                await self.verifier.start(phone)
            except Exception:  # noqa: BLE001
                await self._generic_enrollment_failure(phone)
                return
            await self._send_and_store(
                phone,
                "📱 Enviamos un código SMS al teléfono registrado.\n\nCópialo y pégalo aquí. Vence en 10 minutos.",
            )
            return
        await self._send_and_store(
            phone,
            "👋 *Bienvenido a RISA*\n\nPara proteger tu información, envía tu código de paciente, por ejemplo: PAT-0724.",
        )

    async def _generic_enrollment_failure(self, phone: str) -> None:
        await self._send_and_store(
            phone,
            "No pudimos iniciar la verificación. Revisa tus datos o contacta al equipo responsable.",
        )

    async def _process_agent(self, phone: str, contact: dict[str, Any], text: str) -> None:
        allowed = {patient_id.upper() for patient_id in contact["patient_ids"]}
        requested = {match.group(0).upper() for match in _PATIENT_ID.finditer(text)}
        query = text
        if text.strip().upper().startswith("GRAFICO"):
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
        await self._send_and_store(phone, agent_summary(response), trace=trace)
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
        await self._send_menu(phone, "¿Qué deseas revisar ahora?")

    async def _send_menu(self, phone: str, body: str = "👋 *RISA está listo*\nElige una opción:") -> None:
        await self._send_buttons_store(
            phone,
            body,
            [
                {"id": "MENU_ALERTS", "title": "🚨 Ver alertas"},
                {"id": "MENU_VITALS", "title": "📊 Constantes"},
                {"id": "MENU_PDF", "title": "📥 Informe PDF"},
            ],
        )

    async def _send_help_list(self, phone: str) -> None:
        rows = [
            {"id": "MENU_ALERTS", "title": "Alertas activas", "description": "Resumen y acciones"},
            {"id": "MENU_VITALS", "title": "Constantes", "description": "Gráficos recientes"},
            {"id": "MENU_PDF", "title": "Informe PDF", "description": "Descargar seguimiento"},
            {"id": "CONTACT_CLINICAL", "title": "Contacto clínico", "description": "Ver teléfono configurado"},
            {"id": "SALIR", "title": "Cerrar sesión", "description": "Mantiene notificaciones"},
            {"id": "BAJA", "title": "Dar de baja", "description": "Desactiva notificaciones"},
        ]
        message_id = await self.client.send_list(
            phone,
            "Selecciona una acción. También puedes escribir una pregunta sobre tus datos.",
            rows,
        )
        self.store.add_message(
            phone,
            "outbound",
            "Lista de ayuda RISA",
            wa_message_id=message_id,
            status="sent",
            trace={"interactive_list": [row["id"] for row in rows]},
        )

    async def _send_alerts(self, phone: str, allowed: set[str]) -> None:
        patient_id = next(iter(allowed))
        alerts = self.state.alerts_for_patient(patient_id)
        await self._send_and_store(phone, alert_summary(patient_id, alerts))
        if alerts:
            alert_id = str(alerts[0]["id"])
            await self._send_buttons_store(
                phone,
                "Acciones disponibles:",
                [
                    {"id": f"ALERT_DETAIL:{alert_id}", "title": "Ver detalle"},
                    {"id": f"ALERT_CONFIRM:{alert_id}", "title": "Confirmar lectura"},
                    {"id": "CONTACT_CLINICAL", "title": "Contactar médico"},
                ],
            )

    async def _send_alert_detail(self, phone: str, alert_id: str, allowed: set[str]) -> None:
        alert = self.state.alert_by_id(alert_id)
        if not alert or alert["patient_id"] not in allowed:
            await self._send_and_store(phone, "No se encontró una alerta autorizada.")
            return
        await self._send_and_store(phone, alert_detail(alert))

    async def _confirm_alert(self, phone: str, alert_id: str, allowed: set[str]) -> None:
        alert = self.state.alert_by_id(alert_id)
        if not alert or alert["patient_id"] not in allowed:
            await self._send_and_store(phone, "No se encontró una alerta autorizada.")
            return
        created = self.store.record_alert_action(phone, alert_id, "confirm_read")
        await self._send_and_store(
            phone,
            "✅ Lectura confirmada y registrada." if created else "✅ Esta lectura ya estaba confirmada.",
        )

    async def _send_clinical_contact(self, phone: str, allowed: set[str]) -> None:
        patient_id = next(iter(allowed))
        trusted = self.clinical.trusted_contact(patient_id) or {}
        clinical_phone = trusted.get("clinical_contact_phone") or self.settings.clinical_contact_phone
        if not clinical_phone:
            await self._send_and_store(
                phone,
                "No hay un teléfono clínico configurado. Si es una emergencia, usa los servicios locales de emergencia.",
            )
            return
        display_phone = _display_phone(str(clinical_phone))
        await self._send_and_store(
            phone,
            "📞 *Contacto médico*\n\n"
            "Te compartimos el número del Dr. responsable:\n"
            f"*{display_phone}*\n\n"
            "Puedes tocar el número para llamar. Si es una emergencia, utiliza los servicios de emergencia locales.",
            trace={"patient_id": patient_id, "action": "share_clinical_contact"},
        )

    async def _send_pdf(self, phone: str, allowed: set[str]) -> None:
        patient_id = next(iter(allowed))
        content = build_patient_report(self.state, patient_id)
        message_id = await self.client.send_document(
            phone,
            content,
            f"informe-risa-{patient_id}.pdf",
            "Informe de seguimiento RISA. Documento informativo, no diagnóstico.",
        )
        self.store.add_message(
            phone,
            "media",
            f"Informe PDF {patient_id}",
            wa_message_id=message_id,
            status="sent",
            trace={"patient_id": patient_id, "kind": "pdf"},
        )

    async def _send_buttons_store(
        self,
        phone: str,
        body: str,
        buttons: list[dict[str, str]],
    ) -> str:
        message_id = await self.client.send_buttons(phone, body, buttons)
        self.store.add_message(
            phone,
            "outbound",
            body,
            wa_message_id=message_id,
            status="sent",
            trace={"interactive_buttons": [button["id"] for button in buttons]},
        )
        return message_id

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
        if message.get("type") == "button":
            button = message.get("button") or {}
            return str(button.get("payload") or button.get("text") or "")
        interactive = message.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return str(reply.get("id") or reply.get("title") or "")


def _chunks(text: str, size: int = 3500) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)] or [""]


def _timezone_for_phone(phone: str) -> str:
    if phone.startswith("51"):
        return "America/Lima"
    if phone.startswith("593"):
        return "America/Guayaquil"
    return "UTC"


def _display_phone(phone: str) -> str:
    digits = normalize_phone(phone)
    if digits.startswith("51") and len(digits) == 11:
        return f"+51 {digits[2:5]} {digits[5:8]} {digits[8:]}"
    return f"+{digits}"


runtime = WhatsAppRuntime(settings, state)
