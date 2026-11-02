# Implementation Status

Current implementation status of each pipeline stage, verified against the
repository contents (2026-08-02; source availability re-checked 2026-11-01;
stages 4, 6 and 7 implemented 2026-11-02).

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
| 6. Figure extraction | `figure_extractor.py` | `FigureExtractor` crops figure-sized regions of each page image to `<document>-fig-NNN.png` and records their caption candidates in `figures.json`. Runnable standalone: `python figure_extractor.py`. See the figure contract below. |
| 7. Language analysis | `language_analyzer.py` | `LanguageAnalyzer` writes `language_analysis.json` and `SUMMARY.md` for the converted text. Runnable standalone: `python language_analyzer.py`. See the statistics contract below. |

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

## Figure contract (stage 6)

`FigureExtractor` reads the page images stage 4 wrote and, per document in
sorted order and per page in page order, writes each figure as
`<document>-fig-NNN.png` (three digits from `fig-001`, numbering continuing
across the pages of one document) into the figure output directory, plus a
`figures.json` metadata file:

| Field | Content |
| --- | --- |
| `figure` | Figure file name. |
| `page`, `page_image` | Page number and the page file the figure came from. |
| `page_size` | Page width and height in pixels, so a box can be rescaled. |
| `bbox` | The figure's source box on the page, in page pixels, right and bottom edges exclusive. |
| `caption_candidate`, `caption_bbox` | The nearest text block's text and box, or `null` when no block is close enough. |

Decisions this contract fixes:

- Detection runs on the rendered page and needs no source-document layout: the
  page is binarized (ink below a grayscale threshold) and connected components
  are built with a run-length sweep, then merged when their boxes are within a
  few pixels.
- A component becomes a figure when both sides of its box reach a minimum size
  and its box covers between 3% and 80% of the page. That excludes text lines
  (too thin) and whole-page scans (too large); page-sized regions are counted
  in the report instead of being cropped.
- The caption candidate is the text block nearest to the figure box, measured
  as the vertical gap of blocks that overlap the figure horizontally, with
  blocks below the figure preferred when two are equally close.
- A figure without a candidate within the gap limit is still written, with
  `caption_candidate: null`, so an ambiguous case stays visible rather than
  being dropped.
- The caption text comes from Tesseract's word boxes for the page, so the
  stage needs the system Tesseract binary and inherits its recognition
  accuracy; a caption split across two detected blocks is reported as the
  block nearest the figure.

## Statistics contract (stage 7)

`LanguageAnalyzer` reads every `.txt` file in its input directory — the
`text/` directory written by stage 4 — and writes two artifacts:

| Artifact | Content |
| --- | --- |
| `language_analysis.json` | One record per document (name, characters, words, unique words, sentences, average word length, average words per sentence, the 50 most frequent words) plus the corpus totals (documents, characters, words, unique words, sentences, both averages, the 100 most frequent words). |
| `SUMMARY.md` | The same figures as two Markdown tables and the corpus word list. |

Decisions this contract fixes:

- The statistics are descriptive and use only the standard library; no
  lemmatization, part-of-speech tagging or stop-word removal is applied.
- A word is a run of letters, digits or apostrophes after lowercasing, so
  `Proceedings`, `proceedings,` and `proceedings.` all count as
  `proceedings`, and `don't` stays one word.
- A sentence ends at `.`, `!` or `?`; empty segments do not count.
- Documents are read in sorted name order and artifacts overwrite earlier
  runs, so the output is deterministic.

## Pipeline classes

| Module | Class | Constructor | Method |
| --- | --- | --- | --- |
| `file_converter.py` | `FileConverter` | `FileConverter(download_path, converted_path)` | `convert_files()` |
| `figure_extractor.py` | `FigureExtractor` | `FigureExtractor(converted_path, figure_output_path)` | `extract_figures()` |
| `language_analyzer.py` | `LanguageAnalyzer` | `LanguageAnalyzer(text_path, output_path)` | `analyze_language()` |

The two constructors that the original wiring documented as
`ocr_output_path`/`converted_path` placeholders were settled when the stages
were implemented: stage 6 reads the page images of the converted tree, and
stage 7 reads its `text/` directory, because OCR stays a standalone stage.

To change a stage: keep its class and method names, keep the artifacts in the
contract above (or update the contract and the dependent stages together), add
offline tests under `tests/` (see [tests/README.md](../tests/README.md) for the
rules), and update this page and the
[README](../README.md#pipeline-components) component table.
