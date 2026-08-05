from __future__ import annotations

import hashlib
import io
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .config import RuntimeConfig
from .models import AttachmentPayload, InvoiceMetadata, ParsedMessage

AMOUNT_PATTERNS = [
    re.compile(r"价税合计（小写）\s*[¥￥]\s*([0-9]+(?:\.[0-9]{1,2})?)"),
    re.compile(r"价税合计\(小写\)\s*[¥￥]\s*([0-9]+(?:\.[0-9]{1,2})?)"),
    re.compile(r"(?:发票金额|合计金额|金额)[:：]?\s*[¥￥]?\s*([0-9]+(?:\.[0-9]{1,2})?)"),
    re.compile(r"[¥￥]\s*([0-9]+(?:\.[0-9]{1,2})?)"),
]
INVOICE_NUMBER_PATTERNS = [
    re.compile(r"发票号码[:：]?\s*([0-9]{8,20})"),
    re.compile(r"\b([0-9]{20})\b"),
]
INVOICE_CODE_PATTERNS = [
    re.compile(r"发票代码[:：]?\s*([0-9]{8,20})"),
]
DATE_PATTERNS = [
    re.compile(r"开票日期[:：]?\s*([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})"),
    re.compile(r"开票时间[:：]?\s*([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})"),
]
VENDOR_PATTERNS = [
    re.compile(r"(?:开票方|销方名称)[:：]?\s*([^\n\r\s，,；;]+(?:有限公司|事务所|餐饮发展有限公司|餐饮有限公司|酒店))"),
    re.compile(r"名称[:：]?\s*名称[:：]?[\s\S]*?\n\s*[^\n\r]+\n\s*[^\n\r]+\n\s*([^\n\r]+?(?:有限公司|事务所|餐饮发展有限公司|餐饮有限公司|酒店))\n", re.S),
]
URL_PATTERN = re.compile(r"https?://[^\s<>\"]+")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def probable_invoice_message(message: ParsedMessage, config: RuntimeConfig) -> bool:
    haystack = " ".join([message.sender, message.subject, message.preview]).lower()
    score = 0
    for keyword in config.keyword_allowlist:
        if keyword.lower() in haystack:
            score += 2
    for keyword in config.keyword_denylist:
        if keyword.lower() in haystack:
            score -= 3
    for attachment in message.attachments:
        if attachment.extension in config.candidate_extensions:
            score += 2
    return score >= 2


def probable_invoice_attachment(
    attachment: AttachmentPayload,
    message: ParsedMessage,
    config: RuntimeConfig,
) -> bool:
    haystack = " ".join(
        [
            attachment.filename,
            message.subject,
            message.preview,
            message.sender,
        ]
    ).lower()
    if attachment.extension in config.candidate_extensions:
        return True
    return any(keyword.lower() in haystack for keyword in config.keyword_allowlist)


def extract_urls(message: ParsedMessage, config: RuntimeConfig) -> list[str]:
    urls = URL_PATTERN.findall(message.body_text)
    if not urls:
        return []
    if not config.download_link_domains:
        return urls
    filtered: list[str] = []
    for url in urls:
        for domain in config.download_link_domains:
            if domain in url:
                filtered.append(url)
                break
    return filtered


def extract_invoice_metadata(
    message: ParsedMessage,
    attachment: AttachmentPayload | None = None,
) -> InvoiceMetadata:
    message_metadata = extract_from_text(
        " ".join([message.subject, message.preview, message.body_text]),
        source="message-text",
    )
    metadata = message_metadata
    if attachment:
        filename_metadata = extract_from_text(attachment.filename, source="attachment-filename")
        if attachment.extension == "xml":
            metadata = message_metadata.merge(filename_metadata).merge(extract_from_xml(attachment.data))
        elif attachment.extension == "pdf":
            metadata = extract_from_pdf(attachment.data).merge(filename_metadata).merge(message_metadata)
        elif attachment.extension == "ofd":
            metadata = extract_from_ofd(attachment.data).merge(filename_metadata).merge(message_metadata)
        elif attachment.extension in {"png", "jpg", "jpeg"}:
            metadata = extract_from_image(attachment.data, attachment.extension).merge(filename_metadata).merge(
                message_metadata
            )
        else:
            metadata = filename_metadata.merge(message_metadata)
    return metadata


def extract_from_text(text: str, source: str) -> InvoiceMetadata:
    metadata = InvoiceMetadata(extraction_sources=[source])
    metadata.invoice_number = _first_match(INVOICE_NUMBER_PATTERNS, text)
    metadata.invoice_code = _first_match(INVOICE_CODE_PATTERNS, text)
    amount_text = _first_match(AMOUNT_PATTERNS, text)
    metadata.amount_cents = amount_to_cents(amount_text)
    metadata.invoice_date = _first_match(DATE_PATTERNS, text)
    metadata.vendor = extract_vendor(text)
    if metadata.invoice_number or metadata.amount_cents is not None:
        metadata.confidence = "medium"
    return metadata


def extract_vendor(text: str) -> str | None:
    layout_vendor = _extract_vendor_from_invoice_layout(text)
    if layout_vendor:
        return layout_vendor
    return _first_match(VENDOR_PATTERNS, text)


def _extract_vendor_from_invoice_layout(text: str) -> str | None:
    normalized = text.replace('\r', '')
    marker = '名称： 名称：'
    idx = normalized.find(marker)
    if idx == -1:
        return None
    tail = normalized[idx + len(marker):]
    lines = [line.strip() for line in tail.split('\n')]
    candidates = [line for line in lines if line]
    if len(candidates) < 4:
        return None
    for i in range(len(candidates) - 3):
        buyer_name, buyer_tax, seller_name, seller_tax = candidates[i : i + 4]
        if not _looks_like_tax_id(buyer_tax):
            continue
        if not _looks_like_tax_id(seller_tax):
            continue
        if seller_name and _looks_like_vendor_name(seller_name):
            return seller_name
    return None


def extract_from_xml(data: bytes) -> InvoiceMetadata:
    try:
        root = ET.fromstring(data)
        text = " ".join((element.text or "") for element in root.iter())
    except ET.ParseError:
        return InvoiceMetadata(extraction_sources=["xml-parse-failed"])
    metadata = extract_from_text(text, source="xml")
    total_tax_included = _extract_xml_tax_included_total(root)
    if total_tax_included is not None:
        metadata.amount_cents = total_tax_included
        metadata.extraction_sources.append("xml-tax-included-total")
    if metadata.invoice_number or metadata.amount_cents is not None:
        metadata.confidence = "high"
    return metadata


def _extract_xml_tax_included_total(root: ET.Element) -> int | None:
    preferred_names = {
        "totaltaxincludedamount",
        "totaltaxinclusiveamount",
        "taxincludedamount",
        "taxinclusiveamount",
    }
    for element in root.iter():
        local_name = str(element.tag).rsplit("}", 1)[-1]
        normalized = re.sub(r"[-_\s]", "", local_name).lower()
        if normalized not in preferred_names:
            continue
        amount = amount_to_cents(element.text)
        if amount is not None:
            return amount
    return None


def extract_from_pdf(data: bytes) -> InvoiceMetadata:
    try:
        from pypdf import PdfReader
    except Exception:
        return InvoiceMetadata(extraction_sources=["pdf-missing-pypdf"])
    try:
        reader = PdfReader(io.BytesIO(data))
        text = " ".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return InvoiceMetadata(extraction_sources=["pdf-read-failed"])
    text = join_spaced_digits(text)
    metadata = extract_from_text(text, source="pdf-text")
    pdf_amount = extract_pdf_invoice_total(text)
    if pdf_amount is not None:
        metadata.amount_cents = pdf_amount
    cn_amount = extract_chinese_uppercase_total(text)
    if cn_amount is not None and cn_amount != metadata.amount_cents:
        metadata.amount_cents = cn_amount
        metadata.extraction_sources.append("pdf-chinese-uppercase-total")
    if metadata.invoice_number or metadata.amount_cents is not None:
        metadata.confidence = "high"
        return metadata
    ocr_metadata = extract_pdf_via_ocr(data)
    return ocr_metadata.merge(metadata)


def join_spaced_digits(text: str) -> str:
    """Collapse per-character spacing in numbers.

    Some invoice PDFs lay out every glyph separately, so the text layer reads
    ``¥ 9 5 0 . 0 0`` and ``2 6 4 4 2 ...`` instead of ``¥950.00`` / ``26442...``.
    Left as-is, the amount and invoice-number patterns match only the first
    digit and silently report a wrong amount. Only rewrite when the document
    actually shows that spacing (4+ single digits in a row), so ordinary tables
    that merely separate two numbers with a space are left untouched.
    """
    if not re.search(r'\d(?:[ \t][\d.]){3,}', text):
        return text
    collapsed = re.sub(r'(?<=\d)[ \t]+(?=[\d.])', '', text)
    return re.sub(r'(?<=\.)[ \t]+(?=\d)', '', collapsed)


CN_DIGITS = {'零': 0, '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5, '陆': 6, '柒': 7, '捌': 8, '玖': 9}
CN_UNITS = {'拾': 10, '佰': 100, '仟': 1000}
CN_TOTAL_PATTERN = re.compile(r'[零壹贰叁肆伍陆柒捌玖拾佰仟万]{2,}[圆元](?:整|[零壹贰叁肆伍陆柒捌玖]角(?:[零壹贰叁肆伍陆柒捌玖]分)?)')


def extract_chinese_uppercase_total(text: str) -> int | None:
    """Read 价税合计（大写）, e.g. 玖佰伍拾圆整 -> 95000 cents.

    The uppercase total is written in Chinese characters, so it survives the
    digit-spacing and OCR problems that corrupt the numeric ``¥`` fields. Used
    as the authority when it disagrees with the digits.
    """
    match = CN_TOTAL_PATTERN.search(re.sub(r'[ \t]+', '', text))
    if not match:
        return None
    body = match.group(0)
    yuan_part, _, fraction_part = body.replace('圆', '元').partition('元')
    total = section = current = 0
    for ch in yuan_part:
        if ch in CN_DIGITS:
            current = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            section += (current or 1) * CN_UNITS[ch]
            current = 0
        elif ch == '万':
            section = (section + current) * 10000
            total += section
            section = current = 0
    cents = (total + section + current) * 100
    jiao = re.search(r'([零壹贰叁肆伍陆柒捌玖])角', fraction_part)
    fen = re.search(r'([零壹贰叁肆伍陆柒捌玖])分', fraction_part)
    if jiao:
        cents += CN_DIGITS[jiao.group(1)] * 10
    if fen:
        cents += CN_DIGITS[fen.group(1)]
    return cents or None


def extract_pdf_invoice_total(text: str) -> int | None:
    normalized = text.replace('\r', '')
    marker = '价税合计'
    idx = normalized.find(marker)
    window = normalized[idx: idx + 300] if idx != -1 else normalized
    amounts = re.findall(r'[¥￥]\s*([0-9]+(?:\.[0-9]{1,2})?)', window)
    if amounts:
        return amount_to_cents(amounts[-1])
    return None


def extract_from_ofd(data: bytes) -> InvoiceMetadata:
    try:
        import zipfile
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            text_chunks: list[str] = []
            for name in zf.namelist():
                lower = name.lower()
                if not lower.endswith('.xml'):
                    continue
                try:
                    raw = zf.read(name)
                except Exception:
                    continue
                xml_meta = extract_from_xml(raw)
                text_chunks.extend([v for v in [xml_meta.invoice_number, xml_meta.invoice_code, xml_meta.invoice_date, xml_meta.vendor] if v])
                if xml_meta.amount_cents is not None:
                    text_chunks.append(f"金额 {xml_meta.amount_cents / 100:.2f}")
                try:
                    root = ET.fromstring(raw)
                    text_chunks.append(" ".join((element.text or "") for element in root.iter()))
                except Exception:
                    pass
    except Exception:
        return InvoiceMetadata(extraction_sources=["ofd-read-failed"])
    text = " ".join(chunk for chunk in text_chunks if chunk)
    metadata = extract_from_text(text, source="ofd-xml")
    if metadata.invoice_number or metadata.amount_cents is not None:
        metadata.confidence = "high"
    return metadata


def extract_pdf_via_ocr(data: bytes) -> InvoiceMetadata:
    tesseract = shutil.which("tesseract")
    ocrmypdf = shutil.which("ocrmypdf")
    if not tesseract or not ocrmypdf:
        return InvoiceMetadata(extraction_sources=["pdf-ocr-unavailable"])
    try:
        from pypdf import PdfReader
    except Exception:
        return InvoiceMetadata(extraction_sources=["pdf-missing-pypdf"])
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.pdf"
        output_path = Path(tmpdir) / "ocr.pdf"
        input_path.write_bytes(data)
        try:
            subprocess.run(
                [ocrmypdf, "--force-ocr", "-l", "chi_sim+eng", str(input_path), str(output_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            reader = PdfReader(str(output_path))
            text = " ".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return InvoiceMetadata(extraction_sources=["pdf-ocr-failed"])
    metadata = extract_from_text(text, source="pdf-ocr")
    if metadata.invoice_number or metadata.amount_cents is not None:
        metadata.confidence = "medium"
    return metadata


def extract_from_image(data: bytes, extension: str) -> InvoiceMetadata:
    tesseract = shutil.which("tesseract")
    if not tesseract:
        return InvoiceMetadata(extraction_sources=["ocr-unavailable"])
    with tempfile.TemporaryDirectory() as tmpdir:
        image_path = Path(tmpdir) / f"invoice.{extension}"
        image_path.write_bytes(data)
        try:
            result = subprocess.run(
                [tesseract, str(image_path), "stdout", "-l", "eng+chi_sim"],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            return InvoiceMetadata(extraction_sources=["ocr-failed"])
    metadata = extract_from_text(result.stdout, source="ocr")
    if metadata.invoice_number or metadata.amount_cents is not None:
        metadata.confidence = "medium"
    return metadata


def amount_to_cents(raw: str | None) -> int | None:
    if not raw:
        return None
    normalized = raw.replace(",", "").strip()
    try:
        return int(round(float(normalized) * 100))
    except ValueError:
        return None


def infer_business_key(metadata: InvoiceMetadata, content_sha256: str) -> str:
    if metadata.invoice_number and metadata.amount_cents is not None:
        return f"invoice:{metadata.invoice_number}:{metadata.amount_cents}"
    return f"sha256:{content_sha256}"


def metadata_json(metadata: InvoiceMetadata) -> dict[str, object]:
    return asdict(metadata)


def _first_match(patterns: Iterable[re.Pattern[str]], text: str) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def _looks_like_tax_id(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    return bool(re.fullmatch(r"[0-9A-Z]{15,20}", compact))


def _looks_like_vendor_name(text: str) -> bool:
    value = (text or '').strip()
    if not value or value in {'名称：', '名称'}:
        return False
    return any(token in value for token in ['公司', '事务所', '酒店', '餐饮'])
