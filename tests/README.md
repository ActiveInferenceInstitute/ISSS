# Tests

The suite covers all seven implemented pipeline stages (`web_scraper.py`,
`document_downloader.py`, `metadata_archiver.py`, `file_converter.py`,
`ocr_processor.py`, `figure_extractor.py`, `language_analyzer.py`) and the
`main.py` wiring.

```bash
pip install -e '.[dev]'
./run.sh test      # the whole suite, offline
./run.sh test-cov  # the same suite with the 90% coverage floor
./run.sh lint      # ruff check .
```

`./run.sh` is the repository's single gate entry point and CI calls the same
arms. `pytest` runs with coverage for the implemented modules and a 90% floor;
the suite reaches 100%. Both arms run in CI on Python 3.12, 3.13 and 3.14
(the coverage gate on 3.12). The collected test count and the measured arm
times are in [../docs/_generated/gate-status.md](../docs/_generated/gate-status.md).

## The suite is offline

No test performs a live network request or needs the system Tesseract binary:

- `tests/conftest.py` serves fixture pages from an in-process HTTP server on
  `127.0.0.1` and registers an autouse guard that fails any test opening a
  socket to another host.
- `tests/test_document_downloader.py` and `tests/test_main.py` replace the
  `aiohttp` session and the downloader with stubs.
- `tests/test_ocr_processor.py` replaces `pytesseract.image_to_string` with a
  stub, so the OCR stage is exercised without Tesseract installed; the same
  stub covers the converter's OCR fallback for image-only PDF pages.
- `tests/test_file_converter.py` generates its PDF, Word, PowerPoint and Excel
  fixtures in `tmp_path` with the pipeline's own libraries, so no document
  fixtures are committed.

- `tests/test_figure_extractor.py` generates page images with PIL and replaces
  `pytesseract.image_to_data` with a stub, so figure detection and caption
  association are deterministic without Tesseract.
- `tests/test_language_analyzer.py` writes its text fixtures in `tmp_path`; the
  stage uses only the standard library, so nothing is stubbed.
- `tests/test_check_docs.py` checks local Markdown link and image targets,
  missing-target diagnostics and the offline handling of external URLs.

Fixtures are generated in `tmp_path`; the suite never touches the real
`downloaded_documents/`, `archived_documents/`, `converted_documents/`,
`ocr_texts/`, `extracted_figures/` or `language_analysis/` directories.
