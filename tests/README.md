# Tests

The suite covers the four implemented pipeline stages (`web_scraper.py`,
`document_downloader.py`, `metadata_archiver.py`, `ocr_processor.py`) and the
`main.py` wiring of stages 1-3.

```bash
pip install -e '.[dev]'
pytest
```

`pytest` runs with coverage for the implemented modules and a 90% floor (the
current suite reaches 100%); `ruff check .` is the lint gate. Both run in CI on
Python 3.12, 3.13 and 3.14.

## The suite is offline

No test performs a live network request or needs the system Tesseract binary:

- `tests/conftest.py` serves fixture pages from an in-process HTTP server on
  `127.0.0.1` and registers an autouse guard that fails any test opening a
  socket to another host.
- `tests/test_document_downloader.py` and `tests/test_main.py` replace the
  `aiohttp` session and the downloader with stubs.
- `tests/test_ocr_processor.py` replaces `pytesseract.image_to_string` with a
  stub, so the OCR stage is exercised without Tesseract installed.

Fixtures are generated in `tmp_path`; the suite never touches the real
`downloaded_documents/`, `archived_documents/` or `ocr_texts/` directories.
