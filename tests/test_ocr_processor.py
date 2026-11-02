"""Tests for ``ocr_processor.OCRProcessor``.

``pytesseract.image_to_string`` is stubbed, so the suite needs no system
Tesseract binary and never calls out to it.
"""

from PIL import Image

import ocr_processor
from ocr_processor import OCRProcessor


def _write_jpeg(path, color=(255, 255, 255), size=(12, 12)):
    Image.new("RGB", size, color).save(path, format="JPEG")


def test_constructor_creates_the_output_directory(tmp_path):
    output = tmp_path / "ocr_texts"

    OCRProcessor(str(tmp_path / "converted_documents"), str(output))

    assert output.is_dir()


def test_process_documents_writes_one_text_file_per_jpeg(tmp_path, monkeypatch):
    converted = tmp_path / "converted_documents"
    converted.mkdir()
    _write_jpeg(converted / "page-0001.jpg")
    _write_jpeg(converted / "page-0002.jpg")
    (converted / "notes.txt").write_text("not an image")
    (converted / "page-0003.png").write_text("not a jpeg")
    monkeypatch.setattr(ocr_processor.pytesseract, "image_to_string", lambda image: "stub text")

    output = tmp_path / "ocr_texts"
    OCRProcessor(str(converted), str(output)).process_documents()

    assert sorted(path.name for path in output.iterdir()) == ["page-0001.txt", "page-0002.txt"]
    assert (output / "page-0001.txt").read_text() == "stub text"


def test_extract_text_from_image_reads_the_image_and_saves_its_text(tmp_path, monkeypatch):
    converted = tmp_path / "converted_documents"
    converted.mkdir()
    _write_jpeg(converted / "page-0001.jpg", size=(24, 16))
    seen_sizes = []

    def stub_image_to_string(image):
        seen_sizes.append(image.size)
        return "extracted"

    monkeypatch.setattr(ocr_processor.pytesseract, "image_to_string", stub_image_to_string)

    output = tmp_path / "ocr_texts"
    OCRProcessor(str(converted), str(output)).extract_text_from_image("page-0001.jpg")

    assert seen_sizes == [(24, 16)]
    assert (output / "page-0001.txt").read_text() == "extracted"
