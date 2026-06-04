---
name: mail-invoice-archiver
description: Use the mailbox web UI as the source of truth, import downloaded invoice files, deduplicate by invoice number and amount, and prepare summaries plus chat-delivery bundles.
version: 2.0.0
author: Codex
license: MIT
platforms: [macos, windows, linux]
category: productivity
tags: [email, invoice, finance, browser, automation]
---

# Mail Invoice Archiver

## Purpose

Use the mailbox web UI as the reliable source of truth for invoice discovery. Use the shared runtime in `../../../skills/mail_invoice_archiver/scripts/cli.py` only after original invoice files have been downloaded from webmail.

For multi-month final folders, merged PDFs, monthly totals, or iterative include/exclude edits, also read:
[../../../skills/mail_invoice_archiver/references/final-pdf-export-workflow.md](../../../skills/mail_invoice_archiver/references/final-pdf-export-workflow.md).

## Commands

- `bash scripts/run-mail-invoice-archiver.sh doctor --json`
- `bash scripts/run-mail-invoice-archiver.sh checklist --from-month YYYY-MM --to-month YYYY-MM --json`
- `bash scripts/run-mail-invoice-archiver.sh import-files --month YYYY-MM --source-dir /path/to/downloads --json`
- `bash scripts/run-mail-invoice-archiver.sh report --month YYYY-MM --json`
- `bash scripts/run-mail-invoice-archiver.sh pack --month YYYY-MM --json`
- `bash scripts/run-mail-invoice-archiver.sh deliver --month YYYY-MM --json`

## Rules

- Search and download through the provider webmail UI.
- Use business dedupe by `invoice number + amount`.
- Keep conflicts when invoice number matches but amount differs, and surface them in the report.
- OFD-only candidates must be skipped from the final source folder, merged PDF, and totals, then listed as skipped because no usable PDF invoice was available.
- Never force OFD-derived text pages, screenshots, placeholder pages, or conversions into the final merged PDF.
- Exclude non-invoice proofs unless explicitly requested.
- Final amount summaries default to grand total plus monthly totals rounded to two decimals. Do not list every invoice unless requested.
