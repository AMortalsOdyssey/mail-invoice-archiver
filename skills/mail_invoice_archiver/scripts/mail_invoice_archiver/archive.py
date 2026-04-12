from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

from .config import RuntimeConfig
from .extractors import (
    extract_invoice_metadata,
    extract_urls,
    infer_business_key,
    probable_invoice_attachment,
    probable_invoice_message,
    sha256_bytes,
)
from .imap_client import IMAPMailbox
from .index import ArchiveIndex
from .models import AttachmentPayload, DeliveryResult, InvoiceMetadata, ParsedMessage, SyncResult
from .providers import get_mail_provider


def run_doctor(config: RuntimeConfig, account: str, password: str) -> dict[str, object]:
    mailbox = IMAPMailbox(config, account=account, password=password)
    host, folder = mailbox.connect()
    probe_month = datetime.now().strftime("%Y-%m")
    status = mailbox.month_status(probe_month)
    mailbox.close()
    provider = get_mail_provider(config.mail_provider, config.email_address or account)
    return {
        "account": account,
        "mail_provider": provider.id,
        "mail_provider_label": provider.display_name,
        "selected_host": host,
        "selected_folder": folder,
        "probe_month": probe_month,
        "probe_message_count": status["message_count"],
        "archive_root": str(config.archive_root),
        "database_path": str(config.database_path),
        "web_healthcheck_enabled": config.web_healthcheck_enabled,
        "ocr": {
            "tesseract": bool(shutil.which("tesseract")),
            "ocrmypdf": bool(shutil.which("ocrmypdf")),
        },
    }


def list_month_messages(
    config: RuntimeConfig,
    account: str,
    password: str,
    month: str,
    limit: int | None = None,
) -> list[dict[str, object]]:
    mailbox = IMAPMailbox(config, account=account, password=password)
    mailbox.connect()
    rows: list[dict[str, object]] = []
    for message in mailbox.iter_month_messages(month, limit=limit):
        rows.append(
            {
                "uid": message.uid,
                "received_at": message.received_at.isoformat() if message.received_at else None,
                "sender": message.sender,
                "subject": message.subject,
                "attachment_names": [item.filename for item in message.attachments],
                "invoice_candidate": probable_invoice_message(message, config),
                "preview": message.preview,
            }
        )
    mailbox.close()
    return rows


def sync_month(
    config: RuntimeConfig,
    account: str,
    password: str,
    month: str,
    *,
    limit: int | None = None,
    follow_links: bool = True,
) -> SyncResult:
    config.archive_root.mkdir(parents=True, exist_ok=True)
    index = ArchiveIndex(config.database_path)
    mailbox = IMAPMailbox(config, account=account, password=password)
    mailbox.connect()
    result = SyncResult(month=month)
    try:
        for message in mailbox.iter_month_messages(month, limit=limit):
            result.scanned_messages += 1
            if not probable_invoice_message(message, config):
                continue
            for attachment in message.attachments:
                if not probable_invoice_attachment(attachment, message, config):
                    continue
                status = _store_attachment(config, index, month, message, attachment)
                _apply_status(result, status)
            if follow_links:
                for url in extract_urls(message, config):
                    downloaded = _download_link_if_invoice_like(url)
                    if isinstance(downloaded, AttachmentPayload):
                        status = _store_attachment(config, index, month, message, downloaded)
                        _apply_status(result, status)
                    elif downloaded:
                        result.link_failures += 1
                        result.failures += 1
                        index.insert_artifact(
                            account=message.account,
                            folder=message.folder,
                            message_uid=message.uid,
                            part_ref=f"url:{sha256_bytes(url.encode())[:12]}",
                            source_kind="link",
                            source_ref=url,
                            received_at=message.received_at.isoformat() if message.received_at else None,
                            sender=message.sender,
                            subject=message.subject,
                            preview=message.preview,
                            local_path=None,
                            sha256=sha256_bytes(url.encode()),
                            mime_type="text/uri-list",
                            extension="",
                            metadata=InvoiceMetadata(extraction_sources=["link-failed"]),
                            business_key=f"link:{sha256_bytes(url.encode())}",
                            status="failed",
                            duplicate_of_id=None,
                            failure_reason=str(downloaded),
                        )
    finally:
        mailbox.close()
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
        f"- 下载失败数：{summary['failure_count']}",
        "",
        "## 金额大于等于阈值的发票",
        "",
    ]
    high_value = summary["high_value"]
    if not high_value:
        lines.append("- 无")
    else:
        for row in high_value:
            lines.append(
                f"- {row['invoice_date'] or row['received_at']}: {row['source_ref']} / {cents_to_currency(row['amount_cents'])} / {row['sender']}"
            )
    lines.extend(["", "## 失败项", ""])
    failures = summary["failures"]
    if not failures:
        lines.append("- 无")
    else:
        for row in failures:
            lines.append(
                f"- {row['received_at']}: {row['subject']} / {row['source_ref']} / {row['failure_reason'] or 'unknown error'}"
            )
    return "\n".join(lines) + "\n"


def _apply_status(result: SyncResult, status: dict[str, object]) -> None:
    state = status["status"]
    if state == "saved":
        result.canonical_saved += 1
        result.saved_paths.append(status["local_path"])
    elif state == "duplicate":
        result.duplicates += 1
    elif state == "conflict":
        result.conflicts += 1
        result.saved_paths.append(status["local_path"])
    elif state == "failed":
        result.failures += 1


def _store_attachment(
    config: RuntimeConfig,
    index: ArchiveIndex,
    month: str,
    message: ParsedMessage,
    attachment: AttachmentPayload,
) -> dict[str, object]:
    metadata = extract_invoice_metadata(message, attachment)
    content_sha = sha256_bytes(attachment.data)
    business_key = infer_business_key(metadata, content_sha)
    extension = attachment.extension

    if metadata.invoice_number:
        same_number = index.find_same_invoice_number(metadata.invoice_number)
        for row in same_number:
            if row["amount_cents"] == metadata.amount_cents and metadata.amount_cents is not None:
                artifact_id = index.insert_artifact(
                    account=message.account,
                    folder=message.folder,
                    message_uid=message.uid,
                    part_ref=attachment.part_ref,
                    source_kind=attachment.source_kind,
                    source_ref=attachment.source_ref or attachment.filename,
                    received_at=message.received_at.isoformat() if message.received_at else None,
                    sender=message.sender,
                    subject=message.subject,
                    preview=message.preview,
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
            local_path = _write_artifact(config, month, message, attachment)
            artifact_id = index.insert_artifact(
                account=message.account,
                folder=message.folder,
                message_uid=message.uid,
                part_ref=attachment.part_ref,
                source_kind=attachment.source_kind,
                source_ref=attachment.source_ref or attachment.filename,
                received_at=message.received_at.isoformat() if message.received_at else None,
                sender=message.sender,
                subject=message.subject,
                preview=message.preview,
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
            account=message.account,
            folder=message.folder,
            message_uid=message.uid,
            part_ref=attachment.part_ref,
            source_kind=attachment.source_kind,
            source_ref=attachment.source_ref or attachment.filename,
            received_at=message.received_at.isoformat() if message.received_at else None,
            sender=message.sender,
            subject=message.subject,
            preview=message.preview,
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

    local_path = _write_artifact(config, month, message, attachment)
    artifact_id = index.insert_artifact(
        account=message.account,
        folder=message.folder,
        message_uid=message.uid,
        part_ref=attachment.part_ref,
        source_kind=attachment.source_kind,
        source_ref=attachment.source_ref or attachment.filename,
        received_at=message.received_at.isoformat() if message.received_at else None,
        sender=message.sender,
        subject=message.subject,
        preview=message.preview,
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


def _write_artifact(
    config: RuntimeConfig,
    month: str,
    message: ParsedMessage,
    attachment: AttachmentPayload,
) -> Path:
    month_dir = config.archive_root / month
    month_dir.mkdir(parents=True, exist_ok=True)
    received = message.received_at.date().isoformat() if message.received_at else month + "-01"
    safe_name = sanitize_filename(attachment.filename)
    filename = f"{received}__uid{message.uid}__{attachment.part_ref}__{safe_name}"
    target = month_dir / filename
    target.write_bytes(attachment.data)
    return target


def sanitize_filename(name: str) -> str:
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_", ".", "(", ")", " "} else "_" for ch in name)
    return sanitized.strip() or "attachment.bin"


def cents_to_currency(amount_cents: int | None) -> str:
    if amount_cents is None:
        return "¥unknown"
    return f"¥{amount_cents / 100:.2f}"


def _download_link_if_invoice_like(url: str) -> AttachmentPayload | str | None:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    if not path.endswith((".pdf", ".xml", ".ofd", ".zip", ".png", ".jpg", ".jpeg")):
        return None
    request = urllib.request.Request(url, headers={"User-Agent": "mail-invoice-archiver/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
            content_type = response.headers.get_content_type()
    except urllib.error.URLError as exc:
        return str(exc)
    filename = Path(parsed.path).name or "downloaded-file"
    return AttachmentPayload(
        part_ref=f"link-{sha256_bytes(url.encode())[:12]}",
        filename=filename,
        content_type=content_type,
        data=data,
        source_kind="link",
        source_ref=url,
    )
