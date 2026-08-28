from __future__ import annotations

import json
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if not 8 <= len(digits) <= 15:
        raise ValueError("el teléfono debe estar en formato internacional")
    return digits


class WhatsAppStore:
    def __init__(self, path: str) -> None:
        db_path = Path(path)
        if not db_path.is_absolute():
            db_path = Path(__file__).resolve().parents[2] / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(db_path)
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def init_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS contacts (
                    phone TEXT PRIMARY KEY,
                    role TEXT NOT NULL CHECK(role IN ('patient','clinician')),
                    patient_ids TEXT NOT NULL DEFAULT '[]',
                    opted_in INTEGER NOT NULL DEFAULT 0,
                    timezone TEXT NOT NULL DEFAULT 'UTC',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    phone TEXT PRIMARY KEY REFERENCES contacts(phone),
                    active_until TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS enrollment_codes (
                    code_hash TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    claimed_phone TEXT,
                    claimed_at TEXT,
                    used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS pending_enrollments (
                    phone TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    code_hash TEXT NOT NULL REFERENCES enrollment_codes(code_hash),
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    wa_message_id TEXT UNIQUE,
                    status TEXT,
                    trace_json TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_phone ON messages(phone, id);
                CREATE TABLE IF NOT EXISTS webhook_events (
                    event_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alert_state (
                    phone TEXT NOT NULL,
                    patient_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    priority_rank INTEGER NOT NULL,
                    risk_score REAL NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_notified_at TEXT,
                    notification_day TEXT,
                    notification_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(phone, patient_id)
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    dedupe_key TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    available_at TEXT NOT NULL,
                    wa_message_id TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS leases (
                    name TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                """
            )

    def create_enrollment_code(self, patient_id: str, hours: int = 24) -> str:
        code = secrets.token_hex(4).upper()
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO enrollment_codes(code_hash,patient_id,expires_at)
                VALUES(?,?,?)
                """,
                (
                    code_hash,
                    patient_id.upper(),
                    (utc_now() + timedelta(hours=hours)).isoformat(),
                ),
            )
        return code

    def begin_enrollment(self, phone: str, code: str) -> str:
        phone = normalize_phone(phone)
        code_hash = hashlib.sha256(code.strip().upper().encode()).hexdigest()
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM enrollment_codes WHERE code_hash=?",
                (code_hash,),
            ).fetchone()
            if (
                not row
                or row["used_at"]
                or datetime.fromisoformat(row["expires_at"]) <= now
                or (row["claimed_phone"] and row["claimed_phone"] != phone)
            ):
                raise ValueError("código inválido, vencido o ya utilizado")
            connection.execute(
                """
                UPDATE enrollment_codes SET claimed_phone=?,claimed_at=?
                WHERE code_hash=?
                """,
                (phone, now.isoformat(), code_hash),
            )
            connection.execute(
                """
                INSERT INTO pending_enrollments(phone,patient_id,code_hash,expires_at)
                VALUES(?,?,?,?)
                ON CONFLICT(phone) DO UPDATE SET
                    patient_id=excluded.patient_id,code_hash=excluded.code_hash,
                    expires_at=excluded.expires_at
                """,
                (phone, row["patient_id"], code_hash, row["expires_at"]),
            )
        return str(row["patient_id"])

    def complete_enrollment(self, phone: str, timezone_name: str = "UTC") -> dict[str, Any]:
        phone = normalize_phone(phone)
        now = utc_now()
        with self.connect() as connection:
            pending = connection.execute(
                "SELECT * FROM pending_enrollments WHERE phone=?",
                (phone,),
            ).fetchone()
            if not pending or datetime.fromisoformat(pending["expires_at"]) <= now:
                raise ValueError("no existe un registro pendiente válido")
            updated = connection.execute(
                """
                UPDATE enrollment_codes SET used_at=?
                WHERE code_hash=? AND claimed_phone=? AND used_at IS NULL
                """,
                (now.isoformat(), pending["code_hash"], phone),
            )
            if updated.rowcount != 1:
                raise ValueError("el código ya fue utilizado")
            patient_id = str(pending["patient_id"])
            connection.execute("DELETE FROM pending_enrollments WHERE phone=?", (phone,))
        return self.upsert_contact(phone, "patient", [patient_id], True, timezone_name)

    def upsert_contact(
        self,
        phone: str,
        role: str,
        patient_ids: list[str],
        opted_in: bool,
        timezone_name: str = "UTC",
    ) -> dict[str, Any]:
        phone = normalize_phone(phone)
        if role not in {"patient", "clinician"}:
            raise ValueError("rol inválido")
        ids = sorted({patient_id.upper() for patient_id in patient_ids})
        if role == "patient" and len(ids) != 1:
            raise ValueError("un contacto patient debe tener exactamente un PAT-ID")
        now = utc_now().isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO contacts(phone, role, patient_ids, opted_in, timezone, active, created_at, updated_at)
                VALUES(?,?,?,?,?,1,?,?)
                ON CONFLICT(phone) DO UPDATE SET
                    role=excluded.role, patient_ids=excluded.patient_ids,
                    opted_in=excluded.opted_in, timezone=excluded.timezone,
                    active=1, updated_at=excluded.updated_at
                """,
                (phone, role, json.dumps(ids), int(opted_in), timezone_name, now, now),
            )
        return self.get_contact(phone) or {}

    def get_contact(self, phone: str) -> dict[str, Any] | None:
        phone = normalize_phone(phone)
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM contacts WHERE phone=?", (phone,)).fetchone()
        if not row:
            return None
        value = dict(row)
        value["patient_ids"] = json.loads(value["patient_ids"])
        value["opted_in"] = bool(value["opted_in"])
        value["active"] = bool(value["active"])
        return value

    def list_contacts(self, opted_in_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM contacts WHERE active=1"
        if opted_in_only:
            query += " AND opted_in=1"
        with self.connect() as connection:
            phones = [row["phone"] for row in connection.execute(query).fetchall()]
        return [contact for phone in phones if (contact := self.get_contact(phone))]

    def set_opt_in(self, phone: str, enabled: bool) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE contacts SET opted_in=?, updated_at=? WHERE phone=?",
                (int(enabled), utc_now().isoformat(), normalize_phone(phone)),
            )

    def open_session(self, phone: str, hours: int = 24) -> None:
        phone = normalize_phone(phone)
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(phone, active_until, updated_at) VALUES(?,?,?)
                ON CONFLICT(phone) DO UPDATE SET active_until=excluded.active_until, updated_at=excluded.updated_at
                """,
                (phone, (now + timedelta(hours=hours)).isoformat(), now.isoformat()),
            )

    def close_session(self, phone: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE sessions SET active_until=NULL, updated_at=? WHERE phone=?",
                (utc_now().isoformat(), normalize_phone(phone)),
            )

    def session_active(self, phone: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT active_until FROM sessions WHERE phone=?", (normalize_phone(phone),)
            ).fetchone()
        return bool(row and row["active_until"] and datetime.fromisoformat(row["active_until"]) > utc_now())

    def event_once(self, event_id: str) -> bool:
        try:
            with self.connect() as connection:
                connection.execute(
                    "INSERT INTO webhook_events(event_id, created_at) VALUES(?,?)",
                    (event_id, utc_now().isoformat()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def add_message(
        self,
        phone: str,
        direction: str,
        content: str,
        wa_message_id: str | None = None,
        status: str | None = None,
        trace: dict[str, Any] | None = None,
    ) -> None:
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO messages(phone,direction,content,wa_message_id,status,trace_json,created_at)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        normalize_phone(phone),
                        direction,
                        content,
                        wa_message_id,
                        status,
                        json.dumps(trace, ensure_ascii=False, default=str) if trace else None,
                        utc_now().isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            return

    def update_message_status(self, wa_message_id: str, status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE messages SET status=? WHERE wa_message_id=?",
                (status, wa_message_id),
            )
            connection.execute(
                "UPDATE outbox SET status=? WHERE wa_message_id=?",
                (status, wa_message_id),
            )

    def conversation(self, phone: str, limit: int = 20) -> list[dict[str, str]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT direction, content FROM messages
                WHERE phone=? AND direction IN ('inbound','outbound') AND content <> ''
                ORDER BY id DESC LIMIT ?
                """,
                (normalize_phone(phone), limit),
            ).fetchall()
        return [
            {"role": "user" if row["direction"] == "inbound" else "assistant", "content": row["content"]}
            for row in reversed(rows)
        ]

    def audit(self, phone: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = "SELECT * FROM messages"
        params: list[Any] = []
        if phone:
            query += " WHERE phone=?"
            params.append(normalize_phone(phone))
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["trace"] = json.loads(item.pop("trace_json")) if item.get("trace_json") else None
            output.append(item)
        return output

    def alert_state(self, phone: str, patient_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM alert_state WHERE phone=? AND patient_id=?",
                (normalize_phone(phone), patient_id),
            ).fetchone()
        return dict(row) if row else None

    def save_alert_state(
        self,
        phone: str,
        patient_id: str,
        fingerprint: str,
        priority_rank: int,
        risk_score: float,
        notified: bool = False,
    ) -> None:
        phone = normalize_phone(phone)
        now = utc_now()
        previous = self.alert_state(phone, patient_id)
        day = now.date().isoformat()
        count = 0
        if previous and previous.get("notification_day") == day:
            count = int(previous["notification_count"])
        if notified:
            count += 1
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO alert_state(
                    phone,patient_id,fingerprint,priority_rank,risk_score,first_seen_at,last_seen_at,
                    last_notified_at,notification_day,notification_count
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(phone,patient_id) DO UPDATE SET
                    fingerprint=excluded.fingerprint, priority_rank=excluded.priority_rank,
                    risk_score=excluded.risk_score, last_seen_at=excluded.last_seen_at,
                    last_notified_at=COALESCE(excluded.last_notified_at,alert_state.last_notified_at),
                    notification_day=excluded.notification_day,
                    notification_count=excluded.notification_count
                """,
                (
                    phone,
                    patient_id,
                    fingerprint,
                    priority_rank,
                    risk_score,
                    previous["first_seen_at"] if previous else now.isoformat(),
                    now.isoformat(),
                    now.isoformat() if notified else None,
                    day,
                    count,
                ),
            )

    def queue(self, phone: str, kind: str, payload: dict[str, Any], dedupe_key: str) -> bool:
        try:
            now = utc_now().isoformat()
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO outbox(phone,kind,payload_json,dedupe_key,available_at,created_at)
                    VALUES(?,?,?,?,?,?)
                    """,
                    (normalize_phone(phone), kind, json.dumps(payload, ensure_ascii=False), dedupe_key, now, now),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def due_outbox(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM outbox
                WHERE status IN ('pending','retry') AND available_at<=?
                ORDER BY id LIMIT ?
                """,
                (utc_now().isoformat(), limit),
            ).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            values.append(item)
        return values

    def mark_outbox(
        self,
        item_id: int,
        status: str,
        wa_message_id: str | None = None,
        error: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE outbox SET status=?, wa_message_id=COALESCE(?,wa_message_id),
                    last_error=?, attempts=attempts+1,
                    available_at=?
                WHERE id=?
                """,
                (
                    status,
                    wa_message_id,
                    error,
                    (utc_now() + timedelta(minutes=5)).isoformat(),
                    item_id,
                ),
            )

    def acquire_lease(self, name: str, owner: str, seconds: int) -> bool:
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM leases WHERE name=?", (name,)).fetchone()
            if row and datetime.fromisoformat(row["expires_at"]) > now and row["owner"] != owner:
                return False
            connection.execute(
                """
                INSERT INTO leases(name,owner,expires_at) VALUES(?,?,?)
                ON CONFLICT(name) DO UPDATE SET owner=excluded.owner,expires_at=excluded.expires_at
                """,
                (name, owner, (now + timedelta(seconds=seconds)).isoformat()),
            )
        return True
