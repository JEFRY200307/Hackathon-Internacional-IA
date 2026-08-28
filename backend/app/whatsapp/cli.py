from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.config import settings
from app.whatsapp.runtime import runtime


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Administración local de WhatsApp RISA")
    commands = root.add_subparsers(dest="command", required=True)

    register = commands.add_parser("register", help="registra o actualiza un contacto")
    register.add_argument("--phone", required=True, help="teléfono internacional, por ejemplo +593...")
    register.add_argument("--role", required=True, choices=("clinician",))
    register.add_argument("--patient", action="append", required=True, dest="patients")
    register.add_argument("--timezone", default="UTC")
    register.add_argument("--opt-in", action="store_true", help="confirma consentimiento para notificaciones")

    consent = commands.add_parser("consent", help="activa o desactiva notificaciones")
    consent.add_argument("--phone", required=True)
    consent.add_argument("--enabled", choices=("yes", "no"), required=True)

    scan = commands.add_parser("scan", help="ejecuta el filtro y despacha el outbox")
    scan.add_argument("--include-baseline", action="store_true")

    audit = commands.add_parser("audit", help="muestra trazabilidad reciente")
    audit.add_argument("--phone")
    audit.add_argument("--limit", type=int, default=30)
    audit.add_argument("--include-content", action="store_true")

    sync = commands.add_parser("sync-clinical-data", help="sincroniza CSV y contactos con SQLite")
    sync.add_argument("--raw-root")
    sync.add_argument("--contacts")

    commands.add_parser("twilio-status", help="valida configuración local de Twilio Verify")
    return root


async def _scan(include_baseline: bool) -> None:
    queued = await runtime.scan_notifications(allow_baseline=include_baseline)
    sent = await runtime.dispatch_outbox()
    print(json.dumps({"queued": queued, "sent": sent, "dry_run": runtime.client.dry_run}))
    await runtime.client.close()


def main() -> None:
    args = parser().parse_args()
    if args.command == "register":
        contact = runtime.store.upsert_contact(
            args.phone,
            args.role,
            args.patients,
            args.opt_in,
            args.timezone,
        )
        print(json.dumps(contact, ensure_ascii=False, indent=2))
    elif args.command == "consent":
        runtime.store.set_opt_in(args.phone, args.enabled == "yes")
        print(json.dumps({"phone": args.phone, "opted_in": args.enabled == "yes"}))
    elif args.command == "scan":
        asyncio.run(_scan(args.include_baseline))
    elif args.command == "audit":
        items = runtime.store.audit(args.phone, args.limit)
        if not args.include_content:
            for item in items:
                item["phone"] = "***" + str(item["phone"])[-4:]
                item["content"] = "[redacted]"
                item["trace"] = None
        print(json.dumps(items, ensure_ascii=False, indent=2))
    elif args.command == "sync-clinical-data":
        repository_root = Path(__file__).resolve().parents[3]
        raw_root = Path(args.raw_root) if args.raw_root else repository_root / "pipeline" / "data" / "raw"
        contacts = Path(args.contacts or settings.patient_contacts_csv)
        if not contacts.is_absolute():
            contacts = Path(__file__).resolve().parents[2] / contacts
        raw = runtime.clinical.sync_raw_csvs(raw_root)
        known = set(runtime.state.dataset.patients["patient_id"].astype(str))
        contacts_count = runtime.clinical.import_contacts(contacts, known)
        alerts_count = runtime.clinical.sync_alerts(runtime.state.alerts)
        print(
            json.dumps(
                {
                    "csv_updated": len(raw),
                    "rows_imported": sum(raw.values()),
                    "contacts": contacts_count,
                    "alerts": alerts_count,
                },
                indent=2,
            )
        )
    elif args.command == "twilio-status":
        print(
            json.dumps(
                {
                    "live_ready": settings.twilio_live_ready,
                    "dry_run": runtime.verifier.dry_run,
                    "verify_service_configured": bool(settings.twilio_verify_service_sid),
                }
            )
        )


if __name__ == "__main__":
    main()
