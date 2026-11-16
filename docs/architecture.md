# Pipeline Architecture

The ISSS repository implements a document processing pipeline that discovers
documents on the Open ISSS site (`https://web3.isss.org`) and the society site
(`https://www.isss.org`), downloads them, archives their metadata, converts
them into text and page images, extracts figures with caption candidates, and
compiles descriptive statistics over the text. All seven stages are
implemented (see [implementation-status.md](implementation-status.md) for the
details).

Discovery starts from the configured seeds rather than from a single URL: the
`web3.isss.org` front end is a WordPress incubation site that links no
documents, while the society site links the corpus, including legacy paths on
`web3.isss.org` (see the source-availability note in
[implementation-status.md](implementation-status.md)).

## Stages

| # | Stage | Module / class | Status |
| --- | --- | --- | --- |
| 1 | Web scraping — discover document URLs | `web_scraper.py` / `WebScraper` | Implemented |
| 2 | Document download | `document_downloader.py` / `DocumentDownloader` | Implemented |
| 3 | Metadata archiving | `metadata_archiver.py` / `MetadataArchiver` | Implemented |
| 4 | File conversion | `file_converter.py` / `FileConverter` | Implemented |
| 5 | OCR | `ocr_processor.py` / `OCRProcessor` | Implemented (standalone; the converter OCRs empty text layers) |
| 6 | Figure extraction | `figure_extractor.py` / `FigureExtractor` | Implemented |
| 7 | Language analysis | `language_analyzer.py` / `LanguageAnalyzer` | Implemented |

## Data flow

1. **Discovery:** seeds share the existing round-robin budget. HTTP(S) hostnames and every redirect are admitted before requests; results distinguish successful, successful-empty, partial, and failed discovery. Budget truncation is explicit.
2. **Download:** each completed file has a `DownloadReceipt` binding source/final URLs, bytes, and original acquisition time. Same-volume staging and no-clobber publication prevent partial files from masquerading as completed downloads. Cache hits require matching receipt/content, not mere file existence.
3. **Metadata:** a complete receipt batch is validated before one metadata-array publication. Cached receipts do not append duplicate events or gain new acquisition times.
4. **Conversion:** the pipeline carries each acquisition receipt's expected hash and size into conversion and checks them before extraction as well as before publication. Immutable `.generations/<id>/` sets contain text, page images, and `record.json` source/output hashes. `active.json` atomically selects qualified successful sets. Failed, retired, stale, or corrupt generations are not current inputs; historical/unowned files are not deleted.
5. **OCR:** standalone `.jpg` processing remains separate. Conversion uses actual Tesseract for image-only PDF pages; controlled tests do not qualify recognition accuracy.
6. **Figures:** extraction consumes active conversion sets and publishes its own immutable generations selected by `active.json`, retaining boxes, caption candidates, source/output hashes, and historical records. Legacy `figures.json` is preserved history, not the current discovery source.
7. **Language:** `LanguageAnalyzer` takes the converted root and reloads its active selection for each analysis, reading only qualified current text. Lowercased ASCII/apostrophe tokens, counters, weighted averages, and the most frequent words retain their fixed descriptive definitions.

## Orchestration and standalone entry points

- `python main.py` runs all seven stages, with stage 5 (OCR) also available
  standalone. Configuration lives in the CONFIG block at the top of `main.py`;
  see [configuration.md](configuration.md).
- Each implemented module can also be run standalone with its own demo:
  `python web_scraper.py`, `python document_downloader.py`,
  `python metadata_archiver.py`, `python file_converter.py`,
  `python figure_extractor.py`, `python ocr_processor.py`,
  `python language_analyzer.py`. The scraper and downloader demos use a small
  seed list and a page budget, so a demo run stays bounded.

## Directory conventions

The pipeline writes to the following directories, relative to where it is
run. All of them are gitignored.

| Directory | Default | Created by |
| --- | --- | --- |
| `downloaded_documents/` | Download directory | `DocumentDownloader` |
| `archived_documents/` | Archive directory (holds `metadata.json`) | `MetadataArchiver` |
| `converted_documents/` | Immutable conversion generations and `active.json` | `FileConverter` |
| `ocr_texts/` | OCR text output (standalone demo; reserved in `main.py`) | `OCRProcessor` |
| `extracted_figures/` | Immutable figure generations and `active.json` | `FigureExtractor` |
| `language_analysis/` | Statistics output (`language_analysis.json`, `SUMMARY.md`) | `LanguageAnalyzer` |
