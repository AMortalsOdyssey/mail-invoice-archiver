---
name: mail_invoice_archiver
description: Use the mailbox web UI as the source of truth for invoice discovery, guide browser-based invoice downloads, import downloaded invoice files, deduplicate by invoice number and amount, and prepare monthly summaries plus delivery bundles. Use when OpenClaw needs to collect invoice mail, organize downloaded invoice files, package invoices, or summarize totals.
metadata: {"openclaw":{"name":"mail_invoice_archiver","displayName":"Mail Invoice Archiver","requires":["python3"],"requiresNetwork":false}}
---

# Mail Invoice Archiver

## Source Of Truth

- Use the user's authenticated mailbox web UI as the source of truth.
- Search and verify in the web UI by month boundaries, invoice keywords, senders, and attachment indicators.
- Download original usable invoice PDF or image files from the web UI, then import those files locally.

## Quick Start

- Read [references/final-pdf-export-workflow.md](references/final-pdf-export-workflow.md) before packaging multi-month folders, merged PDFs, monthly totals, or user-driven include/exclude edits.
- Run `python3 {baseDir}/scripts/cli.py doctor --json` to verify local archive paths and tooling.
- Run `python3 {baseDir}/scripts/cli.py checklist --from-month YYYY-MM --to-month YYYY-MM --json` to get the browser/webmail search checklist.
- After downloading files from webmail into a local month folder, run:
  `python3 {baseDir}/scripts/cli.py import-files --month YYYY-MM --source-dir /path/to/downloads --json`
- Run `python3 {baseDir}/scripts/cli.py report --month YYYY-MM --json` to inspect totals, duplicates, conflicts, skipped files, and failures.
- Run `python3 {baseDir}/scripts/cli.py pack --month YYYY-MM --json` or `deliver --month YYYY-MM --json` to prepare zip plus summary files.

## Browser Workflow

1. Open the user's logged-in mailbox in the browser. If the user is not logged in, ask them to log in manually.
2. Search each requested month explicitly. Use webmail date filters, full-text search, attachment filters, and visible pagination.
3. Use invoice keywords such as `发票`, `电子发票`, `invoice`, `票据`, `普票`, and `专票`.
4. Open candidate messages and download original PDF or image invoice attachments.
5. Keep a local source folder per month for files downloaded from the web UI.
6. Import that folder with `import-files`, then rebuild report, package, and final merged PDF from the imported set.
7. If the user changes include/exclude decisions, rebuild the candidate set, totals, and merged PDF together.

When the browser tool can evaluate JavaScript in the logged-in tab, prefer
[references/webmail-api-collection.md](references/webmail-api-collection.md) over paging the
UI by hand: it drives the mailbox's own authenticated endpoints for listing, attachment
metadata, and attachment bytes, and it covers range-completeness checks, the Chrome
multi-file download block, template decoration images, and link-only invoices. The web UI
remains the source of truth; only the reading method changes.

## Amount Accuracy

- Cross-check every monthly total against a second signal before reporting it: 价税合计（大写）
  from the PDF, or the amount declared in the mail subject.
- Watch for PDFs whose text layer spaces every glyph (`¥ 9 5 0 . 0 0`). See the amount
  extraction section of [references/compatibility-notes.md](references/compatibility-notes.md).

## Final Export Rules

- Final merged PDFs must contain usable invoice PDF or image documents only.
- OFD may be retained outside the final export as a raw clue, but OFD-only candidates must be skipped from the final source folder, merged PDF, and totals. List them as skipped because no usable PDF invoice was available.
- Never force OFD-derived text pages, screenshots, placeholder pages, or conversions into the final merged PDF.
- Exclude hotel folios, water statements, booking vouchers, itinerary-only files, QR-code screenshots, scan-to-issue placeholders, and other non-invoice proofs unless explicitly requested.
- Prefer original readable PDF or image artifacts over XML, OFD, or ZIP.
- For XML-backed travel or platform invoices, use XML only as an amount extraction aid when a usable PDF/image invoice is present. Prefer tax-included total fields such as `TotalTax-includedAmount`.
- Final amount summaries default to grand total plus monthly totals rounded to two decimals. Do not list every invoice unless requested.
- Render-check merged PDFs page by page for blank or placeholder pages before delivery.
- Keep old or intermediate PDFs out of the final export folder.

## Resources

- Runtime: [scripts/cli.py](scripts/cli.py)
- Final PDF export workflow: [references/final-pdf-export-workflow.md](references/final-pdf-export-workflow.md)
- Browser-first notes: [references/compatibility-notes.md](references/compatibility-notes.md)
