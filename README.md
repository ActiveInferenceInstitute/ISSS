# ISSS — Document Processing Pipeline

A Python pipeline that discovers documents on the Open ISSS site
(`https://web3.isss.org`) and the International Society for the Systems
Sciences site (`https://www.isss.org`), downloads them, and archives their
metadata for future analysis.

The pipeline is designed as seven stages. Four stages are implemented; three
are placeholders awaiting implementation. See
[docs/implementation-status.md](docs/implementation-status.md) for the
current status of every stage.

## Source availability (checked 2026-11-01)

The `web3.isss.org` front end is a WordPress incubation site: its sitemaps
list three URLs and its pages link no documents, so a crawl from that URL
alone discovers nothing. The corpus remains reachable — the society site
links documents, including legacy paths on `web3.isss.org` such as
`https://web3.isss.org/proceedings/2008_ISSS_Proceedings_from_CD.pdf`
(HTTP 200, 52,882,005 bytes). Discovery therefore starts from the seeds in
`SEED_URLS` rather than from the front end alone. Directory listings under the
legacy paths are not browsable (`/proceedings/` returns HTTP 403), so seeds
must be pages that link documents.

## Pipeline Components

| Stage | Module | Status |
| --- | --- | --- |
| Web Scraper — collects document URLs from targeted pages | `web_scraper.py` | Implemented |
| Document Downloader — asynchronous downloading of discovered documents | `document_downloader.py` | Implemented |
| Metadata Archiver — stores metadata for each downloaded document | `metadata_archiver.py` | Implemented |
| File Converter — converts documents into text files and page images | `file_converter.py` | Implemented |
| OCR Processor — extracts text from document images | `ocr_processor.py` | Implemented |
| Figure Extractor — isolates figures and captions for separate analysis | `figure_extractor.py` | Placeholder |
| Language Analyzer — compiles descriptive statistics on document text | `language_analyzer.py` | Implemented |

## Getting Started

1. **Initial Setup**: Install the package and its dependencies with
   `pip install -e '.[dev]'`; dependencies are declared in `pyproject.toml`
   and the `dev` extra adds the test and lint tooling. The OCR stage
   additionally requires the system Tesseract binary (e.g.
   `brew install tesseract` on macOS, `apt install tesseract-ocr` on
   Debian/Ubuntu).
2. **Configuration**: Adjust the CONFIG block at the top of `main.py`,
   including `BASE_URL`, `SEED_URLS`, `MAX_PAGES`, `DOWNLOAD_PATH`, and the
   other output paths. See [docs/configuration.md](docs/configuration.md) for
   the full reference.
3. **Run the Pipeline**: Initiate the implemented stages with
   `python main.py`.

Each implemented module can also be run standalone as a demo:
`python web_scraper.py`, `python document_downloader.py`,
`python metadata_archiver.py`, `python file_converter.py`,
`python ocr_processor.py`, `python language_analyzer.py`.

## Prerequisites

- Python 3.12 or newer (declared in `pyproject.toml`).
- `requests` and `beautifulsoup4` — web scraping (`web_scraper.py`).
- `aiohttp` — asynchronous downloads (`document_downloader.py`).
- `PyMuPDF` — PDF text extraction and page rendering, and `python-docx`,
  `python-pptx` and `openpyxl` — Word, PowerPoint and Excel text extraction
  (`file_converter.py`).
- `Pillow` and `pytesseract` plus the system Tesseract binary — OCR
  (`ocr_processor.py`), also used by the converter for PDF pages whose text
  layer is empty.
- The metadata archiver and the language analyzer use only the standard
  library.

## Tests

The suite covers the six implemented stages and the `main.py` wiring, and it
runs offline: fixture pages come from an in-process server, the HTTP and OCR
calls are stubbed, and the document fixtures are generated in the test
directory, so no test needs network access or Tesseract.

```bash
pip install -e '.[dev]'
pytest        # coverage floor 90% for the implemented modules
ruff check .
```

CI runs both on Python 3.12, 3.13 and 3.14. See
[tests/README.md](tests/README.md) for the details.

## Documentation

- [Documentation index](docs/README.md)
- [Pipeline architecture](docs/architecture.md)
- [Configuration reference](docs/configuration.md)
- [Implementation status](docs/implementation-status.md)
- [Test suite](tests/README.md)
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
