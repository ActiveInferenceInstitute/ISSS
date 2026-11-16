"""Tests for ``file_converter.FileConverter``.

Documents are generated in ``tmp_path`` with the same libraries the stage uses,
so no binary fixtures are committed, and ``pytesseract.image_to_string`` is
stubbed: the suite stays offline and needs no system Tesseract binary.
"""

import io
from pathlib import Path

import openpyxl
import pymupdf
import pytest
from docx import Document as DocxDocument
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

import file_converter
import pipeline_artifacts
from file_converter import PDF_DPI, FileConverter
from language_analyzer import LanguageAnalyzer
from pipeline_artifacts import ArtifactStore

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


def _text(root, source_name):
    store = ArtifactStore(root, 'conversion')
    record = next(row for row in store.active_documents() if row['document_name'] == source_name)
    return store.resolve(record, record['text_file']).read_text()


# ---------------------------------------------------------------------------
# Output layout
# ---------------------------------------------------------------------------




def test_convert_files_writes_text_and_page_images(tmp_path):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    pdf_path = downloads / "proceedings.pdf"
    _write_text_pdf(pdf_path, texts=("first page text", "second page text"))
    (downloads / "readme.md").write_text("not a document")

    converted = tmp_path / "converted_documents"
    records = FileConverter(str(downloads), str(converted)).convert_files()

    assert [row['document_name'] for row in records] == ['proceedings.pdf']
    assert records[0]['page_count'] == 2
    assert records[0]['characters'] == len("first page text\fsecond page text")
    text = _text(converted, 'proceedings.pdf')
    assert text.split("\f") == ["first page text", "second page text"]

    assert [Path(page).name for page in records[0]['page_files']] == [
        'page-0001.png', 'page-0002.png'
    ]
    assert all((converted / page).is_file() for page in records[0]['page_files'])


def test_page_images_are_png_at_the_configured_dpi(tmp_path):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    pdf_path = downloads / "programme.pdf"
    _write_text_pdf(pdf_path)

    converted = tmp_path / "converted_documents"
    records = FileConverter(str(downloads), str(converted)).convert_files()

    width_points, height_points = _page_size_points(pdf_path)
    with Image.open(converted / records[0]['page_files'][0]) as image:
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

    assert _text(converted, 'scan.pdf') == "text read by tesseract"
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

    assert "first page text" in _text(converted, 'proceedings.pdf')


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

    word_text = _text(converted, 'minutes.docx')
    assert word_text.splitlines() == ["Word paragraph", "left | right"]

    assert _text(converted, 'slides.pptx') == "Slide paragraph"

    spreadsheet_text = _text(converted, 'index.xlsx')
    assert spreadsheet_text.splitlines() == ["[Proceedings]", "year | title", "2008 | ISSS Proceedings"]


def test_office_documents_produce_no_page_images(tmp_path):
    downloads = tmp_path / "downloaded_documents"
    downloads.mkdir()
    _write_docx(downloads / "minutes.docx")

    converted = tmp_path / "converted_documents"
    records = FileConverter(str(downloads), str(converted)).convert_files()

    assert records[0]['page_files'] == []


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
    store = ArtifactStore(converted, 'conversion')
    assert 'broken.pdf' in store.failures
    assert [row['document_name'] for row in store.active_documents()] == ['proceedings.pdf']


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
    records = FileConverter(str(downloads), str(converted)).convert_files()
    assert sorted(Path(row['text_file']).name for row in records) == [
        'programme-pdf.txt', 'programme.txt'
    ]
    assert "first page text" in _text(converted, 'programme.pdf')
    assert "Word paragraph" in _text(converted, 'programme.docx')


def test_fallback_name_collision_cannot_overwrite_another_document(tmp_path):
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    _write_text_pdf(downloads / 'a-pdf.pdf', ('distinct first PDF',))
    _write_docx(downloads / 'a.docx')
    _write_text_pdf(downloads / 'a.pdf', ('distinct second PDF',))
    converted = tmp_path / 'converted'
    converter = FileConverter(downloads, converted)
    records = converter.convert_files()
    names = [Path(row['text_file']).name for row in records]
    assert len(set(names)) == 3
    assert _text(converted, 'a-pdf.pdf') == 'distinct first PDF'
    assert _text(converted, 'a.pdf') == 'distinct second PDF'
    assert 'Word paragraph' in _text(converted, 'a.docx')
    rerun = converter.convert_files()
    assert {row['document_name']: Path(row['text_file']).name for row in rerun} == {
        row['document_name']: Path(row['text_file']).name for row in records
    }


def test_shrinking_pdf_retires_active_pages_but_preserves_previous_generation(tmp_path):
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    source = downloads / 'paper.pdf'
    _write_text_pdf(source, ('old first page', 'old second page'))
    converted = tmp_path / 'converted'
    converter = FileConverter(downloads, converted)
    previous = converter.convert_files()[0]
    previous_bytes = {path: (converted / path).read_bytes() for path in previous['page_files']}
    sentinel = converted / 'text' / 'unowned.txt'
    sentinel.parent.mkdir()
    sentinel.write_text('unowned evidence')
    _write_text_pdf(source, ('new single page',))
    current = converter.convert_files()[0]
    assert len(current['page_files']) == 1
    assert _text(converted, 'paper.pdf') == 'new single page'
    assert all((converted / path).read_bytes() == content for path, content in previous_bytes.items())
    assert sentinel.read_text() == 'unowned evidence'
    report = LanguageAnalyzer(converted, tmp_path / 'analysis').analyze_language()
    assert report['document_count'] == 1
    assert report['totals']['words'] == 3


def test_later_ocr_failure_deactivates_document_without_exposing_partial_pages(
    tmp_path, monkeypatch
):
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    source = downloads / 'paper.pdf'
    _write_text_pdf(source, ('previous complete text',))
    converted = tmp_path / 'converted'
    converter = FileConverter(downloads, converted)
    previous = converter.convert_files()[0]
    previous_text = converted / previous['text_file']
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), 'new first page')
    document.new_page()
    document.save(source)
    document.close()

    def fail_ocr(image):
        raise RuntimeError('later OCR failed')

    monkeypatch.setattr(file_converter.FileConverter, '_ocr_page', staticmethod(fail_ocr))
    assert converter.convert_files() == []
    store = ArtifactStore(converted, 'conversion')
    assert store.active_documents() == []
    assert 'later OCR failed' in store.failures['paper.pdf']
    assert previous_text.read_text() == 'previous complete text'
    assert not list((converted / '.generations').glob('.staging-*'))
    report = LanguageAnalyzer(converted, tmp_path / 'analysis').analyze_language()
    assert report['documents'] == []


def test_failed_manifest_publication_keeps_old_manifest_and_rejects_stale_source(
    tmp_path, monkeypatch
):
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    source = downloads / 'paper.pdf'
    _write_text_pdf(source, ('first generation',))
    converted = tmp_path / 'converted'
    converter = FileConverter(downloads, converted)
    previous = converter.convert_files()[0]
    manifest = (converted / 'active.json').read_bytes()
    _write_text_pdf(source, ('replacement generation',))
    original_replace = pipeline_artifacts.os.replace

    def refuse_manifest(staged, destination):
        if Path(destination).name == 'active.json':
            raise OSError('manifest publication failed')
        return original_replace(staged, destination)

    monkeypatch.setattr(pipeline_artifacts.os, 'replace', refuse_manifest)
    with pytest.raises(OSError, match='publication failed'):
        converter.convert_document(source)
    assert (converted / 'active.json').read_bytes() == manifest
    assert (converted / previous['text_file']).read_text() == 'first generation'
    assert ArtifactStore(converted, 'conversion').active_documents() == []


def test_conversion_rejects_replaced_acquisition_without_reidentifying_it(
    tmp_path, receipt_factory
):
    source = tmp_path / 'downloaded_documents' / 'paper.docx'
    receipt = receipt_factory('paper.docx', b'not read before identity admission')
    source.write_bytes(b'replacement bytes')
    converted = tmp_path / 'converted'
    converter = FileConverter(source.parent, converted)
    assert converter.convert_files(
        [source],
        expected_identities={
            receipt.document_name: {'sha256': receipt.sha256, 'size': receipt.size}
        },
    ) == []
    assert 'acquisition content changed' in converter.store.failures['paper.docx']
    assert ArtifactStore(converted, 'conversion').active_documents() == []
