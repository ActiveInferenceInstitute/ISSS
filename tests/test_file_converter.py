"""Tests for ``file_converter.FileConverter``.

Documents are generated in ``tmp_path`` with the same libraries the stage uses,
so no binary fixtures are committed, and ``pytesseract.image_to_string`` is
stubbed: the suite stays offline and needs no system Tesseract binary.
"""

import io

import openpyxl
import pymupdf
import pytest
from docx import Document as DocxDocument
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

import file_converter
from file_converter import PDF_DPI, FileConverter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_text_pdf(path, texts=("first page text",)):
    """Writes a PDF with one text-bearing page per entry in ``texts``."""
    document = pymupdf.open()
    for text in texts:
        page = document.new_page()
        page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def _write_image_only_pdf(path):
    """Writes a one-page PDF whose page holds an image and no text layer."""
    buffer = io.BytesIO()
    Image.new("RGB", (120, 60), (240, 240, 240)).save(buffer, format="PNG")
    document = pymupdf.open()
    page = document.new_page()
    page.insert_image(pymupdf.Rect(0, 0, 120, 60), stream=buffer.getvalue())
    document.save(path)
    document.close()


def _write_docx(path):
    document = DocxDocument()
    document.add_paragraph("Word paragraph")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "left"
    table.cell(0, 1).text = "right"
    document.save(path)


def _write_pptx(path):
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), (200, 200, 200)).save(buffer, format="PNG")
    buffer.seek(0)
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    # A picture shape has no text frame and must be skipped by the extractor.
    slide.shapes.add_picture(buffer, Inches(1), Inches(2), Inches(1), Inches(1))
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    box.text_frame.text = "Slide paragraph"
    presentation.save(path)


def _write_xlsx(path):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Proceedings"
    sheet.append(["year", "title"])
    sheet.append([2008, "ISSS Proceedings"])
    workbook.save(path)


def _page_size_points(path, page_number=0):
    with pymupdf.open(path) as document:
        rect = document[page_number].rect
    return rect.width, rect.height


# ---------------------------------------------------------------------------
# Output layout
# ---------------------------------------------------------------------------


def test_constructor_creates_text_and_pages_directories(tmp_path):
    converted = tmp_path / "converted_documents"

    FileConverter(str(tmp_path / "downloaded_documents"), str(converted))

    assert (converted / "text").is_dir()
    assert (converted / "pages").is_dir()


def test_convert_files_writes_text_and_page_images(tmp_path):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    pdf_path = downloads / "proceedings.pdf"
    _write_text_pdf(pdf_path, texts=("first page text", "second page text"))
    (downloads / "readme.md").write_text("not a document")

    converted = tmp_path / "converted_documents"
    records = FileConverter(str(downloads), str(converted)).convert_files()

    assert records == [
        {"document_name": "proceedings.pdf", "page_count": 2, "characters": len("first page text\fsecond page text")}
    ]
    text = (converted / "text" / "proceedings.txt").read_text()
    assert text.split("\f") == ["first page text", "second page text"]

    pages = sorted((converted / "pages" / "proceedings").iterdir())
    assert [page.name for page in pages] == ["page-0001.png", "page-0002.png"]


def test_page_images_are_png_at_the_configured_dpi(tmp_path):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    pdf_path = downloads / "programme.pdf"
    _write_text_pdf(pdf_path)

    converted = tmp_path / "converted_documents"
    FileConverter(str(downloads), str(converted)).convert_files()

    width_points, height_points = _page_size_points(pdf_path)
    with Image.open(converted / "pages" / "programme" / "page-0001.png") as image:
        assert image.format == "PNG"
        expected = (width_points * PDF_DPI / 72, height_points * PDF_DPI / 72)
        assert abs(image.size[0] - expected[0]) <= 1
        assert abs(image.size[1] - expected[1]) <= 1


def test_image_only_page_falls_back_to_ocr(tmp_path, monkeypatch):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    _write_image_only_pdf(downloads / "scan.pdf")
    seen_sizes = []

    def stub_image_to_string(image):
        seen_sizes.append(image.size)
        return "text read by tesseract"

    monkeypatch.setattr(file_converter.pytesseract, "image_to_string", stub_image_to_string)

    converted = tmp_path / "converted_documents"
    records = FileConverter(str(downloads), str(converted)).convert_files()

    assert (converted / "text" / "scan.txt").read_text() == "text read by tesseract"
    assert records[0]["characters"] == len("text read by tesseract")
    assert seen_sizes and seen_sizes[0][0] > 0 and seen_sizes[0][1] > 0


def test_text_layer_pages_are_not_ocrd(tmp_path, monkeypatch):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    _write_text_pdf(downloads / "proceedings.pdf")

    monkeypatch.setattr(
        file_converter.pytesseract,
        "image_to_string",
        lambda image: pytest.fail("a page with a text layer must not be OCR'd"),
    )

    converted = tmp_path / "converted_documents"
    FileConverter(str(downloads), str(converted)).convert_files()

    assert "first page text" in (converted / "text" / "proceedings.txt").read_text()


# ---------------------------------------------------------------------------
# Office documents
# ---------------------------------------------------------------------------


def test_office_documents_are_extracted_to_text(tmp_path):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    _write_docx(downloads / "minutes.docx")
    _write_pptx(downloads / "slides.pptx")
    _write_xlsx(downloads / "index.xlsx")

    converted = tmp_path / "converted_documents"
    records = FileConverter(str(downloads), str(converted)).convert_files()

    assert [record["document_name"] for record in records] == [
        "index.xlsx",
        "minutes.docx",
        "slides.pptx",
    ]
    assert [record["page_count"] for record in records] == [0, 0, 0]

    word_text = (converted / "text" / "minutes.txt").read_text()
    assert word_text.splitlines() == ["Word paragraph", "left | right"]

    assert (converted / "text" / "slides.txt").read_text() == "Slide paragraph"

    spreadsheet_text = (converted / "text" / "index.txt").read_text()
    assert spreadsheet_text.splitlines() == ["[Proceedings]", "year | title", "2008 | ISSS Proceedings"]


def test_office_documents_produce_no_page_images(tmp_path):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    _write_docx(downloads / "minutes.docx")

    converted = tmp_path / "converted_documents"
    FileConverter(str(downloads), str(converted)).convert_files()

    assert list((converted / "pages").iterdir()) == []


# ---------------------------------------------------------------------------
# Failures and name collisions
# ---------------------------------------------------------------------------


def test_unreadable_document_is_reported_and_the_run_continues(tmp_path, capsys):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    (downloads / "broken.pdf").write_bytes(b"not a pdf")
    _write_text_pdf(downloads / "proceedings.pdf")

    converted = tmp_path / "converted_documents"
    records = FileConverter(str(downloads), str(converted)).convert_files()

    assert [record["document_name"] for record in records] == ["proceedings.pdf"]
    assert "Skipped broken.pdf" in capsys.readouterr().out
    assert sorted(path.name for path in (converted / "text").iterdir()) == ["proceedings.txt"]


def test_convert_document_returns_none_for_an_unsupported_type(tmp_path):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    document_path = downloads / "notes.txt"
    document_path.write_text("plain text")

    converter = FileConverter(str(downloads), str(tmp_path / "converted_documents"))

    assert converter.convert_document(str(document_path)) is None


def test_same_base_name_with_two_extensions_does_not_overwrite(tmp_path):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    _write_text_pdf(downloads / "programme.pdf")
    _write_docx(downloads / "programme.docx")

    converted = tmp_path / "converted_documents"
    FileConverter(str(downloads), str(converted)).convert_files()

    # Documents are converted in sorted order, so programme.docx keeps
    # programme.txt and programme.pdf is written as programme-pdf.txt.
    text_names = sorted(path.name for path in (converted / "text").iterdir())
    assert text_names == ["programme-pdf.txt", "programme.txt"]
    assert "first page text" in (converted / "text" / "programme-pdf.txt").read_text()
    assert "Word paragraph" in (converted / "text" / "programme.txt").read_text()
