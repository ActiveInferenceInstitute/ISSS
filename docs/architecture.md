# Pipeline Architecture

The ISSS repository implements a document processing pipeline that discovers
documents on the Open ISSS site (`https://web3.isss.org`) and the society site
(`https://www.isss.org`), downloads them, and archives their metadata. The
pipeline is designed as seven stages; four are implemented and three are
placeholders (see [implementation-status.md](implementation-status.md) for the
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
| 4 | File conversion | `file_converter.py` / `FileConverter` | Placeholder |
| 5 | OCR | `ocr_processor.py` / `OCRProcessor` | Implemented (needs stage 4 output) |
| 6 | Figure extraction | `figure_extractor.py` / `FigureExtractor` | Placeholder |
| 7 | Language analysis | `language_analyzer.py` / `LanguageAnalyzer` | Placeholder |

## Data flow

1. **Web scraping** — `WebScraper` crawls from each configured seed
   (`SEED_URLS`), following same-domain links (`*.isss.org`) up to `max_depth`
   (default 11) and at most `MAX_PAGES` pages per run, and collects URLs
   ending in `.pdf`, `.docx`, `.pptx`, or `.xlsx`.
2. **Document download** — `DocumentDownloader` downloads each discovered URL
   into the download directory in 1 KiB chunks, skipping files that already
   exist.
3. **Metadata archiving** — `MetadataArchiver` appends one record per
   downloaded document to `metadata.json` in the archive directory (see
   [configuration.md](configuration.md) for the record schema).
4. **File conversion** *(placeholder)* — intended to transform downloaded
   documents into a uniform format in the converted directory.
5. **OCR** — `OCRProcessor` reads `.jpg` images from an input directory and
   writes the extracted text to one `.txt` file per image. It requires the
   system Tesseract binary. In the full pipeline it operates on the output of
   stage 4, which is not yet implemented.
6. **Figure extraction** *(placeholder)* — intended to isolate figures and
   their captions from documents.
7. **Language analysis** *(placeholder)* — intended to examine document text
   and compile descriptive statistics.

## Orchestration and standalone entry points

- `python main.py` runs stages 1-3 end to end. Configuration lives in the
  CONFIG block at the top of `main.py`; see [configuration.md](configuration.md).
- Each implemented module can also be run standalone with its own demo:
  `python web_scraper.py`, `python document_downloader.py`,
  `python metadata_archiver.py`, `python ocr_processor.py`. The scraper and
  downloader demos use a small seed list and a page budget, so a demo run
  stays bounded.

## Directory conventions

The pipeline writes to the following directories, relative to where it is
run. All of them are gitignored.

| Directory | Default | Created by |
| --- | --- | --- |
| `downloaded_documents/` | Download directory | `DocumentDownloader` |
| `archived_documents/` | Archive directory (holds `metadata.json`) | `MetadataArchiver` |
| `converted_documents/` | Converted output (reserved) | — |
| `ocr_texts/` | OCR text output (reserved in `main.py`; used by the module demo) | `OCRProcessor` |
| `extracted_figures/` | Figure output (reserved) | — |
| `language_analysis/` | Language analysis output (reserved) | — |
