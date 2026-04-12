# Compatibility Notes

## Real-World Findings

- 126 mailbox IMAP worked with a Keychain-stored authorization code.
- Direct `imap.126.com` TLS handshakes were unreliable in the tested terminal environment.
- `appleimap.126.com` succeeded and allowed a real login with the 126 account.
- After login, selecting `INBOX` failed with `Unsafe Login` unless the client sent a realistic IMAP `ID` first.
- Using an Apple Mail style client `ID` allowed `SELECT INBOX` and normal mailbox reads.
- During the live test, the mailbox sent a new-device login alert, which confirms the login path was real.
- The runtime now implements `system` auth with macOS Keychain on macOS and Windows Credential Manager on Windows.
- The Windows Credential Manager path is implemented and covered by unit tests, but it was not live-tested in this macOS session.

## Pitfalls

- Do not assume `imap.126.com` is the best production host for every environment.
- Do not assume macOS Keychain is the only acceptable secret store. The runtime now supports `system`, `env`, `config`, and `prompt` modes, and `system` now covers Windows Credential Manager too.
- Do not rely on file names for invoice identity. Re-sent messages and alternate formats can represent the same invoice.
- Do not assume OCR is always available. The runtime falls back to XML, PDF text, subject, and body extraction when OCR tools are missing.
- Do not auto-merge invoices when the invoice number matches but the amount differs; flag them as conflicts.
- Do not treat chat delivery as SMTP. The runtime only prepares the zip and summary; the agent layer must attach the zip in the current chat.
