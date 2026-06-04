# Browser-First Compatibility Notes

## Source Of Truth

- Mailbox web UI search and visible message lists are the source of truth for invoice discovery.
- Do not use protocol-level mailbox sync for completeness checks. It can miss messages, differ from provider search behavior, or hide webmail-only indexing.
- The runtime starts after files are downloaded from webmail. It imports, deduplicates, summarizes, and packages local files.

## Webmail Search Practices

- Search each requested month explicitly with date boundaries.
- Use full-text search, attachment filters, visible pagination, folder/category navigation, and provider invoice helpers when available.
- Search invoice terms such as `发票`, `电子发票`, `invoice`, `票据`, `普票`, and `专票`.
- Open candidate messages and download original invoice PDF or image attachments.
- Keep a neutral local month source folder for files downloaded from the web UI.
- If the user says a month or invoice is missing, go back to the web UI and verify visually instead of trusting a prior local import.

## Final Export Rules

- Use readable original PDF or image files for the final export.
- OFD, XML, and ZIP may be useful raw clues, but they are not final invoice documents by themselves.
- For final merged PDF exports, skip OFD-only candidates from the final source folder, merged PDF, and totals.
- List OFD-only candidates as skipped because no usable PDF invoice was available.
- Do not create OFD-derived text pages, screenshots, placeholder pages, or forced conversions for the final merged PDF.
- Exclude non-invoice proofs such as hotel folios, water statements, booking vouchers, itinerary-only files, QR-code screenshots, and scan-to-issue placeholders unless explicitly requested.

## Amount Extraction

- Do not take the first visible currency amount from extracted PDF text.
- Prefer invoice total areas such as `价税合计`.
- For XML-backed travel or platform invoices, use XML only as an amount extraction aid when a usable PDF/image invoice is present.
- Prefer tax-included total fields such as `TotalTax-includedAmount` or provider-equivalent names.

## Reporting

- Default final summaries should show grand total and monthly totals rounded to two decimals.
- Do not itemize every invoice unless requested.
- Report skipped candidates and the reason, especially missing usable PDF invoices.
