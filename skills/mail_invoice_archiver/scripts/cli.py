#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap() -> None:
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def main() -> int:
    _bootstrap()
    from mail_invoice_archiver.cli import main as inner_main

    return inner_main()


if __name__ == "__main__":
    raise SystemExit(main())
