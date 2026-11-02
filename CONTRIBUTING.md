# Contributing to ISSS

Thanks for your interest in the ISSS document processing pipeline. This
repository follows the conventional fork-and-pull-request protocol: fork the
repository, make your changes on a branch, and open a pull request.

## Development setup

1. Fork the repository on GitHub and clone your fork.
2. Create a virtual environment (Python 3.12 or newer) and install the package
   with its development dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e '.[dev]'
   ```
   Runtime dependencies are declared in `pyproject.toml`; the `dev` extra adds
   `pytest`, `pytest-cov` and `ruff`.
3. For the OCR stage, install the system Tesseract binary
   (e.g. `brew install tesseract` on macOS, `apt install tesseract-ocr` on
   Debian/Ubuntu).
4. Run the pipeline (`python main.py`) or any module standalone
   (`python web_scraper.py`, etc.) to see the current behavior.

## Guidelines

- **Keep documentation accurate.** Docs must match the code: update the
  relevant pages under `docs/`, the README, or the implementation-status
  table whenever behavior, paths, or defaults change.
- **Do not fabricate.** Claims, links, paths, and numbers in documentation
  must be verifiable against the repository contents.
- **Respect the placeholder stages.** `file_converter.py`,
  `figure_extractor.py`, and `language_analyzer.py` are not yet implemented;
  if you implement one, follow the intended class signatures documented in
  [docs/implementation-status.md](docs/implementation-status.md) and wire it
  into `main()`.
- **Testing.** The suite in `tests/` covers the four implemented stages and
  the `main.py` wiring. Run it before opening a pull request:
  ```bash
  pytest          # offline suite with a 90% coverage floor
  ruff check .    # lint gate
  ```
  Tests must stay offline: use the fixtures in `tests/conftest.py` (a local
  HTTP server plus stubs) instead of live requests, and keep fixtures small.
  See [tests/README.md](tests/README.md). If you implement a placeholder
  stage, add tests for it alongside the code.

## Pull request process

1. Create a feature branch: `git checkout -b my-change`.
2. Make your changes with clear, descriptive commit messages.
3. Run the checks above and make sure the repository still works.
4. Push the branch to your fork and open a pull request against `main`.
5. Describe what you changed and why, referencing any related TO-DO.md items.
