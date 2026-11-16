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

`./run.sh` remains the gate entry point. Governed offline acceptance on the explicitly selected lane exercised 302 tests with the unchanged 90% floor; exact receipts remain private operational evidence, not a hosted or real-OCR verdict. Current generated arm timings/counts must come from their canonical producer rather than copied prose.

## The suite is offline

No test performs a live network request or needs the system Tesseract binary:

- `tests/conftest.py` serves fixture pages from an in-process HTTP server on
  `127.0.0.1` and registers an autouse guard that fails any test opening a
  socket to another host.
- Producer/consumer regressions exercise actual receipts, generation activation/retirement, metadata rollback/deduplication, and pipeline status. External HTTP/OCR/parser boundaries are controlled; these are not live-site or installed-GNN origin proofs.
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
- `test_pipeline_artifacts.py` covers hash/path custody and active generations; `test_gnn_conformance.py` covers exact verdict/report admission; `test_gate_report.py` covers full/offline refresh and historical provenance. Reference-link tests retain code/fence and physical-line diagnostics.

Fixtures are generated in `tmp_path`; the suite never touches the real
`downloaded_documents/`, `archived_documents/`, `converted_documents/`,
`ocr_texts/`, `extracted_figures/` or `language_analysis/` directories.
