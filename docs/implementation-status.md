# Implementation Status

Current implementation status of each pipeline stage, verified against the
repository contents (2026-08-02).

## Implemented

| Stage | Module | Notes |
| --- | --- | --- |
| 1. Web scraping | `web_scraper.py` | `WebScraper` crawls the site and collects document URLs. Runnable standalone: `python web_scraper.py`. |
| 2. Document download | `document_downloader.py` | `DocumentDownloader` downloads the discovered URLs concurrently. Runnable standalone: `python document_downloader.py`. |
| 3. Metadata archiving | `metadata_archiver.py` | `MetadataArchiver` appends records to `metadata.json`. Runnable standalone: `python metadata_archiver.py`. |
| 5. OCR | `ocr_processor.py` | `OCRProcessor` extracts text from `.jpg` images. Runnable standalone: `python ocr_processor.py`. Reached by the full pipeline only after stage 4 (file conversion) exists, because OCR consumes the converted output. |

## Placeholders

The following modules exist in the repository but contain only a status
docstring; the pipeline stage they belong to is not yet implemented:

| Stage | Module | Intended behavior |
| --- | --- | --- |
| 4. File conversion | `file_converter.py` | Transform downloaded documents into a uniform format ready for analysis. |
| 6. Figure extraction | `figure_extractor.py` | Isolate figures and their captions from documents for separate analysis. |
| 7. Language analysis | `language_analyzer.py` | Examine document text and compile descriptive statistics. |

## Completing a placeholder stage

Each placeholder module is expected to expose a class with the constructor
and method signatures used by the pipeline entry point (`main.py`), taken
from the original pipeline wiring:

| Module | Class | Constructor | Method |
| --- | --- | --- | --- |
| `file_converter.py` | `FileConverter` | `FileConverter(download_path, converted_path)` | `convert_files()` |
| `figure_extractor.py` | `FigureExtractor` | `FigureExtractor(converted_path, figure_output_path)` | `extract_figures()` |
| `language_analyzer.py` | `LanguageAnalyzer` | `LanguageAnalyzer(ocr_output_path, language_analysis_output_path)` | `analyze_language()` |

To complete a stage: implement the class in the module, wire the stage back
into `main()` in `main.py`, and update this page and the
[README](../README.md#pipeline-components) component table.
