from __future__ import annotations

import json
import mimetypes
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from .config import RuntimeConfig
from .extractors import extract_invoice_metadata, infer_business_key, sha256_bytes
from .index import ArchiveIndex
from .models import AttachmentPayload, DeliveryResult, ImportResult, InvoiceMetadata, ParsedMessage

FINAL_EXPORT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
SKIPPED_ONLY_EXTENSIONS = {"ofd", "xml", "zip"}


def run_doctor(config: RuntimeConfig) -> dict[str, object]:
    return {
        "workflow": "browser-webmail",
        "source_of_truth": "mailbox web UI and downloaded files",
        "protocol_sync_enabled": False,
        "archive_root": str(config.archive_root),
        "database_path": str(config.database_path),
        "ocr": {
            "tesseract": bool(shutil.which("tesseract")),
            "ocrmypdf": bool(shutil.which("ocrmypdf")),
        },
        "notes": [
            "Use the provider webmail UI to search and download invoice files.",
            "Do not use protocol-level mailbox sync for discovery or completeness checks.",
            "Import only downloaded files with import-files.",
        ],
    }


def webmail_checklist(from_month: str | None = None, to_month: str | None = None) -> dict[str, object]:
    return {
        "date_range": {"from_month": from_month, "to_month": to_month},
        "workflow": [
            "Open the user's authenticated webmail session in the browser.",
            "Use the webmail UI, calendar/date filters, full-text search, and attachment indicators as the source of truth.",
            "Search each month boundary explicitly; do not assume one search page or one folder is complete.",
            "Use invoice keywords, sender names visible in webmail, and attachment filters to find candidates.",
            "Open candidate messages and download original PDF or image invoice attachments when available.",
            "Do not download OFD-only candidates into the final source set; record them as skipped.",
            "Put downloaded files into a temporary month source folder, then run import-files on that folder.",
        ],
        "keywords": ["发票", "电子发票", "invoice", "票据", "普票", "专票"],
    }


def import_files(
    config: RuntimeConfig,
    month: str,
    source_dir: Path,
    *,
    recursive: bool = True,
) -> ImportResult:
    if not source_dir.exists() or not source_dir.is_dir():
        raise RuntimeError(f"source directory does not exist: {source_dir}")

    config.archive_root.mkdir(parents=True, exist_ok=True)
    index = ArchiveIndex(config.database_path)
    result = ImportResult(month=month)
    try:
        files = _iter_source_files(source_dir, recursive=recursive)
        attachments: list[tuple[Path, AttachmentPayload]] = []
        for file_path in files:
            result.scanned_files += 1
            attachment = _attachment_from_file(file_path)
            if attachment.extension not in config.candidate_extensions:
                status = _record_skipped(
                    index,
                    month,
                    file_path,
                    attachment,
                    "unsupported file extension",
                )
                _apply_status(result, status)
                continue
            attachments.append((file_path, attachment))

        for file_path, attachment in _select_final_files(attachments):
            status = _store_attachment(config, index, month, file_path, attachment)
            _apply_status(result, status)

        for file_path, attachment in _skipped_non_final_files(attachments):
            reason = f"{attachment.extension.upper()}-only candidate skipped; no usable PDF/image invoice"
            status = _record_skipped(index, month, file_path, attachment, reason)
            _apply_status(result, status)
    finally:
        index.close()
    return result


def build_report(config: RuntimeConfig, month: str) -> dict[str, object]:
    index = ArchiveIndex(config.database_path)
    try:
        return index.month_summary(month, config.high_value_threshold)
    finally:
        index.close()


def pack_month(config: RuntimeConfig, month: str) -> DeliveryResult:
    summary = build_report(config, month)
    export_dir = config.archive_root / "_exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    month_dir = config.archive_root / month
    if not month_dir.exists():
        raise RuntimeError(f"No local archive exists for {month}")

    zip_path = export_dir / f"{month}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(month_dir.glob("*")):
            if file_path.is_file():
                zf.write(file_path, arcname=file_path.name)

    summary_path = export_dir / f"{month}-summary.md"
    summary_json_path = export_dir / f"{month}-summary.json"
    summary_path.write_text(render_summary_markdown(summary), encoding="utf-8")
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return DeliveryResult(
        month=month,
        zip_path=str(zip_path),
        summary_path=str(summary_path),
        summary_json_path=str(summary_json_path),
    )


def render_summary_markdown(summary: dict[str, object]) -> str:
    total_amount = cents_to_currency(summary["total_amount_cents"])
    lines = [
        f"# {summary['month']} 发票摘要",
        "",
        f"- 总笔数：{summary['canonical_count']}",
        f"- 总金额：{total_amount}",
        f"- 重复去重数：{summary['duplicate_count']}",
        f"- 异常冲突数：{summary['conflict_count']}",
        f"- 金额待确认数：{summary['unknown_amount_count']}",
        f"- 跳过/失败数：{summary['failure_count']}",
        "",
    ]
    failures = summary["failures"]
    if failures:
        lines.extend(["## 跳过或失败项", ""])
        for row in failures:
            lines.append(
                f"- {row['source_ref']}: {row['failure_reason'] or 'unknown error'}"
            )
        lines.append("")
    return "\n".join(lines)


def _iter_source_files(source_dir: Path, *, recursive: bool) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    return sorted(path for path in source_dir.glob(pattern) if path.is_file() and not path.name.startswith("."))


def _attachment_from_file(file_path: Path) -> AttachmentPayload:
    data = file_path.read_bytes()
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return AttachmentPayload(
        part_ref=f"file-{sha256_bytes(str(file_path).encode())[:12]}",
        filename=file_path.name,
        content_type=content_type,
        data=data,
        source_kind="webmail-download",
        source_ref=str(file_path),
    )


def _select_final_files(
    attachments: list[tuple[Path, AttachmentPayload]]
) -> list[tuple[Path, AttachmentPayload]]:
    grouped: dict[str, tuple[InvoiceMetadata, Path, AttachmentPayload]] = {}
    for file_path, attachment in attachments:
        if attachment.extension not in FINAL_EXPORT_EXTENSIONS:
            continue
        metadata = _metadata_for_local_file(attachment)
        business_key = infer_business_key(metadata, sha256_bytes(attachment.data))
        current = grouped.get(business_key)
        if current is None:
            grouped[business_key] = (metadata, file_path, attachment)
            continue
        _, _, existing_attachment = current
        if _attachment_preference_score(attachment.extension) > _attachment_preference_score(existing_attachment.extension):
            grouped[business_key] = (metadata, file_path, attachment)
    return [(file_path, attachment) for _, file_path, attachment in grouped.values()]


def _skipped_non_final_files(
    attachments: list[tuple[Path, AttachmentPayload]]
) -> list[tuple[Path, AttachmentPayload]]:
    final_keys: set[str] = set()
    for _, attachment in attachments:
        if attachment.extension in FINAL_EXPORT_EXTENSIONS:
            metadata = _metadata_for_local_file(attachment)
            final_keys.add(infer_business_key(metadata, sha256_bytes(attachment.data)))

    skipped: list[tuple[Path, AttachmentPayload]] = []
    for file_path, attachment in attachments:
        if attachment.extension not in SKIPPED_ONLY_EXTENSIONS:
            continue
        metadata = _metadata_for_local_file(attachment)
        key = infer_business_key(metadata, sha256_bytes(attachment.data))
        if key not in final_keys:
            skipped.append((file_path, attachment))
    return skipped


def _metadata_for_local_file(attachment: AttachmentPayload) -> InvoiceMetadata:
    message = ParsedMessage(
        uid=sha256_bytes((attachment.source_ref or attachment.filename).encode())[:16],
        account="webmail",
        folder="browser-download",
        received_at=None,
        sender="webmail",
        subject=attachment.filename,
        preview=attachment.filename,
        body_text="",
        attachments=[attachment],
    )
    return extract_invoice_metadata(message, attachment)


def _store_attachment(
    config: RuntimeConfig,
    index: ArchiveIndex,
    month: str,
    file_path: Path,
    attachment: AttachmentPayload,
) -> dict[str, object]:
    metadata = _metadata_for_local_file(attachment)
    content_sha = sha256_bytes(attachment.data)
    business_key = infer_business_key(metadata, content_sha)
    extension = attachment.extension.lower()

    if extension not in FINAL_EXPORT_EXTENSIONS:
        return _record_skipped(
            index,
            month,
            file_path,
            attachment,
            f"{extension.upper()}-only candidate skipped; no usable PDF/image invoice",
        )

    if metadata.invoice_number:
        same_number = index.find_same_invoice_number(metadata.invoice_number)
        for row in same_number:
            if row["amount_cents"] == metadata.amount_cents and metadata.amount_cents is not None:
                artifact_id = index.insert_artifact(
                    account="webmail",
                    folder="browser-download",
                    message_uid=sha256_bytes(str(file_path).encode())[:16],
                    part_ref=attachment.part_ref,
                    source_kind=attachment.source_kind,
                    source_ref=attachment.source_ref or attachment.filename,
                    received_at=_received_at(month),
                    sender="webmail",
                    subject=attachment.filename,
                    preview=attachment.filename,
                    local_path=None,
                    sha256=content_sha,
                    mime_type=attachment.content_type,
                    extension=extension,
                    metadata=metadata,
                    business_key=business_key,
                    status="duplicate",
                    duplicate_of_id=row["id"],
                )
                return {"status": "duplicate", "id": artifact_id, "local_path": None}
        if same_number and any(row["amount_cents"] != metadata.amount_cents for row in same_number):
            local_path = _write_artifact(config, month, file_path, attachment)
            artifact_id = index.insert_artifact(
                account="webmail",
                folder="browser-download",
                message_uid=sha256_bytes(str(file_path).encode())[:16],
                part_ref=attachment.part_ref,
                source_kind=attachment.source_kind,
                source_ref=attachment.source_ref or attachment.filename,
                received_at=_received_at(month),
                sender="webmail",
                subject=attachment.filename,
                preview=attachment.filename,
                local_path=str(local_path),
                sha256=content_sha,
                mime_type=attachment.content_type,
                extension=extension,
                metadata=metadata,
                business_key=business_key,
                status="conflict",
                duplicate_of_id=None,
                failure_reason="same invoice number with different amount",
            )
            return {"status": "conflict", "id": artifact_id, "local_path": str(local_path)}

    existing = index.find_canonical(business_key)
    if existing:
        artifact_id = index.insert_artifact(
            account="webmail",
            folder="browser-download",
            message_uid=sha256_bytes(str(file_path).encode())[:16],
            part_ref=attachment.part_ref,
            source_kind=attachment.source_kind,
            source_ref=attachment.source_ref or attachment.filename,
            received_at=_received_at(month),
            sender="webmail",
            subject=attachment.filename,
            preview=attachment.filename,
            local_path=None,
            sha256=content_sha,
            mime_type=attachment.content_type,
            extension=extension,
            metadata=metadata,
            business_key=business_key,
            status="duplicate",
            duplicate_of_id=existing["id"],
        )
        return {"status": "duplicate", "id": artifact_id, "local_path": None}

    local_path = _write_artifact(config, month, file_path, attachment)
    artifact_id = index.insert_artifact(
        account="webmail",
        folder="browser-download",
        message_uid=sha256_bytes(str(file_path).encode())[:16],
        part_ref=attachment.part_ref,
        source_kind=attachment.source_kind,
        source_ref=attachment.source_ref or attachment.filename,
        received_at=_received_at(month),
        sender="webmail",
        subject=attachment.filename,
        preview=attachment.filename,
        local_path=str(local_path),
        sha256=content_sha,
        mime_type=attachment.content_type,
        extension=extension,
        metadata=metadata,
        business_key=business_key,
        status="saved",
        duplicate_of_id=None,
    )
    return {"status": "saved", "id": artifact_id, "local_path": str(local_path)}


def _record_skipped(
    index: ArchiveIndex,
    month: str,
    file_path: Path,
    attachment: AttachmentPayload,
    reason: str,
) -> dict[str, object]:
    metadata = _metadata_for_local_file(attachment)
    content_sha = sha256_bytes(attachment.data)
    business_key = infer_business_key(metadata, content_sha)
    artifact_id = index.insert_artifact(
        account="webmail",
        folder="browser-download",
        message_uid=sha256_bytes(str(file_path).encode())[:16],
        part_ref=attachment.part_ref,
        source_kind=attachment.source_kind,
        source_ref=attachment.source_ref or attachment.filename,
        received_at=_received_at(month),
        sender="webmail",
        subject=attachment.filename,
        preview=attachment.filename,
        local_path=None,
        sha256=content_sha,
        mime_type=attachment.content_type,
        extension=attachment.extension,
        metadata=metadata,
        business_key=business_key,
        status="failed",
        duplicate_of_id=None,
        failure_reason=reason,
    )
    return {"status": "skipped", "id": artifact_id, "local_path": None, "source_path": str(file_path)}


def _write_artifact(
    config: RuntimeConfig,
    month: str,
    file_path: Path,
    attachment: AttachmentPayload,
) -> Path:
    month_dir = config.archive_root / month
    month_dir.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(attachment.filename)
    filename = f"{month}-01__webmail__{sha256_bytes(str(file_path).encode())[:12]}__{safe_name}"
    target = month_dir / filename
    target.write_bytes(attachment.data)
    return target


def _apply_status(result: ImportResult, status: dict[str, object]) -> None:
    state = status["status"]
    if state == "saved":
        result.imported += 1
        result.saved_paths.append(status["local_path"])
    elif state == "duplicate":
        result.duplicates += 1
    elif state == "conflict":
        result.conflicts += 1
        result.saved_paths.append(status["local_path"])
    elif state == "skipped":
        result.skipped += 1
        result.skipped_paths.append(status["source_path"])
    elif state == "failed":
        result.failures += 1


def sanitize_filename(name: str) -> str:
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_", ".", "(", ")", " "} else "_" for ch in name)
    return sanitized.strip() or "attachment.bin"


def _attachment_preference_score(extension: str) -> int:
    ext = (extension or "").lower()
    return {
        "png": 5,
        "jpg": 5,
        "jpeg": 5,
        "pdf": 4,
    }.get(ext, 0)


def _received_at(month: str) -> str:
    return f"{month}-01T00:00:00"


def cents_to_currency(amount_cents: int | None) -> str:
    if amount_cents is None:
        return "¥unknown"
    return f"¥{amount_cents / 100:.2f}"
