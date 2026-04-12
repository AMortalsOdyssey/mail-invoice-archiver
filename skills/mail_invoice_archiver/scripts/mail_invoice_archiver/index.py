from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .models import InvoiceMetadata


class ArchiveIndex:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        self.conn.close()

    def _ensure_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account TEXT NOT NULL,
                folder TEXT NOT NULL,
                message_uid TEXT NOT NULL,
                part_ref TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                received_at TEXT,
                sender TEXT,
                subject TEXT,
                preview TEXT,
                local_path TEXT,
                sha256 TEXT NOT NULL,
                mime_type TEXT,
                extension TEXT,
                invoice_number TEXT,
                invoice_code TEXT,
                amount_cents INTEGER,
                currency TEXT,
                invoice_date TEXT,
                vendor TEXT,
                business_key TEXT NOT NULL,
                status TEXT NOT NULL,
                duplicate_of_id INTEGER,
                extraction_sources TEXT,
                failure_reason TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(account, folder, message_uid, source_kind, part_ref)
            );
            CREATE INDEX IF NOT EXISTS idx_artifacts_business_key ON artifacts (business_key);
            CREATE INDEX IF NOT EXISTS idx_artifacts_invoice_number ON artifacts (invoice_number);
            """
        )
        self.conn.commit()

    def find_canonical(self, business_key: str) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT * FROM artifacts
            WHERE business_key = ? AND status IN ('saved', 'conflict') AND duplicate_of_id IS NULL
            ORDER BY id ASC
            LIMIT 1
            """,
            (business_key,),
        ).fetchone()

    def find_same_invoice_number(self, invoice_number: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT * FROM artifacts
                WHERE invoice_number = ? AND status IN ('saved', 'conflict') AND duplicate_of_id IS NULL
                ORDER BY id ASC
                """,
                (invoice_number,),
            ).fetchall()
        )

    def insert_artifact(
        self,
        *,
        account: str,
        folder: str,
        message_uid: str,
        part_ref: str,
        source_kind: str,
        source_ref: str,
        received_at: str | None,
        sender: str,
        subject: str,
        preview: str,
        local_path: str | None,
        sha256: str,
        mime_type: str,
        extension: str,
        metadata: InvoiceMetadata,
        business_key: str,
        status: str,
        duplicate_of_id: int | None,
        failure_reason: str | None = None,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT OR REPLACE INTO artifacts (
                account, folder, message_uid, part_ref, source_kind, source_ref,
                received_at, sender, subject, preview, local_path, sha256, mime_type,
                extension, invoice_number, invoice_code, amount_cents, currency,
                invoice_date, vendor, business_key, status, duplicate_of_id,
                extraction_sources, failure_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account,
                folder,
                message_uid,
                part_ref,
                source_kind,
                source_ref,
                received_at,
                sender,
                subject,
                preview,
                local_path,
                sha256,
                mime_type,
                extension,
                metadata.invoice_number,
                metadata.invoice_code,
                metadata.amount_cents,
                metadata.currency,
                metadata.invoice_date,
                metadata.vendor,
                business_key,
                status,
                duplicate_of_id,
                json.dumps(metadata.extraction_sources, ensure_ascii=False),
                failure_reason,
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def month_rows(self, month: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT * FROM artifacts
                WHERE substr(received_at, 1, 7) = ?
                ORDER BY received_at ASC, id ASC
                """,
                (month,),
            ).fetchall()
        )

    def month_summary(self, month: str, high_value_threshold: int) -> dict[str, object]:
        rows = self.month_rows(month)
        canonical = [row for row in rows if row["status"] == "saved" and row["duplicate_of_id"] is None]
        duplicates = [row for row in rows if row["status"] == "duplicate"]
        failures = [row for row in rows if row["status"] == "failed"]
        conflicts = [row for row in rows if row["status"] == "conflict"]
        unknown_amount = [row for row in canonical if row["amount_cents"] is None]
        total_amount_cents = sum(row["amount_cents"] or 0 for row in canonical)
        high_value = [row for row in canonical if (row["amount_cents"] or 0) >= high_value_threshold * 100]
        return {
            "month": month,
            "canonical_count": len(canonical),
            "duplicate_count": len(duplicates),
            "failure_count": len(failures),
            "conflict_count": len(conflicts),
            "unknown_amount_count": len(unknown_amount),
            "total_amount_cents": total_amount_cents,
            "high_value_threshold": high_value_threshold,
            "high_value": [dict(row) for row in high_value],
            "failures": [dict(row) for row in failures],
            "conflicts": [dict(row) for row in conflicts],
            "canonical_rows": [dict(row) for row in canonical],
        }
