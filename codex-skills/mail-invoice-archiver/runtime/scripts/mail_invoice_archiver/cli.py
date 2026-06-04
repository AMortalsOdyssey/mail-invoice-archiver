from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .archive import build_report, import_files, pack_month, run_doctor, webmail_checklist
from .config import RuntimeConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Organize invoice files downloaded from the mailbox web UI."
    )
    parser.add_argument("--config", type=Path, default=None, help="Optional TOML config path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check local archive tooling and paths.")
    doctor.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    doctor.set_defaults(handler=cmd_doctor)

    checklist = subparsers.add_parser("checklist", help="Emit the browser/webmail search checklist.")
    checklist.add_argument("--from-month", default=None)
    checklist.add_argument("--to-month", default=None)
    checklist.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    checklist.set_defaults(handler=cmd_checklist)

    import_cmd = subparsers.add_parser("import-files", help="Import files downloaded from webmail.")
    import_cmd.add_argument("--month", required=True)
    import_cmd.add_argument("--source-dir", type=Path, required=True)
    import_cmd.add_argument("--no-recursive", action="store_true")
    import_cmd.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    import_cmd.set_defaults(handler=cmd_import_files)

    report = subparsers.add_parser("report", help="Build a month summary from the local index.")
    report.add_argument("--month", required=True)
    report.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    report.set_defaults(handler=cmd_report)

    pack = subparsers.add_parser("pack", help="Build zip and summary files for a month.")
    pack.add_argument("--month", required=True)
    pack.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    pack.set_defaults(handler=cmd_pack)

    deliver = subparsers.add_parser("deliver", help="Prepare a month package for chat delivery.")
    deliver.add_argument("--month", required=True)
    deliver.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    deliver.set_defaults(handler=cmd_deliver)
    return parser


def _config(args: argparse.Namespace) -> RuntimeConfig:
    return RuntimeConfig.load(args.config)


def cmd_doctor(args: argparse.Namespace) -> dict[str, object]:
    return run_doctor(_config(args))


def cmd_checklist(args: argparse.Namespace) -> dict[str, object]:
    return webmail_checklist(args.from_month, args.to_month)


def cmd_import_files(args: argparse.Namespace) -> dict[str, object]:
    result = import_files(
        _config(args),
        args.month,
        args.source_dir,
        recursive=not args.no_recursive,
    )
    return {
        "month": result.month,
        "scanned_files": result.scanned_files,
        "imported": result.imported,
        "duplicates": result.duplicates,
        "conflicts": result.conflicts,
        "skipped": result.skipped,
        "failures": result.failures,
        "saved_paths": result.saved_paths,
        "skipped_paths": result.skipped_paths,
    }


def cmd_report(args: argparse.Namespace) -> dict[str, object]:
    return build_report(_config(args), args.month)


def cmd_pack(args: argparse.Namespace) -> dict[str, object]:
    result = pack_month(_config(args), args.month)
    return {
        "month": result.month,
        "zip_path": result.zip_path,
        "summary_path": result.summary_path,
        "summary_json_path": result.summary_json_path,
    }


def cmd_deliver(args: argparse.Namespace) -> dict[str, object]:
    config = _config(args)
    result = pack_month(config, args.month)
    return {
        "month": result.month,
        "delivery_channel": config.chat_delivery_channel,
        "attachment_path": result.zip_path,
        "summary_path": result.summary_path,
        "summary_json_path": result.summary_json_path,
        "instructions": (
            "Attach the zip file to the current chat, paste the markdown summary, "
            "and call out skipped files plus any failures."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = args.handler(args)
    except RuntimeError as exc:
        payload = {"error": str(exc)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if "error" not in payload else 1


if __name__ == "__main__":
    raise SystemExit(main())
