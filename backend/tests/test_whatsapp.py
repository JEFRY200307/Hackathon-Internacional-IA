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

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.planning import CohortQueryService, deterministic_plan
from app.whatsapp.charts import render_chart_png
from app.whatsapp.client import WhatsAppClient
from app.whatsapp.policy import NotificationPolicy
from app.whatsapp.runtime import WhatsAppRuntime
from app.whatsapp.router import router
from app.whatsapp.store import WhatsAppStore


class FakeClient:
    dry_run = True

    def __init__(self) -> None:
        self.texts: list[tuple[str, str]] = []

    async def send_text(self, to: str, text: str) -> str:
        self.texts.append((to, text))
        return f"msg-{len(self.texts)}"

    async def send_template(self, to: str, count: int, priority: str) -> str:
        return f"template-{to}-{count}-{priority}"

    async def send_image(self, to: str, content: bytes, caption: str) -> str:
        return f"image-{to}-{len(content)}"

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

    def test_patient_registers_from_whatsapp_with_single_use_code(self) -> None:
        phone = "51946153327"
        code = self.store.create_enrollment_code("PAT-0724")
        client = FakeClient()
        runtime = WhatsAppRuntime(self.settings, FakeApp(), self.store, client)

        async def scenario() -> None:
            await runtime.process_message(
                {
                    "id": "enroll-1",
                    "from": phone,
                    "type": "text",
                    "text": {"body": f"REGISTRAR {code}"},
                }
            )
            self.assertIsNone(self.store.get_contact(phone))
            await runtime.process_message(
                {
                    "id": "enroll-2",
                    "from": phone,
                    "type": "text",
                    "text": {"body": "ACEPTO"},
                }
            )

        asyncio.run(scenario())
        contact = self.store.get_contact(phone)
        self.assertEqual(contact["patient_ids"], ["PAT-0724"])
        self.assertTrue(contact["opted_in"])
        self.assertTrue(self.store.session_active(phone))
        with self.assertRaises(ValueError):
            self.store.begin_enrollment("51999999999", code)

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
        self.assertIn("Escribe RISA", client.texts[0][1])
        self.assertIn("Sesión RISA iniciada", client.texts[1][1])

    def test_webhook_event_is_idempotent(self) -> None:
        self.assertTrue(self.store.event_once("wamid-1"))
        self.assertFalse(self.store.event_once("wamid-1"))


if __name__ == "__main__":
    unittest.main()
