# Mail Invoice Archiver

Browser-first AI skill for collecting invoices from mailbox web UI, importing downloaded invoice files, deduplicating by invoice number plus amount, and preparing monthly bundles plus summaries.

## What This Repo Contains

- OpenClaw-compatible skill source in `skills/mail_invoice_archiver/`
- Self-contained Codex skill in `codex-skills/mail-invoice-archiver/`
- Hermes wrapper in `hermes-skills/productivity/mail-invoice-archiver/`
- Python runtime for local file import, metadata extraction, dedupe, report generation, and delivery bundle preparation
- Unit tests for extraction, webmail-download imports, OFD-only skipping, dedupe, and delivery config

## Current Collection Model

The reliable workflow is:

1. Open the user's authenticated mailbox web UI.
2. Search by month, invoice keywords, visible pagination, and attachment indicators.
3. Download original usable invoice PDF or image files from the web UI.
4. Run the local runtime on the downloaded source folder.
5. Rebuild reports, packages, and merged PDFs from the imported local files.

The runtime is not responsible for mailbox discovery. It only organizes files that were downloaded from the mailbox web UI.

## Repository Layout

```text
mail-invoice-archiver/
├── README.md
├── skills/
│   └── mail_invoice_archiver/
│       ├── SKILL.md
│       ├── references/
│       └── scripts/
│           └── mail_invoice_archiver/
│               ├── archive.py
│               ├── config.py
│               ├── extractors.py
│               ├── index.py
│               └── ...
├── codex-skills/
│   └── mail-invoice-archiver/
│       ├── SKILL.md
│       ├── runtime/
│       └── agents/
├── hermes-skills/
│   └── productivity/
│       └── mail-invoice-archiver/
└── tests/
    └── test_mail_invoice_archiver.py
```

OpenClaw is the source-of-truth skill shape. The Codex skill vendors the same runtime under `codex-skills/mail-invoice-archiver/runtime/` so GitHub installation can target a single directory.

## Codex Install

Install the Codex skill from the self-contained directory:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo AMortalsOdyssey/mail-invoice-archiver --path codex-skills/mail-invoice-archiver
```

After installation, Codex should show one skill: `mail-invoice-archiver`.

## Requirements

- Python 3.11 or newer
- `pip install -r requirements.txt`
- Optional OCR tools:
  `tesseract` for image OCR, `ocrmypdf` for scanned PDFs

## Common Commands

From the repository root:

```bash
python3 skills/mail_invoice_archiver/scripts/cli.py doctor --json
python3 skills/mail_invoice_archiver/scripts/cli.py checklist --from-month 2026-01 --to-month 2026-05 --json
python3 skills/mail_invoice_archiver/scripts/cli.py import-files --month 2026-04 --source-dir /path/to/webmail-downloads --json
python3 skills/mail_invoice_archiver/scripts/cli.py report --month 2026-04 --json
python3 skills/mail_invoice_archiver/scripts/cli.py pack --month 2026-04 --json
python3 skills/mail_invoice_archiver/scripts/cli.py deliver --month 2026-04 --json
```

## Collecting From The Mailbox

The runtime does not talk to the mailbox. Collection happens in the browser, and there are
two ways to do it:

- **By hand in the UI** — search per month, open candidates, download attachments.
- **Through the mailbox's own endpoints** — when the browser tool can evaluate JavaScript in
  the logged-in tab, drive the provider's authenticated list/read/part APIs from inside the
  page. Faster, and it makes range-completeness checkable. See
  `skills/mail_invoice_archiver/references/webmail-api-collection.md`.

Either way the web UI stays the source of truth, the user logs in manually, and session ids
and tokens are never copied out of the browser or written to disk.

## Amount Accuracy

Amounts are cross-checked, not taken from the first `¥` in the text:

- `join_spaced_digits` repairs PDFs whose text layer spaces every glyph (`¥ 9 5 0 . 0 0`),
  which would otherwise silently report `9.00` for a 950.00 invoice.
- `extract_chinese_uppercase_total` reads 价税合计（大写） and overrides the digits when the
  two disagree, recording `pdf-chinese-uppercase-total` in `extraction_sources`.

Do not report a monthly total that has not been cross-checked against a second signal —
the uppercase total, or the amount declared in the mail subject.

## Final PDF Exports

- See `skills/mail_invoice_archiver/references/final-pdf-export-workflow.md` for the privacy-safe final export workflow.
- The Codex-installed copy lives at `codex-skills/mail-invoice-archiver/runtime/references/final-pdf-export-workflow.md`.
- Final export summaries default to grand total plus monthly totals rounded to two decimals, without itemized invoice rows unless requested.
- Final merged PDFs contain usable invoice PDF or image documents only.
- OFD-only candidates are skipped from final PDF and totals, then listed as missing a usable PDF invoice.
- Non-invoice proofs such as water statements, booking vouchers, itinerary-only files, and QR screenshots are excluded unless requested.

## Optional Feishu Delivery Helper

- The shared runtime includes an optional Feishu helper in `skills/mail_invoice_archiver/scripts/mail_invoice_archiver/feishu_delivery.py`.
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

## Testing

```bash
python3 -m unittest discover -s tests -v
```

## Security

- Do not commit local config, exported invoices, runtime databases, or credentials.
- `.gitignore` excludes local config files, ZIP exports, SQLite files, PEM keys, archive output, and the in-skill Feishu secret path.
- `skills/mail_invoice_archiver/.openclawignore` blocks accidental upload of `config/feishu/config.yaml` if someone misplaces secrets inside the skill directory.
