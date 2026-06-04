---
name: mail-invoice-archiver
description: Sync invoice emails from supported mailbox providers such as 126, 163, and Gmail, archive candidate invoices by month, deduplicate by invoice number and amount, and prepare summaries plus chat-delivery bundles.
version: 1.0.0
author: Codex
license: MIT
platforms: [macos, windows, linux]
category: productivity
tags: [email, invoice, finance, automation]
---

# Mail Invoice Archiver

## Purpose

Use the shared runtime in `../../../skills/mail_invoice_archiver/scripts/cli.py` to inspect invoice mail, archive invoices, and prepare monthly bundles for the current chat.

For multi-month final folders, merged PDFs, monthly totals, or iterative include/exclude edits, also read the shared final export workflow:
[../../../skills/mail_invoice_archiver/references/final-pdf-export-workflow.md](../../../skills/mail_invoice_archiver/references/final-pdf-export-workflow.md).

## Commands

- `bash scripts/run-mail-invoice-archiver.sh setup --provider system|env|config|prompt --json`
- `bash scripts/run-mail-invoice-archiver.sh providers --json`
- `bash scripts/run-mail-invoice-archiver.sh doctor --json`
- `bash scripts/run-mail-invoice-archiver.sh list --month YYYY-MM --limit 20 --json`
- `bash scripts/run-mail-invoice-archiver.sh sync --month YYYY-MM --json`
- `bash scripts/run-mail-invoice-archiver.sh report --month YYYY-MM --json`
- `bash scripts/run-mail-invoice-archiver.sh deliver --month YYYY-MM --json`

## Windows Env Setup

- If the user chooses `env` on Windows, offer one of these exact snippets and wait for confirmation before rerunning `doctor`.

```powershell
$env:MAIL_INVOICE_ARCHIVER_EMAIL = "your-mail@example.com"
$env:MAIL_INVOICE_ARCHIVER_AUTH_CODE = "your-provider-secret"
```

```cmd
set MAIL_INVOICE_ARCHIVER_EMAIL=your-mail@example.com
set MAIL_INVOICE_ARCHIVER_AUTH_CODE=your-provider-secret
```

## Rules

- In the first session after installation, ask the user which mailbox provider and credential storage mode they want before doing anything else.
- Run `providers` if you need to show the supported mailbox matrix.
- Run `doctor` first. If it returns `setup_required`, ask the user to choose `126`, `163`, `gmail`, or `custom`, then ask for `system`, `env`, `config`, or `prompt`, then run `setup`.
- Prefer `system` on macOS and Windows, and `env` for Linux, CI, or headless sessions.
- `system` means macOS Keychain on macOS and Windows Credential Manager on Windows.
- Built-in providers in this phase are `126`, `163`, and `gmail`.
- Prefer `appleimap.126.com` for 126. Use provider-specific host defaults instead of forcing one host on every mailbox.
- Send an Apple Mail style IMAP `ID` for 126 and 163. Do not force that path on Gmail.
- Gmail currently requires an app password in this runtime for personal Gmail accounts. Some Google Workspace tenants may still require admin-side IMAP changes or OAuth, which is not implemented yet.
- Use business dedupe by `invoice number + amount`.
- Keep conflicts when invoice number matches but amount differs, and surface them in the report.
- For final merged PDFs, include only invoice documents. Exclude hotel folios, water statements, booking vouchers, itinerary-only files, QR-code screenshots, scan-to-issue placeholders, and other non-invoice proofs unless explicitly requested.
- Prefer original readable PDF or image artifacts over XML, OFD, or ZIP for user-facing exports. OFD-derived text or screenshot pages are fallbacks only when no better representation exists.
- If the user manually removes, restores, or names invoice files or invoice numbers, rebuild the final source folder, merged PDF, and totals together.
- Final amount summaries default to grand total plus monthly totals rounded to two decimals. Do not list every invoice unless requested.
- Render-check merged PDFs page by page for blank or placeholder pages before delivery, and keep old/intermediate PDFs out of the final export folder.
- For XML-backed travel or platform invoices, prefer tax-included total fields such as `TotalTax-includedAmount` or provider-equivalent fields over the first visible PDF amount.
- After `deliver`, attach the returned zip file to the current Hermes conversation and include the generated summary.
