# ISSS — Document Processing Pipeline

A Python pipeline that discovers documents on the Open ISSS website
(`https://web3.isss.org`), downloads them, and archives their metadata for
future analysis.

The pipeline is designed as seven stages. Four stages are implemented; three
are placeholders awaiting implementation. See
[docs/implementation-status.md](docs/implementation-status.md) for the
current status of every stage.

## Pipeline Components

| Stage | Module | Status |
| --- | --- | --- |
| Web Scraper — collects document URLs from targeted pages | `web_scraper.py` | Implemented |
| Document Downloader — asynchronous downloading of discovered documents | `document_downloader.py` | Implemented |
| Metadata Archiver — stores metadata for each downloaded document | `metadata_archiver.py` | Implemented |
| File Converter — transforms documents into a uniform format | `file_converter.py` | Placeholder |
| OCR Processor — extracts text from document images | `ocr_processor.py` | Implemented |
| Figure Extractor — isolates figures and captions for separate analysis | `figure_extractor.py` | Placeholder |
| Language Analyzer — compiles descriptive statistics on document text | `language_analyzer.py` | Placeholder |

## Getting Started

1. **Initial Setup**: Install all necessary dependencies with
   `pip install -r requirements.txt`. The OCR stage additionally requires the
   system Tesseract binary (e.g. `brew install tesseract` on macOS,
   `apt install tesseract-ocr` on Debian/Ubuntu).
2. **Configuration**: Adjust the CONFIG block at the top of `main.py`,
   including `BASE_URL`, `DOWNLOAD_PATH`, and the other output paths. See
   [docs/configuration.md](docs/configuration.md) for the full reference.
3. **Run the Pipeline**: Initiate the implemented stages with
   `python main.py`.

Each implemented module can also be run standalone as a demo:
`python web_scraper.py`, `python document_downloader.py`,
`python metadata_archiver.py`, `python ocr_processor.py`.

## Prerequisites

- Python 3.7 or newer (the code uses f-strings and `asyncio.run`).
- `requests` and `beautifulsoup4` — web scraping (`web_scraper.py`).
- `aiohttp` — asynchronous downloads (`document_downloader.py`).
- `Pillow` and `pytesseract` plus the system Tesseract binary — OCR
  (`ocr_processor.py`).
- The metadata archiver uses only the standard library.

## Documentation

- [Documentation index](docs/README.md)
- [Pipeline architecture](docs/architecture.md)
- [Configuration reference](docs/configuration.md)
- [Implementation status](docs/implementation-status.md)
- [TO-DO and roadmap](TO-DO.md)

## How to Contribute

We encourage contributions that enhance the functionality of the pipeline.
Please follow the conventional fork-and-pull request protocol — see
[CONTRIBUTING.md](CONTRIBUTING.md) for setup and guidelines.

## Security

To report a security issue, follow the guidance in [SECURITY.md](SECURITY.md).

## Licensing

This project is distributed under the MIT License. For more details, refer to
the [LICENSE](LICENSE) file.
