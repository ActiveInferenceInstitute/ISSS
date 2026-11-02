# Configuration Reference

All pipeline settings are plain Python constants in the CONFIG block at the
top of `main.py`; no configuration file is required. Edit the constants and
run `python main.py`.

## Pipeline settings (`main.py`)

| Setting | Default | Purpose |
| --- | --- | --- |
| `BASE_URL` | `https://web3.isss.org` | Base URL of the Open ISSS site. |
| `SEED_URLS` | `BASE_URL`, `https://www.isss.org/`, `https://www.isss.org/annual-meetings/` | Pages the discovery crawl starts from. The `web3.isss.org` front end alone links no documents; the society site links the corpus, including legacy paths on `web3.isss.org`. |
| `MAX_PAGES` | `250` | Upper bound on pages fetched in one discovery run, so a run stays finite. |
| `DOWNLOAD_PATH` | `downloaded_documents` | Where downloaded files are saved. |
| `ARCHIVE_PATH` | `archived_documents` | Where `metadata.json` is written. |
| `CONVERTED_PATH` | `converted_documents` | Where the conversion stage writes `text/` and `pages/`. |
| `OCR_OUTPUT_PATH` | `ocr_texts` | Used by the standalone OCR demo, not by `main()`. |
| `FIGURE_OUTPUT_PATH` | `extracted_figures` | Where the extracted figures and `figures.json` are written. |
| `LANGUAGE_ANALYSIS_OUTPUT_PATH` | `language_analysis` | Where the statistics report and summary are written. |

## Module parameters

### `WebScraper` (`web_scraper.py`)

- Constructor:
  `WebScraper(base_url='https://web3.isss.org', seed_urls=None, max_pages=None)`.
  `seed_urls` defaults to `[base_url]`; `max_pages` defaults to `None`
  (unbounded) and stops the crawl once the budget is used up.
- `start_crawling(max_depth=11)` — crawls from every seed in turn, with the
  given depth limit per seed.
- `crawl(url, depth=0, max_depth=11)` — recursive crawl step, also bounded by
  `max_pages`.
- `is_valid_url(url)` — a URL is valid when it has a scheme and netloc and
  the netloc ends with `isss.org`, so both `web3.isss.org` and
  `www.isss.org` links are followed.
- Recognized document extensions: `.pdf`, `.docx`, `.pptx`, `.xlsx`
  (`filter_documents`).
- Page requests use a 30-second timeout; a failing page is reported and the
  crawl continues.

### `DocumentDownloader` (`document_downloader.py`)

- Constructor: `DocumentDownloader(base_url, save_path, seed_urls=None,
  max_pages=None)` — creates `save_path` if needed and forwards the
  discovery settings to its internal `WebScraper`.
- `save_document(session, url)` — downloads in 1 KiB chunks and skips files
  that already exist.
- `download_documents()` — crawls via an internal `WebScraper`, then
  downloads all discovered document URLs concurrently.

### `MetadataArchiver` (`metadata_archiver.py`)

- Constructor: `MetadataArchiver(archive_path)` — creates the directory and
  initializes an empty `metadata.json` if absent.
- `archive_metadata(document_path, url, document_type)` — appends one record
  with this schema:

| Field | Value |
| --- | --- |
| `document_name` | Base name of the document file. |
| `document_path` | Full path of the document. |
| `source_url` | Source URL the document was downloaded from. |
| `document_type` | File extension (e.g. `pdf`, `docx`). |
| `download_date` | Timestamp, format `YYYY-MM-DD HH:MM:SS`. |

### `FileConverter` (`file_converter.py`)

- Constructor: `FileConverter(download_path, converted_path)` — creates
  `converted_path/text/` and `converted_path/pages/` if needed.
- `convert_files()` — converts every `.pdf`, `.docx`, `.pptx` and `.xlsx` file
  in `download_path`, in sorted name order, and returns one record per
  converted document (`document_name`, `page_count`, `characters`).
- `convert_document(document_path)` — converts one document; returns `None`
  and reports the failure when the document cannot be read.
- Module constants: `DOCUMENT_EXTENSIONS`, `PDF_DPI` (150) and
  `PAGE_SEPARATOR` (`\f`). The artifact contract is in
  [implementation-status.md](implementation-status.md#conversion-contract-stage-4).
- Requires `PyMuPDF`, `python-docx`, `python-pptx` and `openpyxl`; image-only
  PDF pages additionally need the system Tesseract binary.

### `FigureExtractor` (`figure_extractor.py`)

- Constructor: `FigureExtractor(converted_path, figure_output_path)` — reads
  `converted_path/pages/` and creates `figure_output_path` if needed.
- `extract_figures()` — extracts the figures of every document in sorted order
  and writes `figures.json`; returns the report.
- `extract_document(document_name)` and
  `extract_page(page_path, document_name, page_number, first_figure_number=1)`
  — work on one document or one page; useful on their own for large runs.
- Module constants: `INK_THRESHOLD`, `MERGE_DISTANCE`, `MIN_FIGURE_SIDE`,
  `MIN_FIGURE_AREA_RATIO`, `MAX_FIGURE_AREA_RATIO`, `TEXT_COVERAGE_LIMIT` and
  `CAPTION_MAX_GAP`. The heuristic and its limits are in
  [implementation-status.md](implementation-status.md#figure-contract-stage-6).
- Needs the system Tesseract binary for the caption candidates.

### `LanguageAnalyzer` (`language_analyzer.py`)

- Constructor: `LanguageAnalyzer(text_path, output_path)` — creates
  `output_path` if needed. `main.py` passes `<CONVERTED_PATH>/text`, the
  directory stage 4 writes.
- `analyze_language()` — analyses every `.txt` file in `text_path` in sorted
  order and writes `language_analysis.json` and `SUMMARY.md` into
  `output_path`; returns the report.
- `analyze_document(document_path)` — analyses one text file and returns its
  record.
- Module constants: `WORD_PATTERN`, `SENTENCE_PATTERN`, `REPORT_NAME`,
  `SUMMARY_NAME`, `TOP_WORDS_PER_DOCUMENT` (50) and `TOP_WORDS_CORPUS` (100).
  The statistics contract is in
  [implementation-status.md](implementation-status.md#statistics-contract-stage-7).
- Uses only the standard library.

### `OCRProcessor` (`ocr_processor.py`)

- Constructor: `OCRProcessor(input_path, output_path)`.
- `process_documents()` — processes every `.jpg` file in `input_path` and
  writes `<base_name>.txt` into `output_path`.
- Requires the system Tesseract binary in addition to the Python packages
  (declared in `pyproject.toml`).
