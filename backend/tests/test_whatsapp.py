from __future__ import annotations

import asyncio
import hashlib
import hmac
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.planning import CohortQueryService, deterministic_plan
from app.whatsapp.charts import render_chart_png
from app.whatsapp.client import WhatsAppClient
from app.whatsapp.clinical_store import ClinicalStore
from app.whatsapp.formatting import clean_whatsapp_text
from app.whatsapp.policy import NotificationPolicy
from app.whatsapp.reports import build_patient_report
from app.whatsapp.runtime import WhatsAppRuntime
from app.whatsapp.router import router
from app.whatsapp.store import WhatsAppStore
from app.whatsapp.twilio_verify import TwilioVerify


class FakeClient:
    dry_run = True

    def __init__(self) -> None:
        self.texts: list[tuple[str, str]] = []

    async def send_text(self, to: str, text: str) -> str:
        self.texts.append((to, text))
        return f"msg-{len(self.texts)}"

    async def send_template(self, to: str, count: int, priority: str) -> str:
        return f"template-{to}-{count}-{priority}"

    async def send_buttons(self, to: str, body: str, buttons, footer: str = "") -> str:
        self.texts.append((to, body))
        return f"buttons-{len(self.texts)}"

    async def send_list(self, to: str, body: str, rows, button_text: str = "") -> str:
        self.texts.append((to, body))
        return f"list-{len(self.texts)}"

    async def send_image(self, to: str, content: bytes, caption: str) -> str:
        return f"image-{to}-{len(content)}"

    async def send_document(self, to: str, content: bytes, filename: str, caption: str) -> str:
        return f"document-{to}-{len(content)}"

    async def send_contact(self, to: str, clinical_phone: str) -> str:
        return f"contact-{to}-{clinical_phone}"

    async def close(self) -> None:
        return None


class FakeVerifier:
    dry_run = False

    async def start(self, phone: str):
        return {"sid": "VE-test", "status": "pending"}

    async def check(self, phone: str, code: str) -> bool:
        return code == "123456"

    async def close(self) -> None:
        return None


class FakeApp:
    def __init__(self) -> None:
        self.dataset = type(
            "Dataset",
            (),
            {
                "patients": pd.DataFrame(
                    [{"patient_id": "PAT-0724"}, {"patient_id": "PAT-0290"}]
                ),
                "origin": "test",
                "vitals_for": lambda _, patient_id: pd.DataFrame(
                    [
                        {
                            "timestamp": pd.Timestamp("2026-08-01"),
                            "heart_rate": 75,
                            "spo2": 97,
                        }
                    ]
                ),
                "labs_for": lambda _, patient_id: pd.DataFrame(
                    [
                        {
                            "timestamp": pd.Timestamp("2026-08-01"),
                            "analyte": "LAB_C",
                            "value": 4.2,
                        }
                    ]
                ),
            },
        )()
        self.alerts = [
            {
                "id": "A-724",
                "patient_id": "PAT-0724",
                "level": "ALTO",
                "priority_level": "HIGH",
                "risk_score": 0.8,
                "anomaly_score": 0.7,
                "pattern_score": 0.7,
                "pattern": "test",
                "model_provenance": {"fingerprint": "model-1"},
            }
        ]

    def alerts_for_patient(self, patient_id: str):
        return [alert for alert in self.alerts if alert["patient_id"] == patient_id]

    def alert_by_id(self, alert_id: str):
        return next((alert for alert in self.alerts if alert["id"] == alert_id), None)


class WhatsAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "whatsapp.sqlite3")
        self.settings = Settings(
            _env_file=None,
            whatsapp_dry_run=True,
            whatsapp_app_secret="secret",
            whatsapp_db_path=self.db,
            whatsapp_quiet_start_hour=23,
            whatsapp_quiet_end_hour=23,
        )
        self.store = WhatsAppStore(self.db)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_contact_scope_and_session_are_persisted(self) -> None:
        contact = self.store.upsert_contact(
            "+593 999-999-999",
            "patient",
            ["PAT-0724"],
            True,
            "America/Guayaquil",
        )
        self.assertEqual(contact["phone"], "593999999999")
        self.assertEqual(contact["patient_ids"], ["PAT-0724"])
        self.store.open_session(contact["phone"])
        self.assertTrue(self.store.session_active(contact["phone"]))
        self.store.close_session(contact["phone"])
        self.assertFalse(self.store.session_active(contact["phone"]))

    def test_patient_requires_exactly_one_scope(self) -> None:
        with self.assertRaises(ValueError):
            self.store.upsert_contact("+593999999999", "patient", [], True)

    def test_patient_registers_with_trusted_phone_sms_and_consent(self) -> None:
        phone = "51946153327"
        contacts_path = Path(self.temp.name) / "contacts.csv"
        contacts_path.write_text(
            "patient_id,phone_e164,timezone,clinical_contact_phone\n"
            "PAT-0724,+51946153327,America/Lima,\n",
            encoding="utf-8",
        )
        clinical = ClinicalStore(self.db)
        clinical.import_contacts(contacts_path, {"PAT-0724", "PAT-0290"})
        client = FakeClient()
        runtime = WhatsAppRuntime(
            self.settings,
            FakeApp(),
            self.store,
            client,
            clinical_store=clinical,
            verifier=FakeVerifier(),
        )

        async def scenario() -> None:
            await runtime.process_message(
                {
                    "id": "enroll-1",
                    "from": phone,
                    "type": "text",
                    "text": {"body": "PAT-0724"},
                }
            )
            self.assertIsNone(self.store.get_contact(phone))
            await runtime.process_message(
                {
                    "id": "enroll-2",
                    "from": phone,
                    "type": "text",
                    "text": {"body": "123456"},
                }
            )
            self.assertIsNone(self.store.get_contact(phone))
            await runtime.process_message(
                {
                    "id": "enroll-3",
                    "from": phone,
                    "type": "interactive",
                    "interactive": {
                        "type": "button_reply",
                        "button_reply": {"id": "CONSENT_ACCEPT", "title": "Acepto"},
                    },
                }
            )

        asyncio.run(scenario())
        contact = self.store.get_contact(phone)
        self.assertEqual(contact["patient_ids"], ["PAT-0724"])
        self.assertTrue(contact["opted_in"])
        self.assertTrue(self.store.session_active(phone))

    def test_authorized_scope_intersects_query(self) -> None:
        app = FakeApp()
        service = CohortQueryService(app)
        plan = deterministic_plan("Dashboard PAT-0290", service.catalog())
        scope = service.resolve(plan, authorized_patient_ids={"PAT-0724"})
        self.assertEqual(scope.patient_ids, [])
        self.assertTrue(any("sin autorización" in warning for warning in scope.warnings))

    def test_signature_is_hmac_sha256(self) -> None:
        client = WhatsAppClient(self.settings)
        body = b'{"object":"whatsapp_business_account"}'
        digest = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        self.assertTrue(client.verify_signature(body, f"sha256={digest}"))
        self.assertFalse(client.verify_signature(body + b"x", f"sha256={digest}"))
        asyncio.run(client.close())

    def test_webhook_challenge_and_signature(self) -> None:
        config = Settings(
            _env_file=None,
            whatsapp_dry_run=True,
            whatsapp_app_secret="secret",
            whatsapp_verify_token="verify-me",
            whatsapp_db_path=self.db,
        )
        local_runtime = WhatsAppRuntime(
            config,
            FakeApp(),
            self.store,
            WhatsAppClient(config),
        )
        api = FastAPI()
        api.include_router(router)
        router_module = importlib.import_module("app.whatsapp.router")
        body = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()
        signature = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        with patch.object(router_module, "runtime", local_runtime):
            client = TestClient(api)
            response = client.get(
                "/api/whatsapp/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "verify-me",
                    "hub.challenge": "12345",
                },
            )
            self.assertEqual(response.text, "12345")
            self.assertEqual(
                client.post("/api/whatsapp/webhook", content=body).status_code,
                401,
            )
            accepted = client.post(
                "/api/whatsapp/webhook",
                content=body,
                headers={"X-Hub-Signature-256": f"sha256={signature}"},
            )
            self.assertEqual(accepted.json(), {"status": "accepted"})
        asyncio.run(local_runtime.client.close())

    def test_policy_baselines_then_notifies_escalation_once(self) -> None:
        contact = self.store.upsert_contact(
            "+593999999999", "patient", ["PAT-0724"], True
        )
        policy = NotificationPolicy(self.store, self.settings)
        app = FakeApp()
        self.assertEqual(policy.evaluate_contact(contact, app.alerts), [])
        escalated = [{**app.alerts[0], "level": "CRITICO", "priority_level": "CRITICAL", "risk_score": 0.95}]
        decisions = policy.evaluate_contact(contact, escalated)
        self.assertEqual(len(decisions), 1)
        self.assertTrue(policy.queue_digest(contact, decisions))
        self.assertFalse(policy.queue_digest(contact, decisions))

    def test_medium_requires_model_agreement(self) -> None:
        policy = NotificationPolicy(self.store, self.settings)
        alert = {
            "priority_level": "MEDIUM",
            "risk_score": 0.8,
            "anomaly_score": 0.8,
            "pattern_score": 0.2,
        }
        self.assertFalse(policy.eligible(alert))
        alert["pattern_score"] = 0.8
        self.assertTrue(policy.eligible(alert))

    def test_chart_is_rendered_locally_as_png(self) -> None:
        content = render_chart_png(
            {
                "data": [
                    {
                        "type": "bar",
                        "name": "alertas",
                        "x": ["CRITICO", "ALTO", "MEDIO"],
                        "y": [1, 2, 3],
                    }
                ],
                "layout": {"title": "Alertas por nivel"},
            }
        )
        self.assertTrue(content.startswith(b"\x89PNG"))
        self.assertLess(len(content), 5 * 1024 * 1024)

    def test_clinical_csv_sync_is_idempotent_and_imports_contact(self) -> None:
        raw = Path(self.temp.name) / "raw"
        master = raw / "01_master"
        master.mkdir(parents=True)
        (master / "patients.csv").write_text(
            "patient_id,age_years\nPAT-0724,64\n",
            encoding="utf-8",
        )
        contacts = Path(self.temp.name) / "contacts.csv"
        contacts.write_text(
            "patient_id,phone_e164,timezone,clinical_contact_phone\n"
            "PAT-0724,+51946153327,America/Lima,\n",
            encoding="utf-8",
        )
        clinical = ClinicalStore(self.db)
        first = clinical.sync_raw_csvs(raw)
        second = clinical.sync_raw_csvs(raw)
        self.assertEqual(first["01_master/patients.csv"], 1)
        self.assertEqual(second, {})
        self.assertEqual(clinical.import_contacts(contacts, {"PAT-0724"}), 1)
        self.assertEqual(clinical.trusted_contact("PAT-0724")["phone"], "51946153327")
        self.assertEqual(clinical.patient_profile("PAT-0724")["age_years"], 64)

    def test_whatsapp_formatting_removes_headings_and_translates_codes(self) -> None:
        text = clean_whatsapp_text(
            "### Resultado\n**Patrón:** PROGRESSIVE_MULTISOURCE\n- LAB_C"
        )
        self.assertNotIn("###", text)
        self.assertNotIn("**", text)
        self.assertIn("Tendencia progresiva en múltiples fuentes", text)
        self.assertIn("Marcador de laboratorio C", text)

    def test_pdf_report_is_generated_for_authorized_patient(self) -> None:
        content = build_patient_report(FakeApp(), "PAT-0724")
        self.assertTrue(content.startswith(b"%PDF"))

    def test_interactive_button_limits_are_enforced(self) -> None:
        client = WhatsAppClient(self.settings)
        with self.assertRaises(ValueError):
            asyncio.run(
                client.send_buttons(
                    "51946153327",
                    "Opciones",
                    [{"id": str(index), "title": "Opción"} for index in range(4)],
                )
            )
        asyncio.run(client.close())

    def test_notification_template_can_include_alert_quick_reply(self) -> None:
        captured = {}

        def handler(request):
            captured.update(json.loads(request.content))
            return httpx.Response(200, json={"messages": [{"id": "wamid-test"}]})

        config = Settings(
            _env_file=None,
            whatsapp_dry_run=False,
            whatsapp_app_secret="secret",
            whatsapp_access_token="token",
            whatsapp_phone_number_id="123",
            whatsapp_waba_id="456",
            whatsapp_verify_token="verify",
            whatsapp_template_quick_reply=True,
        )
        client = WhatsAppClient(config, transport=httpx.MockTransport(handler))

        async def scenario() -> None:
            await client.send_template("51946153327", 1, "Alta")
            await client.close()

        asyncio.run(scenario())
        button = captured["template"]["components"][-1]
        self.assertEqual(button["sub_type"], "quick_reply")
        self.assertEqual(button["parameters"][0]["payload"], "MENU_ALERTS")

    def test_twilio_verify_start_and_check(self) -> None:
        def handler(request):
            if request.url.path.endswith("/Verifications"):
                return httpx.Response(201, json={"sid": "VE123", "status": "pending"})
            return httpx.Response(200, json={"status": "approved"})

        config = Settings(
            _env_file=None,
            twilio_account_sid="AC123",
            twilio_auth_token="secret",
            twilio_verify_service_sid="VA123",
            twilio_dry_run=False,
        )
        verifier = TwilioVerify(config, transport=httpx.MockTransport(handler))

        async def scenario() -> None:
            started = await verifier.start("51946153327")
            self.assertEqual(started["status"], "pending")
            self.assertTrue(await verifier.check("51946153327", "123456"))
            await verifier.close()

        asyncio.run(scenario())

    def test_commands_require_session_and_preserve_authorization(self) -> None:
        phone = "593999999999"
        self.store.upsert_contact(phone, "patient", ["PAT-0724"], True)
        client = FakeClient()
        runtime = WhatsAppRuntime(self.settings, FakeApp(), self.store, client)

        async def scenario() -> None:
            await runtime.process_message({"id": "wamid-1", "from": phone, "type": "text", "text": {"body": "consulta"}})
            await runtime.process_message({"id": "wamid-2", "from": phone, "type": "text", "text": {"body": "RISA"}})
            response = {
                "content": "Respuesta PAT-0724",
                "charts": [],
                "risa_ui": None,
                "resolved_scope": {"patient_ids": ["PAT-0724"]},
            }
            with patch("app.whatsapp.runtime.handle_chat", new=AsyncMock(return_value=response)) as mocked:
                await runtime.process_message(
                    {"id": "wamid-3", "from": phone, "type": "text", "text": {"body": "mi estado"}}
                )
                self.assertEqual(mocked.await_args.kwargs["authorized_patient_ids"], {"PAT-0724"})

        asyncio.run(scenario())
        self.assertIn("sesión está cerrada", client.texts[0][1])
        self.assertIn("RISA está listo", client.texts[1][1])

    def test_alert_confirmation_is_idempotent_and_scoped(self) -> None:
        phone = "51946153327"
        self.store.upsert_contact(phone, "patient", ["PAT-0724"], True)
        self.store.open_session(phone)
        client = FakeClient()
        runtime = WhatsAppRuntime(
            self.settings,
            FakeApp(),
            self.store,
            client,
            verifier=FakeVerifier(),
        )

        async def scenario() -> None:
            message = {
                "from": phone,
                "type": "interactive",
                "interactive": {
                    "button_reply": {
                        "id": "ALERT_CONFIRM:A-724",
                        "title": "Confirmar lectura",
                    }
                },
            }
            await runtime.process_message({**message, "id": "confirm-1"})
            await runtime.process_message({**message, "id": "confirm-2"})

        asyncio.run(scenario())
        self.assertIn("registrada", client.texts[0][1])
        self.assertIn("ya estaba confirmada", client.texts[1][1])

    def test_webhook_event_is_idempotent(self) -> None:
        self.assertTrue(self.store.event_once("wamid-1"))
        self.assertFalse(self.store.event_once("wamid-1"))


if __name__ == "__main__":
    unittest.main()
