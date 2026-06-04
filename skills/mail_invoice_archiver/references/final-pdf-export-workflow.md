# Final PDF Export Workflow

Use this reference when the user asks for a multi-month invoice folder, one merged PDF, a final amount summary, or follow-up include/exclude adjustments.

## Privacy

- Do not write personal mailbox addresses, local filesystem paths, real names, real invoice numbers, or private amounts into published skill docs, examples, tests, commit messages, or issue notes.
- Use placeholders such as `<mailbox>`, `<export-root>`, `<invoice-number>`, `<amount>`, and `YYYY-MM` when describing examples.
- Keep real downloaded invoices, archive databases, intermediate exports, screenshots, and local config out of the skill repository.

## Canonical Files

- Build the final source folder from representative invoice documents only.
- Prefer one canonical artifact per `invoice number + amount`.
- When the same invoice exists in multiple formats, prefer a readable original PDF or image over XML, OFD, or ZIP.
- OFD may be retained in the raw archive for traceability, but it is not acceptable as a default final invoice artifact.
- If an invoice candidate only has OFD and no readable original PDF or image, skip it from the final source folder, merged PDF, and amount totals.
- Never create OFD-derived text pages, screenshots, placeholder pages, or forced conversions for the final merged PDF.
- List OFD-only candidates separately as skipped because they do not have a usable PDF invoice representation.
- Exclude hotel folios, water statements, booking vouchers, itinerary-only documents, QR-code or scan-to-issue screenshots, and other non-invoice proofs unless the user explicitly asks to include them.
- If the user says they manually removed, restored, or replaced files, re-scan the final source folder before rebuilding the merged PDF and summary.

## Amount Rules

- The default final summary should show only the grand total and monthly totals, rounded to two decimal places. Do not list every invoice unless the user asks for itemized detail.
- Exclude user-rejected invoices from both the merged PDF and all amount totals.
- Include user-restored invoice files in both the merged PDF and all amount totals.
- Exclude OFD-only candidates from both the merged PDF and all amount totals.
- For XML-backed travel or platform invoices, prefer the tax-included total field, such as `TotalTax-includedAmount` or a provider-equivalent field, over the first visible amount extracted from PDF text.
- If a file contains several monetary values, prefer the official invoice total or `价税合计` amount. Do not use tax amount, tax base, deposit, service fee, or visible subtotal by accident.
- If the amount source is ambiguous, pause and report exactly which field is being used before finalizing totals.

## Merged PDF Requirements

- Merge only usable invoice PDF or image documents.
- Never add OFD conversions, OFD text dumps, OFD screenshots, OCR placeholder pages, or other OFD-derived pages to the final merged PDF.
- Do not add cover pages, summary pages, QR screenshots, water statements, or backup pages unless the user explicitly requests them.
- Keep source files organized by month when producing a multi-month package.
- The final merged PDF should contain one representative document per included invoice.
- Rebuild the merged PDF after any include/exclude change. Do not patch totals without regenerating the final PDF.
- Render the final PDF page by page and detect blank or placeholder pages visually. Page count and text extraction alone are not enough.
- Remove or replace blank pages before delivery. Common sources are bad OFD conversion, image-to-PDF placeholders, and duplicated blank trailing pages in vendor PDFs.
- Confirm the final page count matches the expected count after accounting for legitimate multi-page invoice files.
- Keep old, backup, and intermediate merged PDFs outside the final export folder, or delete them when finalizing, so the user does not open the wrong version.

## Iterative Adjustment Loop

1. Record the user's latest include/exclude instructions in neutral terms, such as "exclude invoice numbers in the user-provided block" or "include the restored travel invoice PDFs".
2. Rebuild the candidate set from the current source folder plus any explicit restored files.
3. Remove non-invoices, user-excluded invoices, and OFD-only candidates from the final candidate set.
4. Deduplicate by `invoice number + amount`, keeping the most user-readable artifact.
5. Recompute totals from the rebuilt candidate set, not from stale earlier reports.
6. Regenerate the merged PDF from the rebuilt candidate set.
7. Render and inspect the merged PDF for blank, placeholder, or wrong-format pages.
8. Clean final deliverables so only the current source folder, current merged PDF, and current summary remain in the final export location.
9. Report the final grand total and monthly totals only, unless the user asks for itemized rows.

## Webmail Reconciliation

- If the user points out missing months or messages, do not assume the IMAP sync result is complete.
- Reconcile against the provider web UI, mailbox search, or message list when available.
- Search by month boundaries, invoice keywords, senders, and attachment indicators.
- After finding missed messages, archive them and rebuild the final PDF and totals from the updated source set.

## Validation Checklist

- [ ] The source folder contains only included invoice documents.
- [ ] User-excluded invoice numbers or files are absent from the final PDF and totals.
- [ ] User-restored invoice files are present in the final PDF and totals.
- [ ] Non-invoice documents are absent unless explicitly requested.
- [ ] OFD-only candidates are absent from the final PDF and totals, and are listed as skipped.
- [ ] XML-backed totals use tax-included total fields when available.
- [ ] The summary has grand total plus monthly totals rounded to two decimals.
- [ ] No itemized invoice list is shown by default.
- [ ] The merged PDF has been rendered and checked for blank or placeholder pages.
- [ ] Old or intermediate exports are not mixed into the final deliverables.

## What To Report

- State the date range covered.
- State where the final folder, merged PDF, and summary were produced, using user-safe references in public docs.
- Show the grand total and monthly totals to two decimals.
- Mention any excluded categories, such as non-invoice statements, QR screenshots, or OFD-only candidates, without exposing private invoice details.
- Mention any residual uncertainty, missing files, or invoice candidates skipped because no usable PDF invoice was available.
