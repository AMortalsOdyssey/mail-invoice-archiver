from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path

from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.archive import (
    import_files,
    run_doctor,
    sanitize_filename,
    webmail_checklist,
)
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.config import RuntimeConfig
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.extractors import (
    amount_to_cents,
    extract_chinese_uppercase_total,
    extract_from_text,
    extract_from_xml,
    extract_pdf_invoice_total,
    infer_business_key,
    join_spaced_digits,
)
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.feishu_delivery import load_feishu_config
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.index import ArchiveIndex
from skills.mail_invoice_archiver.scripts.mail_invoice_archiver.models import InvoiceMetadata


class ExtractorTests(unittest.TestCase):
    def test_extract_from_text(self) -> None:
        text = (
            "发票号码：12345678901234567890 开票日期：2026/4/5 "
            "合计金额：￥100.00 开票方：示例乙方有限公司"
        )
        metadata = extract_from_text(text, source="unit-test")
        self.assertEqual(metadata.invoice_number, "12345678901234567890")
        self.assertEqual(metadata.amount_cents, 10000)
        self.assertEqual(metadata.vendor, "示例乙方有限公司")

    def test_amount_to_cents(self) -> None:
        self.assertEqual(amount_to_cents("213.00"), 21300)
        self.assertEqual(amount_to_cents("1,288.50"), 128850)
        self.assertIsNone(amount_to_cents(None))

    def test_extract_vendor_from_collapsed_layout(self) -> None:
        text = (
            "名称： 名称：\n"
            "示例甲方有限公司\n"
            "91440101ABCDEFG12\n"
            "示例乙方有限公司\n"
            "91440101HIJKLMN34\n"
        )
        metadata = extract_from_text(text, source="unit-test")
        self.assertEqual(metadata.vendor, "示例乙方有限公司")

    def test_extract_pdf_invoice_total_prefers_total_area(self) -> None:
        text = (
            "项目 A ¥80.00 税额 ¥20.00 "
            "价税合计（小写） ¥100.00 "
            "其他字段"
        )
        self.assertEqual(extract_pdf_invoice_total(text), 10000)

    def test_extract_xml_prefers_tax_included_total(self) -> None:
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <Invoice>
          <InvoiceNumber>12345678901234567890</InvoiceNumber>
          <TaxAmount>12.34</TaxAmount>
          <TotalTax-includedAmount>345.67</TotalTax-includedAmount>
        </Invoice>
        """
        metadata = extract_from_xml(xml)
        self.assertEqual(metadata.invoice_number, "12345678901234567890")
        self.assertEqual(metadata.amount_cents, 34567)
        self.assertIn("xml-tax-included-total", metadata.extraction_sources)

    def test_join_spaced_digits_repairs_per_glyph_layout(self) -> None:
        text = "发票号码 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 价税合计（小写） ¥ 9 5 0 . 0 0"
        repaired = join_spaced_digits(text)
        self.assertIn("12345678901234567890", repaired)
        self.assertEqual(extract_pdf_invoice_total(repaired), 95000)

    def test_join_spaced_digits_leaves_normal_text_alone(self) -> None:
        # Two independent numbers separated by a space must not be glued together.
        for text in ["1 950.00 2 100.00", "金额 100.00 税率 3", "合计 3 项 共 2 笔"]:
            self.assertEqual(join_spaced_digits(text), text)

    def test_chinese_uppercase_total(self) -> None:
        cases = {
            "价税合计（大写） 玖佰伍拾圆整": 95000,
            "价税合计（大写） 贰仟伍佰玖拾捌圆整": 259800,
            "价税合计（大写） 壹仟壹佰零肆圆整": 110400,
            "价税合计（大写） 叁佰捌拾伍圆贰角": 38520,
            "价税合计（大写） 壹万贰仟叁佰肆拾伍圆陆角柒分": 1234567,
            "价税合计（大写） 玖 佰 伍 拾 圆 整": 95000,
        }
        for text, cents in cases.items():
            self.assertEqual(extract_chinese_uppercase_total(text), cents, text)
        self.assertIsNone(extract_chinese_uppercase_total("没有大写金额"))

    def test_extract_from_pdf_prefers_uppercase_when_digits_are_split(self) -> None:
        # Mirrors a real invoice whose text layer spaces every glyph, which made
        # the ¥ pattern stop at the first digit and report 9.00 instead of 950.00.
        text = "¥ 9 4 0 . 5 9 ¥ 9 . 4 1 价税合计（大写） 玖佰伍拾圆整 （小写） ¥ 9 5 0 . 0 0"
        repaired = join_spaced_digits(text)
        self.assertEqual(extract_pdf_invoice_total(repaired), 95000)
        self.assertEqual(extract_chinese_uppercase_total(repaired), 95000)

    def test_business_key_prefers_invoice_number_and_amount(self) -> None:
        metadata = InvoiceMetadata(invoice_number="1234567890", amount_cents=5000)
        self.assertEqual(
            infer_business_key(metadata, "sha"),
            "invoice:1234567890:5000",
        )

    def test_sanitize_filename(self) -> None:
        self.assertEqual(sanitize_filename("发票/测试?.pdf"), "发票_测试_.pdf")


class WebmailImportTests(unittest.TestCase):
    def test_doctor_declares_protocol_sync_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RuntimeConfig(archive_root=Path(tmpdir))
            payload = run_doctor(cfg)
        self.assertEqual(payload["workflow"], "browser-webmail")
        self.assertFalse(payload["protocol_sync_enabled"])

    def test_checklist_uses_webmail_as_source_of_truth(self) -> None:
        payload = webmail_checklist("2026-01", "2026-05")
        self.assertEqual(payload["date_range"]["from_month"], "2026-01")
        self.assertTrue(any("webmail UI" in step for step in payload["workflow"]))

    def test_import_files_imports_downloaded_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "downloads"
            source.mkdir()
            (source / "发票号码12345678901234567890_金额100.00.pdf").write_bytes(_blank_pdf())
            cfg = RuntimeConfig(archive_root=root / "archive")

            result = import_files(cfg, "2026-04", source)
            summary = ArchiveIndex(cfg.database_path).month_summary("2026-04", 1000)

        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(result.imported, 1)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(summary["canonical_count"], 1)
        self.assertEqual(summary["total_amount_cents"], 10000)

    def test_import_files_skips_ofd_only_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "downloads"
            source.mkdir()
            (source / "发票号码12345678901234567890_金额100.00.ofd").write_bytes(b"not-a-real-ofd")
            cfg = RuntimeConfig(archive_root=root / "archive")

            result = import_files(cfg, "2026-04", source)
            summary = ArchiveIndex(cfg.database_path).month_summary("2026-04", 1000)

        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(result.imported, 0)
        self.assertEqual(result.skipped, 1)
        self.assertEqual(summary["canonical_count"], 0)
        self.assertEqual(summary["total_amount_cents"], 0)
        self.assertIn("no usable PDF/image invoice", summary["failures"][0]["failure_reason"])


class IndexTests(unittest.TestCase):
    def test_month_summary_counts_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RuntimeConfig(archive_root=Path(tmpdir))
            index = ArchiveIndex(cfg.database_path)
            metadata = InvoiceMetadata(invoice_number="111", amount_cents=1000, extraction_sources=["unit"])
            index.insert_artifact(
                account="webmail",
                folder="browser-download",
                message_uid="1",
                part_ref="part-1",
                source_kind="webmail-download",
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
                account="webmail",
                folder="browser-download",
                message_uid="2",
                part_ref="part-1",
                source_kind="webmail-download",
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

    def test_month_summary_includes_current_month_duplicate_of_older_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = RuntimeConfig(archive_root=Path(tmpdir))
            index = ArchiveIndex(cfg.database_path)
            metadata = InvoiceMetadata(invoice_number="222", amount_cents=90000, extraction_sources=["unit"])
            saved_id = index.insert_artifact(
                account="webmail",
                folder="browser-download",
                message_uid="1",
                part_ref="part-1",
                source_kind="webmail-download",
                source_ref="march.pdf",
                received_at="2026-03-28T11:27:07+08:00",
                sender="sender",
                subject="subject",
                preview="preview",
                local_path="/tmp/march.pdf",
                sha256="sha-march",
                mime_type="application/pdf",
                extension="pdf",
                metadata=metadata,
                business_key="invoice:222:90000",
                status="saved",
                duplicate_of_id=None,
            )
            index.insert_artifact(
                account="webmail",
                folder="browser-download",
                message_uid="2",
                part_ref="part-1",
                source_kind="webmail-download",
                source_ref="april.pdf",
                received_at="2026-04-02T11:27:07+08:00",
                sender="sender",
                subject="subject",
                preview="preview",
                local_path=None,
                sha256="sha-april",
                mime_type="application/pdf",
                extension="pdf",
                metadata=metadata,
                business_key="invoice:222:90000",
                status="duplicate",
                duplicate_of_id=saved_id,
            )
            summary = index.month_summary("2026-04", 1000)
            self.assertEqual(summary["canonical_count"], 1)
            self.assertEqual(summary["duplicate_count"], 1)
            self.assertEqual(summary["total_amount_cents"], 90000)
            index.close()


class DeliveryConfigTests(unittest.TestCase):
    def test_load_feishu_config_prefers_env(self) -> None:
        old = {
            "MAIL_INVOICE_ARCHIVER_FEISHU_APP_ID": os.environ.get("MAIL_INVOICE_ARCHIVER_FEISHU_APP_ID"),
            "MAIL_INVOICE_ARCHIVER_FEISHU_APP_SECRET": os.environ.get("MAIL_INVOICE_ARCHIVER_FEISHU_APP_SECRET"),
            "MAIL_INVOICE_ARCHIVER_FEISHU_RECEIVE_ID_TYPE": os.environ.get("MAIL_INVOICE_ARCHIVER_FEISHU_RECEIVE_ID_TYPE"),
        }
        try:
            os.environ["MAIL_INVOICE_ARCHIVER_FEISHU_APP_ID"] = "cli_demo"
            os.environ["MAIL_INVOICE_ARCHIVER_FEISHU_APP_SECRET"] = "secret_demo"
            os.environ["MAIL_INVOICE_ARCHIVER_FEISHU_RECEIVE_ID_TYPE"] = "chat_id"
            config = load_feishu_config(Path("/tmp/nonexistent-skill-root"))
            self.assertEqual(config["app_id"], "cli_demo")
            self.assertEqual(config["app_secret"], "secret_demo")
            self.assertEqual(config["receive_id_type"], "chat_id")
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_load_feishu_config_rejects_in_skill_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_root = Path(tmpdir)
            config_dir = skill_root / "config" / "feishu"
            config_dir.mkdir(parents=True)
            (config_dir / "config.yaml").write_text("feishu:\n  app_id: test\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                load_feishu_config(skill_root)


class CodexWrapperTests(unittest.TestCase):
    def test_codex_wrapper_uses_bundled_runtime(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        wrapper = repo_root / "codex-skills" / "mail-invoice-archiver"
        runner = wrapper / "scripts" / "run-mail-invoice-archiver.sh"
        script = runner.read_text(encoding="utf-8")

        self.assertIn("../runtime/scripts/cli.py", script)
        self.assertTrue((wrapper / "runtime" / "scripts" / "cli.py").is_file())


def _blank_pdf() -> bytes:
    try:
        from pypdf import PdfWriter
    except Exception as exc:
        raise unittest.SkipTest("pypdf is unavailable") from exc
    pdf_buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(pdf_buffer)
    return pdf_buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
