---
name: mail-invoice-archiver
description: Sync invoice emails from a 126 mailbox, archive candidate invoices by month, deduplicate by invoice number and amount, and prepare summaries plus chat-delivery bundles.
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

## Commands

- `bash scripts/run-mail-invoice-archiver.sh setup --provider system|env|config|prompt --json`
- `bash scripts/run-mail-invoice-archiver.sh doctor --json`
- `bash scripts/run-mail-invoice-archiver.sh list --month YYYY-MM --limit 20 --json`
- `bash scripts/run-mail-invoice-archiver.sh sync --month YYYY-MM --json`
- `bash scripts/run-mail-invoice-archiver.sh report --month YYYY-MM --json`
- `bash scripts/run-mail-invoice-archiver.sh deliver --month YYYY-MM --json`

## Windows Env Setup

- If the user chooses `env` on Windows, offer one of these exact snippets and wait for confirmation before rerunning `doctor`.

```powershell
$env:MAIL_INVOICE_ARCHIVER_EMAIL = "your-126@126.com"
$env:MAIL_INVOICE_ARCHIVER_AUTH_CODE = "your-auth-code"
```

```cmd
set MAIL_INVOICE_ARCHIVER_EMAIL=your-126@126.com
set MAIL_INVOICE_ARCHIVER_AUTH_CODE=your-auth-code
```

## Rules

- In the first session after installation, ask the user which credential storage mode they want before doing anything else.
- Run `doctor` first. If it returns `setup_required`, ask the user to choose `system`, `env`, `config`, or `prompt`, then run `setup`.
- Prefer `system` on macOS and Windows, and `env` for Linux, CI, or headless sessions.
- `system` means macOS Keychain on macOS and Windows Credential Manager on Windows.
- Prefer `appleimap.126.com`, because 126 may reject default script clients as `Unsafe Login`.
- Send an Apple Mail style IMAP `ID` before selecting `INBOX`.
- Use business dedupe by `invoice number + amount`.
- Keep conflicts when invoice number matches but amount differs, and surface them in the report.
- After `deliver`, attach the returned zip file to the current Hermes conversation and include the generated summary.
