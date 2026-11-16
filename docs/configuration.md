# Configuration Reference

All pipeline settings are plain Python constants in the CONFIG block at the
top of `main.py`; no configuration file is required. Edit the constants and
run `python main.py`.

## Pipeline settings (`main.py`)

| Setting | Default | Purpose |
| --- | --- | --- |
| `BASE_URL` | `https://web3.isss.org` | Base URL of the Open ISSS site. |
| `SEED_URLS` | `BASE_URL`, `https://www.isss.org/`, `https://www.isss.org/annual-meetings/` | Pages the discovery crawl starts from. The `web3.isss.org` front end alone links no documents; the society site links the corpus, including legacy paths on `web3.isss.org`. |
| `MAX_PAGES` | `250` | Total pages fetched in one discovery run, across every seed, so a run stays finite. |
| `DOWNLOAD_PATH` | `downloaded_documents` | Where downloaded files are saved. |
| `ARCHIVE_PATH` | `archived_documents` | Where `metadata.json` is written. |
| `CONVERTED_PATH` | `converted_documents` | Conversion generations and their `active.json` selection. |
| `OCR_OUTPUT_PATH` | `ocr_texts` | Used by the standalone OCR demo, not by `main()`. |
| `FIGURE_OUTPUT_PATH` | `extracted_figures` | Figure generations and their `active.json` selection. |
| `LANGUAGE_ANALYSIS_OUTPUT_PATH` | `language_analysis` | Where the statistics report and summary are written. |

## Module parameters

### `WebScraper` (`web_scraper.py`)

- Constructor:
  `WebScraper(base_url='https://web3.isss.org', seed_urls=None, max_pages=None)`.
  `seed_urls` defaults to `[base_url]`; `max_pages` defaults to `None`
  (unbounded) and is the total page budget for the run, across every seed.
- `start_crawling(max_depth=11)` — crawls every seed, giving each seed's queue
  one page per turn (round-robin) so the first seed cannot spend the whole
  budget before the others are reached.
- `crawl(url, depth=0, max_depth=11)` — the single-URL entry point: it spends
  the remaining budget on one seed's queue, breadth-first.
- `normalise_url(url)` — drops the fragment, lowercases the scheme and host,
  removes a default port and the session and tracking parameters, and returns
  `''` for a URL that cannot be fetched. Links that normalise alike are one URL.
- `is_document_url(url)` / `is_crawl_utility(url)` — the extension test for
  documents and the site-machinery test (login, admin, feed, search, reply and
  REST endpoints) that keeps them out of the crawl queue.
- URL admission requires HTTP(S), an exact `isss.org` hostname or its subdomain, valid port syntax, and no userinfo/backslash ambiguity. `notisss.org` and `isss.org.evil.invalid` are not allowed. The same boundary is enforced on seeds, links, and redirects before the next request.
- Recognized document extensions remain `.pdf`, `.docx`, `.pptx`, `.xlsx`, after normalization.
- Discovery returns explicit successful, successful-empty, partial, or failed outcomes. Invalid/failed seeds and budget truncation remain visible even when another seed finds documents; incomplete standalone/pipeline outcomes exit nonzero.
- The full rules are in
  [implementation-status.md](implementation-status.md#discovery-contract-stage-1).

### `DocumentDownloader` (`document_downloader.py`)

- Constructor: `DocumentDownloader(base_url, save_path, seed_urls=None,
  max_pages=None)` — creates `save_path` if needed and forwards the
  discovery settings to its internal `WebScraper`.
- `save_document(session, url)` returns a qualified `DownloadReceipt`, not a filename inferred from existence. Receipt/content agreement is required for cache use and downstream metadata/conversion.
- Filename handling retains content-type extension rules while URL/content identities distinguish competing sources with the same basename. Partial downloads and failed receipt publication cannot become completed cache entries.
- Redirects are admitted before following them. The downloader retains successful peers and reports incomplete batch/discovery status rather than manufacturing an empty success.

### `MetadataArchiver` (`metadata_archiver.py`)

- Constructor: `MetadataArchiver(archive_path)` — creates the directory and
  initializes an empty `metadata.json` if absent.
- Metadata admission consumes qualified download receipts in a complete batch. Source/final URLs, actual file identity, and original acquisition timestamp are retained.
- The whole batch is validated before one atomic array publication; failure leaves earlier metadata intact. Cached receipts do not append duplicate acquisition records.

### `FileConverter` (`file_converter.py`)

- Constructor: `FileConverter(download_path, converted_path)`.
- `convert_files(document_paths=None)` activates only successful selected inputs for that invocation; `convert_document(document_path)` publishes one complete replacement or deactivates its failed replacement.
- Text/page artifacts and source/output hashes live in immutable `.generations/<id>/` sets with `record.json`; `active.json` selects current qualified sets.
- Consumers never infer current inputs by scanning legacy flat files. Failed, shrinking, retired, stale, or corrupt sets remain excluded without deleting historical/unowned files.
- Existing page DPI, separators, and scientific extraction rules remain; see the [conversion contract](implementation-status.md#conversion-contract-stage-4).
- Requires `PyMuPDF`, `python-docx`, `python-pptx` and `openpyxl`; image-only
  PDF pages additionally need the system Tesseract binary.

### `FigureExtractor` (`figure_extractor.py`)

- Constructor: `FigureExtractor(converted_path, figure_output_path)` consumes active qualified conversion generations.
- `extract_figures()` atomically selects successful figure generations in `active.json`; `extract_document(document_name)` replaces a selected source document, with source extensions retained in document identity.
- Crops, page boxes, caption candidates, and hashes are retained in immutable generation records. Legacy `figures.json` is not rewritten or scanned as current evidence.
- Module constants: `INK_THRESHOLD`, `MERGE_DISTANCE`, `MIN_FIGURE_SIDE`,
  `MIN_FIGURE_AREA_RATIO`, `MAX_FIGURE_AREA_RATIO`, `TEXT_COVERAGE_LIMIT` and
  `CAPTION_MAX_GAP`. The heuristic and its limits are in
  [implementation-status.md](implementation-status.md#figure-contract-stage-6).
- Needs the system Tesseract binary for the caption candidates.

### `LanguageAnalyzer` (`language_analyzer.py`)

- Constructor: `LanguageAnalyzer(converted_path, output_path)` takes the conversion root, not a flat `text/` directory.
- `analyze_language()` consumes only qualified active text and writes `language_analysis.json` plus `SUMMARY.md`. Vocabulary counters and running weighted totals retain descriptive definitions without corpus-sized token/sentence lists.
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
