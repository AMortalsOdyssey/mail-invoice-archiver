from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.auth import (
    available_auth_methods,
    resolve_credentials,
    setup_required_payload,
)
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.archive import sanitize_filename
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.config import RuntimeConfig
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.providers import (
    default_system_service_name,
    get_mail_provider,
    list_mail_providers,
)
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.extractors import (
    amount_to_cents,
    extract_from_text,
    infer_business_key,
)
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.index import ArchiveIndex
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.models import InvoiceMetadata
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.setup_wizard import run_setup


class ExtractorTests(unittest.TestCase):
    def test_extract_from_text(self) -> None:
        text = (
            "发票号码：26442000003702874156 开票日期：2026/4/5 "
            "合计金额：￥246 开票方：广州宝园阁餐饮有限公司"
        )
        metadata = extract_from_text(text, source="unit-test")
        self.assertEqual(metadata.invoice_number, "26442000003702874156")
        self.assertEqual(metadata.amount_cents, 24600)
        self.assertEqual(metadata.vendor, "广州宝园阁餐饮有限公司")

    def test_amount_to_cents(self) -> None:
        self.assertEqual(amount_to_cents("213.00"), 21300)
        self.assertEqual(amount_to_cents("1,288.50"), 128850)
        self.assertIsNone(amount_to_cents(None))

    def test_business_key_prefers_invoice_number_and_amount(self) -> None:
        metadata = InvoiceMetadata(invoice_number="1234567890", amount_cents=5000)
        self.assertEqual(
            infer_business_key(metadata, "sha"),
            "invoice:1234567890:5000",
        )

    def test_sanitize_filename(self) -> None:
        self.assertEqual(sanitize_filename("发票/测试?.pdf"), "发票_测试_.pdf")


class IndexTests(unittest.TestCase):
    def test_month_summary_counts_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RuntimeConfig(archive_root=Path(tmpdir))
            index = ArchiveIndex(cfg.database_path)
            metadata = InvoiceMetadata(invoice_number="111", amount_cents=1000, extraction_sources=["unit"])
            index.insert_artifact(
                account="a@b.com",
                folder="INBOX",
                message_uid="1",
                part_ref="part-1",
                source_kind="attachment",
                source_ref="invoice.pdf",
                received_at="2026-04-03T11:27:07+08:00",
                sender="sender",
                subject="subject",
                preview="preview",
                local_path="/tmp/invoice.pdf",
                sha256="sha1",
                mime_type="application/pdf",
                extension="pdf",
                metadata=metadata,
                business_key="invoice:111:1000",
                status="saved",
                duplicate_of_id=None,
            )
            index.insert_artifact(
                account="a@b.com",
                folder="INBOX",
                message_uid="2",
                part_ref="part-1",
                source_kind="attachment",
                source_ref="invoice-dup.pdf",
                received_at="2026-04-04T11:27:07+08:00",
                sender="sender",
                subject="subject",
                preview="preview",
                local_path=None,
                sha256="sha2",
                mime_type="application/pdf",
                extension="pdf",
                metadata=metadata,
                business_key="invoice:111:1000",
                status="duplicate",
                duplicate_of_id=1,
            )
            summary = index.month_summary("2026-04", 1000)
            self.assertEqual(summary["canonical_count"], 1)
            self.assertEqual(summary["duplicate_count"], 1)
            self.assertEqual(summary["total_amount_cents"], 1000)
            index.close()


class SetupTests(unittest.TestCase):
    def test_config_provider_setup_and_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            result = run_setup(
                config_path=config_path,
                mail_provider="gmail",
                provider="config",
                email="demo@example.com",
                secret="secret-123",
                interactive=False,
            )
            self.assertTrue(result["setup_complete"])
            config = RuntimeConfig.load(config_path)
            self.assertEqual(config.mail_provider, "gmail")
            self.assertEqual(config.host_candidates, ["imap.gmail.com"])
            credentials = resolve_credentials(config)
            self.assertEqual(credentials.email, "demo@example.com")
            self.assertEqual(credentials.secret, "secret-123")

    def test_env_provider_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            run_setup(
                config_path=config_path,
                provider="env",
                email="demo@example.com",
                env_email_var="TEST_MAIL_EMAIL",
                env_secret_var="TEST_MAIL_SECRET",
                interactive=False,
            )
            config = RuntimeConfig.load(config_path)
            old_email = os.environ.get("TEST_MAIL_EMAIL")
            old_secret = os.environ.get("TEST_MAIL_SECRET")
            try:
                os.environ["TEST_MAIL_EMAIL"] = "demo@example.com"
                os.environ["TEST_MAIL_SECRET"] = "secret-xyz"
                credentials = resolve_credentials(config)
                self.assertEqual(credentials.secret, "secret-xyz")
            finally:
                if old_email is None:
                    os.environ.pop("TEST_MAIL_EMAIL", None)
                else:
                    os.environ["TEST_MAIL_EMAIL"] = old_email
                if old_secret is None:
                    os.environ.pop("TEST_MAIL_SECRET", None)
                else:
                    os.environ["TEST_MAIL_SECRET"] = old_secret

    def test_windows_system_provider_resolution(self) -> None:
        config = RuntimeConfig(
            email_address="demo@example.com",
            auth_provider="system",
            keychain_service="mail-invoice-archiver/126-auth",
        )
        with patch(
            "skills.mail_invoice_archiver.scripts.mail_invoice_archiver.auth.system_store_spec",
            return_value={
                "platform": "Windows",
                "available": True,
                "recommended": True,
                "label": "Windows Credential Manager",
                "notes": "Uses Windows Credential Manager. Best option on Windows.",
            },
        ), patch(
            "skills.mail_invoice_archiver.scripts.mail_invoice_archiver.auth.read_system_secret",
            return_value=("demo@example.com", "secret-win"),
        ):
            credentials = resolve_credentials(config)
        self.assertEqual(credentials.email, "demo@example.com")
        self.assertEqual(credentials.secret, "secret-win")
        self.assertIn("Windows Credential Manager", credentials.detail)

    def test_windows_system_method_is_advertised(self) -> None:
        with patch(
            "skills.mail_invoice_archiver.scripts.mail_invoice_archiver.auth.system_store_spec",
            return_value={
                "platform": "Windows",
                "available": True,
                "recommended": True,
                "label": "Windows Credential Manager",
                "notes": "Uses Windows Credential Manager. Best option on Windows.",
            },
        ):
            methods = available_auth_methods()
        system = methods[0]
        self.assertEqual(system["provider"], "system")
        self.assertTrue(system["available"])
        self.assertTrue(system["recommended"])
        self.assertIn("Windows Credential Manager", system["notes"])

    def test_setup_required_payload(self) -> None:
        payload = setup_required_payload(Path("/tmp/demo.toml"))
        self.assertTrue(payload["setup_required"])
        self.assertEqual(payload["config_path"], "/tmp/demo.toml")
        self.assertGreaterEqual(len(payload["available_auth_methods"]), 4)
        self.assertGreaterEqual(len(payload["available_mail_providers"]), 4)


class ProviderTests(unittest.TestCase):
    def test_detects_163_from_email(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                '\n'.join(
                    [
                        'mail_provider = "auto"',
                        'archive_root = "/tmp/archive"',
                        'imap_port = 993',
                        '',
                        '[auth]',
                        'provider = "env"',
                        'email = "demo@163.com"',
                        'service = ""',
                        'env_email_var = "TEST_MAIL_EMAIL"',
                        'env_secret_var = "TEST_MAIL_SECRET"',
                        'secret = ""',
                        '',
                    ]
                ),
                encoding="utf-8",
            )
            config = RuntimeConfig.load(config_path)
        self.assertEqual(config.mail_provider, "163")
        self.assertEqual(config.host_candidates, ["imap.163.com"])
        self.assertTrue(config.imap_send_id)

    def test_detects_gmail_from_email(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                '\n'.join(
                    [
                        'mail_provider = "auto"',
                        'archive_root = "/tmp/archive"',
                        'imap_port = 993',
                        '',
                        '[auth]',
                        'provider = "env"',
                        'email = "demo@gmail.com"',
                        'service = ""',
                        'env_email_var = "TEST_MAIL_EMAIL"',
                        'env_secret_var = "TEST_MAIL_SECRET"',
                        'secret = ""',
                        '',
                    ]
                ),
                encoding="utf-8",
            )
            config = RuntimeConfig.load(config_path)
        self.assertEqual(config.mail_provider, "gmail")
        self.assertEqual(config.host_candidates, ["imap.gmail.com"])
        self.assertFalse(config.imap_send_id)
        self.assertEqual(config.keychain_service, default_system_service_name("gmail"))

    def test_provider_list_includes_rollout_targets(self) -> None:
        providers = list_mail_providers()
        provider_ids = {item["id"] for item in providers}
        self.assertIn("126", provider_ids)
        self.assertIn("163", provider_ids)
        self.assertIn("gmail", provider_ids)
        gmail = get_mail_provider("gmail")
        self.assertEqual(gmail.secret_label, "app password")


if __name__ == "__main__":
    unittest.main()
