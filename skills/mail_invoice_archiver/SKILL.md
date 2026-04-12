---
name: mail_invoice_archiver
description: Read 126 mailbox messages, identify invoice attachments or invoice download links, archive invoices by month, deduplicate by invoice number and amount, prepare monthly reports and delivery bundles. Use when OpenClaw needs to sync email invoices, investigate failed downloads, package a month's archive, or summarize totals and high-value invoices.
metadata: {"openclaw":{"name":"mail_invoice_archiver","displayName":"Mail Invoice Archiver","requires":["python3"],"requiresNetwork":true}}
---

# Mail Invoice Archiver

## Quick Start

- In the first session after installation, ask the user which credential storage mode they want before doing anything else.
- Run `python3 {baseDir}/scripts/cli.py doctor --json` first. If it returns `setup_required: true`, guide the user through setup and wait for confirmation.
- Use `python3 {baseDir}/scripts/cli.py setup` for an interactive setup wizard, or pass `--provider system|env|config|prompt` for scripted setup.
- Use `python3 {baseDir}/scripts/cli.py sync --month YYYY-MM --json` to pull a month into the local archive.
- Use `python3 {baseDir}/scripts/cli.py report --month YYYY-MM --json` to inspect totals, duplicates, conflicts, and failures.
- Use `python3 {baseDir}/scripts/cli.py deliver --month YYYY-MM --json` to prepare a zip plus summary for the current chat.

## Workflow

1. Run `doctor`.
2. If `doctor` reports `setup_required`, ask the user to choose one of these auth methods and confirm their choice before continuing:
   system credential store, environment variables, config file, or prompt-each-session.
3. Run `setup` with the chosen method and wait for the user to confirm they completed any external steps, such as exporting environment variables.
4. Run `doctor` again to confirm the setup works.
5. Run `list --month YYYY-MM --limit 20 --json` when you need a quick mailbox preview without downloading files.
6. Run `sync --month YYYY-MM --json` to archive candidate invoices into `~/Documents/invoice-archive/YYYY-MM/`.
7. Run `report --month YYYY-MM --json` after sync and summarize:
   total amount, canonical invoice count, high-value invoices, duplicates, conflicts, and failures.
8. Run `deliver --month YYYY-MM --json`, then attach the returned zip file in the current chat and paste the summary.

## Windows Env Setup

- If the user chooses `env` on Windows, offer one of these exact snippets and wait for confirmation before rerunning `doctor`.

```powershell
$env:MAIL_INVOICE_ARCHIVER_EMAIL = "your-126@126.com"
$env:MAIL_INVOICE_ARCHIVER_AUTH_CODE = "your-auth-code"
python "{baseDir}/scripts/cli.py" doctor --json
```

```cmd
set MAIL_INVOICE_ARCHIVER_EMAIL=your-126@126.com
set MAIL_INVOICE_ARCHIVER_AUTH_CODE=your-auth-code
python "{baseDir}\scripts\cli.py" doctor --json
```

## Rules

- Prefer `system` auth on macOS and Windows, `env` on Linux, CI, or headless sessions, and `prompt` only when the user does not want to persist the secret anywhere.
- `system` currently means macOS Keychain on macOS and Windows Credential Manager on Windows.
- Treat `appleimap.126.com` as the preferred IMAP host.
- Always send the configured IMAP client `ID` before selecting `INBOX`; this avoids 126's `Unsafe Login` response in practice.
- Deduplicate in two layers:
  storage duplicates by message UID / part / SHA256;
  business duplicates by `invoice number + amount`.
- If invoice number matches but amount differs, keep the file and report it as a conflict instead of auto-merging.
- Keep invoice amount and OCR results in SQLite metadata, not in file names.
- If a link download fails and the message still looks like an invoice, report that failure back to the user.

## Resources

- Runtime: [scripts/cli.py](scripts/cli.py)
- Detailed findings and pitfalls: [references/compatibility-notes.md](references/compatibility-notes.md)
