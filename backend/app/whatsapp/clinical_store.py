from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from app.whatsapp.store import normalize_phone, utc_now

_SAFE = re.compile(r"[^a-zA-Z0-9]+")


class ClinicalStore:
    """Repositorio SQLite derivado; los CSV/pipeline siguen siendo la fuente."""

    def __init__(self, db_path: str) -> None:
        path = Path(db_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def init_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS clinical_sources(
                    source_path TEXT PRIMARY KEY,
                    table_name TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    rows_imported INTEGER NOT NULL,
                    imported_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trusted_patient_phones(
                    patient_id TEXT PRIMARY KEY,
                    phone TEXT UNIQUE NOT NULL,
                    timezone TEXT NOT NULL DEFAULT 'UTC',
                    clinical_contact_phone TEXT,
                    source TEXT NOT NULL,
                    imported_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pipeline_alerts(
                    alert_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    synced_at TEXT NOT NULL
                );
                """
            )

    def sync_raw_csvs(self, raw_root: Path) -> dict[str, int]:
        results: dict[str, int] = {}
        for path in sorted(raw_root.rglob("*.csv")):
            relative = path.relative_to(raw_root).as_posix()
            table = "raw_" + _SAFE.sub("_", relative.removesuffix(".csv")).strip("_").lower()
            fingerprint = _file_fingerprint(path)
            with self.connect() as connection:
                current = connection.execute(
                    "SELECT fingerprint FROM clinical_sources WHERE source_path=?",
                    (relative,),
                ).fetchone()
            if current and current["fingerprint"] == fingerprint:
                continue
            rows = 0
            first = True
            with self.connect() as connection:
                for chunk in pd.read_csv(path, chunksize=50_000):
                    chunk.to_sql(table, connection, if_exists="replace" if first else "append", index=False)
                    rows += len(chunk)
                    first = False
                if first:
                    pd.read_csv(path).to_sql(table, connection, if_exists="replace", index=False)
                columns = {
                    row["name"]
                    for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
                }
                if "patient_id" in columns:
                    connection.execute(
                        f'CREATE INDEX IF NOT EXISTS "idx_{table}_patient" ON "{table}"(patient_id)'
                    )
                connection.execute(
                    """
                    INSERT INTO clinical_sources(source_path,table_name,fingerprint,rows_imported,imported_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(source_path) DO UPDATE SET
                        table_name=excluded.table_name,fingerprint=excluded.fingerprint,
                        rows_imported=excluded.rows_imported,imported_at=excluded.imported_at
                    """,
                    (relative, table, fingerprint, rows, utc_now().isoformat()),
                )
            results[relative] = rows
        return results

    def import_contacts(
        self,
        csv_path: Path,
        known_patient_ids: set[str],
    ) -> int:
        frame = pd.read_csv(csv_path, dtype=str).fillna("")
        required = {"patient_id", "phone_e164", "timezone", "clinical_contact_phone"}
        if not required.issubset(frame.columns):
            raise ValueError(f"faltan columnas: {', '.join(sorted(required - set(frame.columns)))}")
        records = []
        seen_phones: set[str] = set()
        for row in frame.to_dict(orient="records"):
            patient_id = row["patient_id"].strip().upper()
            if patient_id not in known_patient_ids:
                raise ValueError(f"paciente inexistente: {patient_id}")
            phone = normalize_phone(row["phone_e164"])
            if phone in seen_phones:
                raise ValueError("teléfono duplicado en el registro privado")
            seen_phones.add(phone)
            clinical_phone = (
                normalize_phone(row["clinical_contact_phone"])
                if row["clinical_contact_phone"].strip()
                else None
            )
            records.append(
                (
                    patient_id,
                    phone,
                    row["timezone"].strip() or "UTC",
                    clinical_phone,
                    csv_path.name,
                    utc_now().isoformat(),
                )
            )
        with self.connect() as connection:
            connection.execute("DELETE FROM trusted_patient_phones")
            connection.executemany(
                """
                INSERT INTO trusted_patient_phones(
                    patient_id,phone,timezone,clinical_contact_phone,source,imported_at
                ) VALUES(?,?,?,?,?,?)
                """,
                records,
            )
        return len(records)

    def sync_alerts(self, alerts: Iterable[dict[str, Any]]) -> int:
        now = utc_now().isoformat()
        values = [
            (
                str(alert["id"]),
                str(alert["patient_id"]),
                json.dumps(alert, ensure_ascii=False, default=str),
                now,
            )
            for alert in alerts
        ]
        with self.connect() as connection:
            connection.execute("DELETE FROM pipeline_alerts")
            connection.executemany(
                "INSERT INTO pipeline_alerts(alert_id,patient_id,payload_json,synced_at) VALUES(?,?,?,?)",
                values,
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pipeline_alerts_patient ON pipeline_alerts(patient_id)"
            )
        return len(values)

    def trusted_contact(self, patient_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM trusted_patient_phones WHERE patient_id=?",
                (patient_id.upper(),),
            ).fetchone()
        return dict(row) if row else None

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            sources = connection.execute(
                "SELECT COUNT(*) AS count,COALESCE(SUM(rows_imported),0) AS rows FROM clinical_sources"
            ).fetchone()
            contacts = connection.execute(
                "SELECT COUNT(*) AS count FROM trusted_patient_phones"
            ).fetchone()
            alerts = connection.execute(
                "SELECT COUNT(*) AS count FROM pipeline_alerts"
            ).fetchone()
        return {
            "sources": int(sources["count"]),
            "clinical_rows": int(sources["rows"]),
            "trusted_contacts": int(contacts["count"]),
            "alerts": int(alerts["count"]),
        }

    def patient_profile(self, patient_id: str) -> dict[str, Any] | None:
        table = self._source_table("01_master/patients.csv")
        if not table:
            return None
        with self.connect() as connection:
            row = connection.execute(
                f'SELECT * FROM "{table}" WHERE patient_id=? LIMIT 1',
                (patient_id.upper(),),
            ).fetchone()
        return dict(row) if row else None

    def patient_rows(self, source_suffix: str, patient_id: str, limit: int = 100) -> list[dict[str, Any]]:
        table = self._source_table(source_suffix)
        if not table:
            return []
        with self.connect() as connection:
            rows = connection.execute(
                f'SELECT * FROM "{table}" WHERE patient_id=? LIMIT ?',
                (patient_id.upper(), limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def _source_table(self, path: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT table_name FROM clinical_sources WHERE source_path=?",
                (path,),
            ).fetchone()
        return str(row["table_name"]) if row else None


def _file_fingerprint(path: Path) -> str:
    stat = path.stat()
    payload = f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.sha256(payload.encode()).hexdigest()
