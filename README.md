# Mail Invoice Archiver

Cross-platform AI skill for syncing invoice emails from a 126 mailbox, downloading likely invoice attachments or linked files, deduplicating by invoice number plus amount, and preparing monthly ZIP bundles plus chat-friendly summaries.

## What This Repo Contains

- OpenClaw-compatible skill source in `skills/mail_invoice_archiver/`
- Codex wrapper in `codex-skills/mail-invoice-archiver/`
- Hermes wrapper in `hermes-skills/productivity/mail-invoice-archiver/`
- Shared Python runtime for IMAP sync, metadata extraction, dedupe, report generation, and delivery bundle preparation
- Unit tests for extraction, dedupe, setup flow, and Windows system-credential advertising

## Requirements

- Python 3.11 or newer
- `pip install -r requirements.txt`
- 126 mailbox with IMAP enabled and a client authorization code
- Optional OCR tools:
  `tesseract` for image OCR, `ocrmypdf` if you later want a stronger scanned-PDF pipeline

## First Session Credential Options

The runtime supports four credential modes:

- `system`
  Recommended on macOS and Windows. Uses macOS Keychain or Windows Credential Manager.
- `env`
  Good for Windows shells, Linux, CI, containers, or any session where you do not want to persist the authorization code in the system store.
- `config`
  Cross-platform, but stores the authorization code in plain text.
- `prompt`
  Stores nothing and asks for the authorization code every session.

The standard first-session flow is:

1. Run `doctor`.
2. If it returns `setup_required: true`, choose `system`, `env`, `config`, or `prompt`.
3. Run `setup`.
4. If you chose `env`, export the variables and rerun `doctor`.
5. Only after `doctor` succeeds should you continue with `list`, `sync`, `report`, `pack`, or `deliver`.

## Windows Env Examples

Use these snippets when the user chooses `env` on Windows.

PowerShell:

```powershell
$env:MAIL_INVOICE_ARCHIVER_EMAIL = "your-126@126.com"
$env:MAIL_INVOICE_ARCHIVER_AUTH_CODE = "your-auth-code"
python .\skills\mail_invoice_archiver\scripts\cli.py doctor --json
```

CMD:

```cmd
set MAIL_INVOICE_ARCHIVER_EMAIL=your-126@126.com
set MAIL_INVOICE_ARCHIVER_AUTH_CODE=your-auth-code
python .\skills\mail_invoice_archiver\scripts\cli.py doctor --json
```

Optional service override for advanced setups:

- `MAIL_INVOICE_ARCHIVER_SYSTEM_SERVICE`
  Overrides the system credential entry name when you use `system`

## Common Commands

From the repository root:

```bash
python skills/mail_invoice_archiver/scripts/cli.py doctor --json
python skills/mail_invoice_archiver/scripts/cli.py setup --provider system --email your-126@126.com
python skills/mail_invoice_archiver/scripts/cli.py list --month 2026-04 --limit 20 --json
python skills/mail_invoice_archiver/scripts/cli.py sync --month 2026-04 --json
python skills/mail_invoice_archiver/scripts/cli.py report --month 2026-04 --json
python skills/mail_invoice_archiver/scripts/cli.py deliver --month 2026-04 --json
```

## Notes

- The runtime prefers `appleimap.126.com` and sends an Apple Mail style IMAP `ID` before selecting `INBOX`, because this avoids 126's `Unsafe Login` response in practice.
- Deduplication happens in two layers:
  transport-level duplicates by message UID and content hash, and business-level duplicates by `invoice number + amount`.
- Delivery is chat-oriented. The runtime prepares the ZIP and summary; the host agent is expected to attach the ZIP in the current conversation instead of replying by email.

## Testing

```bash
python -m unittest discover -s tests -v
```

## Security

- Do not commit your local config, auth code, exported archives, or runtime database.
- `.gitignore` already excludes local config files, ZIP exports, SQLite files, PEM keys, and archive output.
