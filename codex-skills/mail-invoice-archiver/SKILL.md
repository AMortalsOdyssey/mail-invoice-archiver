---
name: mail-invoice-archiver
description: Use the mailbox web UI as the source of truth for invoice discovery, guide browser-based invoice downloads, import downloaded invoice files, deduplicate by invoice number plus amount, and prepare delivery bundles plus monthly summaries. Use when Codex needs to collect invoice mail, organize downloaded invoice files, troubleshoot missing invoices, or package invoice archives for the current chat.
---

# Mail Invoice Archiver

## Overview

Use the bundled runtime in `runtime/scripts/cli.py`. Browser/webmail discovery is the source of truth; the runtime only organizes files downloaded from the web UI.

For multi-month final folders, merged PDFs, monthly totals, or iterative include/exclude edits, also read:
[runtime/references/final-pdf-export-workflow.md](runtime/references/final-pdf-export-workflow.md).

## Workflow

1. Open the user's authenticated mailbox web UI in Chrome or the available browser.
2. Search each requested month explicitly with webmail date filters, full-text search, attachment filters, and visible pagination.
3. Download original usable invoice PDF or image files into a local month source folder.
4. Run `bash scripts/run-mail-invoice-archiver.sh doctor --json`.
5. Run `bash scripts/run-mail-invoice-archiver.sh checklist --from-month YYYY-MM --to-month YYYY-MM --json` when you need the browser search checklist.
6. Run `bash scripts/run-mail-invoice-archiver.sh import-files --month YYYY-MM --source-dir /path/to/downloads --json`.
7. Run `bash scripts/run-mail-invoice-archiver.sh report --month YYYY-MM --json`.
8. Run `bash scripts/run-mail-invoice-archiver.sh pack --month YYYY-MM --json` or `deliver --month YYYY-MM --json`.
9. Rebuild imported files, report, and merged PDF together after every include/exclude change.

## Rules

- Treat the mailbox web UI as the source of truth.
- Final merged PDFs include usable invoice PDF or image documents only.
- OFD-only candidates must be skipped from the final source folder, merged PDF, and totals, then listed as skipped because no usable PDF invoice was available.
- Never force OFD-derived text pages, screenshots, placeholder pages, or conversions into the final merged PDF.
- Exclude hotel folios, water statements, booking vouchers, itinerary-only files, QR-code screenshots, scan-to-issue placeholders, and other non-invoice proofs unless explicitly requested.
- Prefer original readable PDF or image artifacts over XML, OFD, or ZIP.
- Use XML only as an amount extraction aid when a usable PDF/image invoice is present; prefer tax-included total fields such as `TotalTax-includedAmount`.
- Final amount summaries default to grand total plus monthly totals rounded to two decimals. Do not list every invoice unless requested.
- Render-check merged PDFs page by page for blank or placeholder pages before delivery.

## References

- Runtime notes: [runtime/references/compatibility-notes.md](runtime/references/compatibility-notes.md)
- Final PDF export workflow: [runtime/references/final-pdf-export-workflow.md](runtime/references/final-pdf-export-workflow.md)
