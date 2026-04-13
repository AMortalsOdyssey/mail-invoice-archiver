# Mail Invoice Archiver

Cross-platform AI skill for syncing invoice emails from supported mailbox providers such as 126, 163, and Gmail, downloading likely invoice attachments or linked files, deduplicating by invoice number plus amount, and preparing monthly ZIP bundles plus chat-friendly summaries.

## What This Repo Contains

- OpenClaw-compatible skill source in `skills/mail_invoice_archiver/`
- Codex wrapper in `codex-skills/mail-invoice-archiver/`
- Hermes wrapper in `hermes-skills/productivity/mail-invoice-archiver/`
- Shared Python runtime for IMAP sync, metadata extraction, dedupe, report generation, and delivery bundle preparation
- Unit tests for extraction, dedupe, setup flow, and Windows system-credential advertising

## Repository Layout

The skill is organized as one shared runtime plus thin wrappers for each host agent.

```text
mail-invoice-archiver/
├── README.md
├── skills/
│   └── mail_invoice_archiver/
│       ├── SKILL.md
│       ├── references/
│       └── scripts/
│           └── mail_invoice_archiver/
│               ├── providers.py
│               ├── config.py
│               ├── auth.py
│               ├── imap_client.py
│               ├── archive.py
│               └── ...
├── codex-skills/
│   └── mail-invoice-archiver/
│       ├── SKILL.md
│       └── agents/
│           └── openai.yaml
├── hermes-skills/
│   └── productivity/
│       └── mail-invoice-archiver/
│           └── SKILL.md
└── tests/
    └── test_mail_invoice_archiver.py
```

- `skills/mail_invoice_archiver/`
  The real skill source and shared runtime. New mailbox providers, archive logic, OCR, dedupe, and packaging behavior should land here first.
- `codex-skills/mail-invoice-archiver/`
  Codex-facing wrapper. It keeps the skill discoverable in Codex while reusing the shared runtime.
- `hermes-skills/productivity/mail-invoice-archiver/`
  Hermes-facing wrapper. It points Hermes to the same shared runtime and usage rules.
- `tests/`
  Shared regression tests for extraction, provider detection, auth setup, and archive behavior.

In practice, this means:

- OpenClaw is the source-of-truth skill shape.
- Codex and Hermes are adapter layers.
- Business logic should stay in the shared Python runtime, not be duplicated across wrappers.

## Requirements

- Python 3.11 or newer
- `pip install -r requirements.txt`
- Supported mailbox providers in phase one:
  `126`, `163`, and `gmail`
- Optional OCR tools:
  `tesseract` for image OCR, `ocrmypdf` if you later want a stronger scanned-PDF pipeline

## Provider Model

The runtime now uses a mailbox-provider registry instead of hard-coding 126 assumptions into the whole stack.

- `126`
  Implemented and live-tested in this workspace.
- `163`
  Implemented with the same Netease IMAP and authorization-code flow as 126.
  It is docs-verified, but not live-tested in this workspace yet.
- `gmail`
  Implemented with `imap.gmail.com` and a Gmail app password.
  This is the phase-one path for personal Gmail accounts.
  Google Workspace deployments may still need admin-side IMAP enablement or OAuth.
  OAuth is not implemented yet in the current runtime.
- `custom`
  Manual fallback for other IMAP providers when you want to supply your own host list and settings.

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

1. Run `providers` if you need to see the built-in provider matrix.
2. Run `doctor`.
3. If it returns `setup_required: true`, choose a mailbox provider such as `126`, `163`, `gmail`, or `custom`.
4. Choose `system`, `env`, `config`, or `prompt`.
5. Run `setup`.
6. If you chose `env`, export the variables and rerun `doctor`.
7. Only after `doctor` succeeds should you continue with `list`, `sync`, `report`, `pack`, or `deliver`.

## Windows Env Examples

Use these snippets when the user chooses `env` on Windows.

PowerShell:

```powershell
$env:MAIL_INVOICE_ARCHIVER_EMAIL = "your-mail@example.com"
$env:MAIL_INVOICE_ARCHIVER_AUTH_CODE = "your-provider-secret"
python .\skills\mail_invoice_archiver\scripts\cli.py doctor --json
```

CMD:

```cmd
set MAIL_INVOICE_ARCHIVER_EMAIL=your-mail@example.com
set MAIL_INVOICE_ARCHIVER_AUTH_CODE=your-provider-secret
python .\skills\mail_invoice_archiver\scripts\cli.py doctor --json
```

Optional service override for advanced setups:

- `MAIL_INVOICE_ARCHIVER_SYSTEM_SERVICE`
  Overrides the system credential entry name when you use `system`

For Gmail, `MAIL_INVOICE_ARCHIVER_AUTH_CODE` must be a Gmail app password, not the normal Google account password.

## Common Commands

From the repository root:

```bash
python skills/mail_invoice_archiver/scripts/cli.py providers --json
python skills/mail_invoice_archiver/scripts/cli.py doctor --json
python skills/mail_invoice_archiver/scripts/cli.py setup --mail-provider 126 --provider system --email your-126@126.com
python skills/mail_invoice_archiver/scripts/cli.py setup --mail-provider gmail --provider env --email your@gmail.com
python skills/mail_invoice_archiver/scripts/cli.py list --month 2026-04 --limit 20 --json
python skills/mail_invoice_archiver/scripts/cli.py sync --month 2026-04 --json
python skills/mail_invoice_archiver/scripts/cli.py report --month 2026-04 --json
python skills/mail_invoice_archiver/scripts/cli.py deliver --month 2026-04 --json
```

## Attachment Preference And OCR Notes

- When the same invoice appears in several formats in one message, the archive now prefers user-friendly canonical artifacts in this order:
  image (`png` / `jpg` / `jpeg`), then `pdf`, then `xml`, then `ofd`, and `zip` last.
- OFD is treated as a fallback archival format. If a readable PDF can be derived or is already present, the runtime avoids making OFD the default saved artifact.
- PDF extraction now prefers the invoice total area over the first visible currency value, and falls back to OCR when direct text extraction is not reliable and OCR tooling is available.

## Optional Feishu Delivery Helper

- The shared runtime now includes an optional Feishu helper in `skills/mail_invoice_archiver/scripts/mail_invoice_archiver/feishu_delivery.py`.
- Do not place real Feishu secrets inside the published skill directory.
- Commit only the example file:
  `skills/mail_invoice_archiver/config/feishu/config.example.yaml`
- Keep real local config outside the repo and outside the published skill:
  `~/.config/openclaw/mail_invoice_archiver/feishu.config.yaml`
- Supported environment variables:
  `MAIL_INVOICE_ARCHIVER_FEISHU_APP_ID`,
  `MAIL_INVOICE_ARCHIVER_FEISHU_APP_SECRET`,
  `MAIL_INVOICE_ARCHIVER_FEISHU_RECEIVE_ID_TYPE`,
  and optional `MAIL_INVOICE_ARCHIVER_FEISHU_CONFIG`

## Notes

- The runtime prefers provider-specific defaults instead of one global IMAP host list.
- For 126, the runtime prefers `appleimap.126.com` and sends an Apple Mail style IMAP `ID` before selecting `INBOX`, because this avoids 126's `Unsafe Login` response in practice.
- For 163, the runtime reuses the same Netease authorization-code and IMAP-ID approach, but that path is docs-verified rather than live-tested in this workspace.
- For Gmail, the runtime uses `imap.gmail.com` and an app password. This is the intended phase-one path for personal Gmail accounts; some Google Workspace tenants may still require OAuth or admin IMAP changes.
- Deduplication happens in two layers:
  transport-level duplicates by message UID and content hash, and business-level duplicates by `invoice number + amount`.
- Delivery is chat-oriented. The runtime prepares the ZIP and summary; the host agent is expected to attach the ZIP in the current conversation instead of replying by email.

## Testing

```bash
python -m unittest discover -s tests -v
```

## Security

- Do not commit your local config, auth code, exported archives, or runtime database.
- `.gitignore` already excludes local config files, ZIP exports, SQLite files, PEM keys, archive output, and the in-skill Feishu secret path.
- `skills/mail_invoice_archiver/.openclawignore` also blocks accidental upload of `config/feishu/config.yaml` if someone misplaces secrets inside the skill directory.
