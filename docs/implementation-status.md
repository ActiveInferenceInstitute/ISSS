# Implementation Status

Current implementation status of each pipeline stage, verified against the
repository contents (2026-08-02; source availability re-checked 2026-11-01;
stage 4 implemented 2026-11-02).

## Source availability (checked 2026-11-01)

The pipeline's original single seed — the `web3.isss.org` front end — links no
documents:

- `https://web3.isss.org` returns HTTP 200 and its WordPress sitemaps list
  three URLs (`/`, `/sample-page/`, one hello-world post); its pages contain
  no `.pdf`/`.docx`/`.pptx`/`.xlsx` links. A crawl from that URL alone
  therefore finds nothing, which is what the 2026-08-02 live run recorded.
- The corpus is reachable on the same domain at legacy paths the front end
  does not link, for example
  `https://web3.isss.org/proceedings/2008_ISSS_Proceedings_from_CD.pdf`
  (HTTP 200, 52,882,005 bytes) and a 2006 Sonoma programme PDF under
  `/conferences/sonoma2006/`. Directory listings are not browsable
  (`/proceedings/` returns HTTP 403).
- The society site `https://www.isss.org` links those legacy paths from
  conference pages (`/annual-meetings/`, `/2023-kruger-national-park/`,
  `/2023-kruger-memories2/`, `/2025-washington-dc/`, `/2025-birmingham-uk/`)
  and also hosts documents of its own under `/editor_upload/File/`.

Discovery therefore starts from `SEED_URLS` (see
[configuration.md](configuration.md)). The seeds are link-bearing pages; a
directory path alone yields nothing.

## Implemented

| Stage | Module | Notes |
| --- | --- | --- |
| 1. Web scraping | `web_scraper.py` | `WebScraper` crawls from the configured seeds and collects document URLs. Runnable standalone: `python web_scraper.py`. |
| 2. Document download | `document_downloader.py` | `DocumentDownloader` downloads the discovered URLs concurrently. Runnable standalone: `python document_downloader.py`. |
| 3. Metadata archiving | `metadata_archiver.py` | `MetadataArchiver` appends records to `metadata.json`. Runnable standalone: `python metadata_archiver.py`. |
| 4. File conversion | `file_converter.py` | `FileConverter` writes `text/<name>.txt` and `pages/<name>/page-NNNN.png` per document. Runnable standalone: `python file_converter.py`. See the conversion contract below. |
| 5. OCR | `ocr_processor.py` | `OCRProcessor` extracts text from `.jpg` images. Runnable standalone: `python ocr_processor.py`. Outside `main.py`: the pipeline emits text and PNG pages, and OCR is applied inside stage 4 to PDF pages whose text layer is empty. |

## Conversion contract (stage 4)

Every converted document produces two uniform artifacts under the converted
directory, so later stages read one shape:

| Artifact | Content |
| --- | --- |
| `text/<name>.txt` | The document text: PDF text layer page by page, a form feed (`\f`) between pages, or the extracted paragraphs/slide text/worksheet rows of a `.docx`, `.pptx` or `.xlsx` file. |
| `pages/<name>/page-NNNN.png` | One PNG per PDF page at 150 DPI, numbered from 1 and zero-padded to four digits. |

Decisions this contract fixes:

- A PDF page whose text layer is empty (an image-only scan) is rendered and
  read with Tesseract, so the text artifact is complete for scanned documents;
  the OCR stage's system requirement applies here too.
- The text artifact is written for every page, not only for image-only pages.
- Office documents produce the text artifact only: paginating and rasterizing
  them needs an external office suite, which this stage does not depend on.
- Conversion is deterministic: documents are converted in sorted name order,
  artifacts overwrite earlier runs, and two documents that share a base name
  with different extensions are written as `<base>.txt` and
  `<base>-<extension>.txt` rather than overwriting each other.
- A document that cannot be read is reported and skipped; the remaining
  documents are still converted.

## Placeholders

The following modules exist in the repository but contain only a status
docstring; the pipeline stage they belong to is not yet implemented:

| Stage | Module | Intended behavior |
| --- | --- | --- |
| 6. Figure extraction | `figure_extractor.py` | Isolate figures and their captions from documents for separate analysis. |
| 7. Language analysis | `language_analyzer.py` | Examine document text and compile descriptive statistics. |

## Completing a placeholder stage

Each placeholder module is expected to expose a class with the constructor
and method signatures used by the pipeline entry point (`main.py`), taken
from the original pipeline wiring:

| Module | Class | Constructor | Method |
| --- | --- | --- | --- |
| `file_converter.py` | `FileConverter` | `FileConverter(download_path, converted_path)` | `convert_files()` — completed 2026-11-02 |
| `figure_extractor.py` | `FigureExtractor` | `FigureExtractor(converted_path, figure_output_path)` | `extract_figures()` |
| `language_analyzer.py` | `LanguageAnalyzer` | `LanguageAnalyzer(ocr_output_path, language_analysis_output_path)` | `analyze_language()` |

To complete a stage: implement the class in the module, wire the stage back
into `main()` in `main.py`, add offline tests under `tests/` (see
[tests/README.md](../tests/README.md) for the rules), and update this page and
the [README](../README.md#pipeline-components) component table.
