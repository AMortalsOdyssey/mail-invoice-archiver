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
- After `deliver`, attach the returned zip file to the current Hermes conversation and include the generated summary.
