---
name: mail-invoice-archiver
description: Read supported mailbox providers such as 126, 163, and Gmail with a user-chosen secret source, identify invoice attachments and invoice download links, archive them by month, deduplicate by invoice number plus amount, and prepare delivery bundles plus monthly summaries. Use when Codex needs to inspect invoice mail, sync a month of invoices, troubleshoot failed downloads, or package a month's archive for the current chat.
---

# Mail Invoice Archiver

## Overview

Use the shared runtime in `../../skills/mail_invoice_archiver/scripts/cli.py`. This Codex wrapper keeps the skill discoverable in hyphen-case while reusing the OpenClaw-compatible implementation.

## Workflow

1. In the first session after installation, ask the user which mailbox provider and credential storage mode they want before doing anything else.
2. Run `bash scripts/run-mail-invoice-archiver.sh providers --json` if you need to show the supported provider matrix.
3. Run `bash scripts/run-mail-invoice-archiver.sh doctor --json`.
4. If `doctor` reports `setup_required`, ask the user to choose one of: `126`, `163`, `gmail`, or `custom`, then ask for one of: `system`, `env`, `config`, or `prompt`, and run `bash scripts/run-mail-invoice-archiver.sh setup --mail-provider ... --provider ...`.
5. Wait for the user to confirm any external step, such as exporting environment variables.
5. Run `bash scripts/run-mail-invoice-archiver.sh doctor --json` again to validate the chosen setup.
6. Run `bash scripts/run-mail-invoice-archiver.sh list --month YYYY-MM --limit 20 --json` to preview a month's mailbox contents.
7. Run `bash scripts/run-mail-invoice-archiver.sh sync --month YYYY-MM --json` to archive candidate invoices locally.
8. Run `bash scripts/run-mail-invoice-archiver.sh report --month YYYY-MM --json` to summarize totals, duplicates, conflicts, and failures.
9. Run `bash scripts/run-mail-invoice-archiver.sh deliver --month YYYY-MM --json`, then attach the returned zip file in the current chat and paste the summary.

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

- Offer multiple auth modes on first use instead of assuming macOS Keychain:
  `system`, `env`, `config`, or `prompt`.
- Prefer `system` on macOS and Windows, and `env` for Linux, CI, or headless sessions.
- `system` means macOS Keychain on macOS and Windows Credential Manager on Windows.
- Built-in providers in this phase are `126`, `163`, and `gmail`.
- Prefer `appleimap.126.com` for 126. Use provider-specific host defaults instead of hard-coding one host for every mailbox.
- Send the Apple Mail style IMAP `ID` for 126 and 163. Do not force that path on Gmail.
- Gmail currently requires an app password in this runtime for personal Gmail accounts. Some Google Workspace tenants may still require admin-side IMAP changes or OAuth, which is not implemented yet.
- Keep invoice metadata in SQLite instead of encoding it into file names.
- Treat same `invoice number + amount` as one canonical invoice even if multiple emails contain it.
- If invoice number matches but amount differs, keep the file and report a conflict.

## References

- Shared runtime notes: [../../skills/mail_invoice_archiver/references/compatibility-notes.md](../../skills/mail_invoice_archiver/references/compatibility-notes.md)
