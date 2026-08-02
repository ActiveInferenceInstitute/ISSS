# Configuration Reference

All pipeline settings are plain Python constants in the CONFIG block at the
top of `main.py`; no configuration file is required. Edit the constants and
run `python main.py`.

## Pipeline settings (`main.py`)

| Setting | Default | Purpose |
| --- | --- | --- |
| `BASE_URL` | `https://web3.isss.org` | Site to crawl for documents. |
| `DOWNLOAD_PATH` | `downloaded_documents` | Where downloaded files are saved. |
| `ARCHIVE_PATH` | `archived_documents` | Where `metadata.json` is written. |
| `CONVERTED_PATH` | `converted_documents` | Reserved for the file-conversion stage. |
| `OCR_OUTPUT_PATH` | `ocr_texts` | Reserved for the OCR stage. |
| `FIGURE_OUTPUT_PATH` | `extracted_figures` | Reserved for figure extraction. |
| `LANGUAGE_ANALYSIS_OUTPUT_PATH` | `language_analysis` | Reserved for language analysis. |

## Module parameters

### `WebScraper` (`web_scraper.py`)

- Constructor: `WebScraper(base_url='https://web3.isss.org')`.
- `crawl(url, depth=0, max_depth=11)` — recursive crawl depth limit
  (default 11).
- `is_valid_url(url)` — a URL is valid when it has a scheme and netloc and
  the netloc ends with `isss.org`.
- Recognized document extensions: `.pdf`, `.docx`, `.pptx`, `.xlsx`
  (`filter_documents`).
- Page requests use a 30-second timeout.

### `DocumentDownloader` (`document_downloader.py`)

- Constructor: `DocumentDownloader(base_url, save_path)` — creates
  `save_path` if needed.
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

### `OCRProcessor` (`ocr_processor.py`)

- Constructor: `OCRProcessor(input_path, output_path)`.
- `process_documents()` — processes every `.jpg` file in `input_path` and
  writes `<base_name>.txt` into `output_path`.
- Requires the system Tesseract binary in addition to the Python packages
  (see `requirements.txt`).
