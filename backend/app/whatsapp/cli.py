from __future__ import annotations

import argparse
import asyncio
import json

from app.whatsapp.runtime import runtime


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Administración local de WhatsApp RISA")
    commands = root.add_subparsers(dest="command", required=True)

    register = commands.add_parser("register", help="registra o actualiza un contacto")
    register.add_argument("--phone", required=True, help="teléfono internacional, por ejemplo +593...")
    register.add_argument("--role", required=True, choices=("patient", "clinician"))
    register.add_argument("--patient", action="append", required=True, dest="patients")
    register.add_argument("--timezone", default="UTC")
    register.add_argument("--opt-in", action="store_true", help="confirma consentimiento para notificaciones")

    consent = commands.add_parser("consent", help="activa o desactiva notificaciones")
    consent.add_argument("--phone", required=True)
    consent.add_argument("--enabled", choices=("yes", "no"), required=True)

    invite = commands.add_parser("invite", help="crea un código temporal de autorregistro")
    invite.add_argument("--patient", required=True)
    invite.add_argument("--expires-hours", type=int, default=24)

    scan = commands.add_parser("scan", help="ejecuta el filtro y despacha el outbox")
    scan.add_argument("--include-baseline", action="store_true")

    audit = commands.add_parser("audit", help="muestra trazabilidad reciente")
    audit.add_argument("--phone")
    audit.add_argument("--limit", type=int, default=30)
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
    elif args.command == "invite":
        patient_id = args.patient.upper()
        known = set(runtime.state.dataset.patients["patient_id"].astype(str))
        if patient_id not in known:
            raise SystemExit(f"Paciente inexistente: {patient_id}")
        code = runtime.store.create_enrollment_code(patient_id, args.expires_hours)
        print(
            json.dumps(
                {
                    "patient_id": patient_id,
                    "code": code,
                    "expires_hours": args.expires_hours,
                    "instruction": f"Enviar por WhatsApp: REGISTRAR {code}",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "scan":
        asyncio.run(_scan(args.include_baseline))
    elif args.command == "audit":
        print(json.dumps(runtime.store.audit(args.phone, args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
