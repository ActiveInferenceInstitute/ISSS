# TO-DO — ISSS

Repository-wide findings and improvement scope from the documentation
deep-review pass (2026-08-02). Items are grouped by severity:

- **Minor** — typos, broken references, formatting, small docstring fixes.
- **Medium** — stale-section rewrites, doc restructures, missing guides added.
- **Major** — large documentation system changes, cross-cutting refactors.

Status markers: `[x]` completed (with commit reference), `[ ]` open/deferred.

Last reviewed: 2026-08-02 (documentation deep-review pass); discovery and
source-availability follow-up 2026-11-01; infrastructure (tests, CI,
packaging) follow-up 2026-11-01; all seven pipeline stages implemented
2026-11-02.

---

## Minor

- [x] Remove stray comment and unused path constants in `main.py`
      (`main.py`) — ✓ `1e510d0`
- [x] Fix configuration assigned *after* the `main()` invocation, plus the
      dangling `download_path` expression (`main.py`) — ✓ `1e510d0`
- [x] Fix the `save_document(url)` call — the method requires a session
      argument (`main.py`, `document_downloader.py`) — ✓ `1e510d0`
- [x] Replace the `http://example.com` placeholder in the
      `document_downloader.py` standalone demo with the pipeline's target site
      (`document_downloader.py`) — ✓ `b920e35`
- [x] Add the missing `Returns` section to the `WebScraper.filter_documents`
      docstring (`web_scraper.py`) — ✓ `c047494`
- [x] Add class/`__init__` docstrings to `OCRProcessor` to match sibling
      modules (`ocr_processor.py`) — ✓ `c047494`
- [x] Align `DocumentDownloader.download_documents` with the scraper's
      document extension set (currently drops `.docx`/`.pptx`/`.xlsx`)
      (`document_downloader.py`) — ✓ `b920e35`
- [x] Add request timeouts so a slow site cannot hang the pipeline
      indefinitely (`web_scraper.py`, `document_downloader.py`) — ✓ `c047494`

## Medium

- [x] Create `requirements.txt` matching the actual runtime dependencies
      (the README references it, but it does not exist)
      (`requirements.txt`) — ✓ `dabab13`
- [x] Rewrite `README.md` to match repository state: 4 of 7 stages
      implemented, correct prerequisites, working quickstart, license clarity
      (`README.md`) — ✓ `70f20e1`
- [x] Make `python main.py` runnable end to end for the implemented stages
      (`main.py`) — ✓ `1e510d0`
- [x] Create a `docs/` documentation hub with an index
      (`docs/README.md`) — ✓ `b86545b`
- [x] Add an architecture overview (`docs/architecture.md`) — ✓ `b86545b`
- [x] Add a configuration reference (`docs/configuration.md`) — ✓ `b86545b`
- [x] Add an implementation-status document
      (`docs/implementation-status.md`) — ✓ `b86545b`
- [x] Add `CONTRIBUTING.md` (setup, fork-and-pull process, docs-accuracy rule)
      (`CONTRIBUTING.md`) — ✓ `7b03000`
- [x] Add `SECURITY.md` (vulnerability reporting path)
      (`SECURITY.md`) — ✓ `7b03000`
- [x] Annotate the three empty placeholder modules with status docstrings
      (`file_converter.py`, `figure_extractor.py`,
      `language_analyzer.py`) — ✓ `7d28458`
- [x] Ignore pipeline output directories in `.gitignore`
      (`downloaded_documents/`, `archived_documents/`, etc.)
      (`.gitignore`) — ✓ `a972d88`
- [x] Register the new documentation artifacts in the `.aii` sidecar manifest
      (`.aii/config.yaml`) — ✓ `b722eb6`
- [x] Start discovery from link-bearing seeds: the `web3.isss.org` front end
      links no documents, so `SEED_URLS` and `MAX_PAGES` now drive the crawl
      (`main.py`, `web_scraper.py`, `document_downloader.py`) — ✓ `4a2f779`
- [x] Record the 2026-11-01 source-availability measurement (front end exposes
      three URLs and no documents; the corpus is reachable at legacy paths
      linked from the society site) (`README.md`,
      `docs/implementation-status.md`, `docs/configuration.md`,
      `docs/architecture.md`) — ✓ `4a2f779`

## Major

- [x] Establish a documentation system for the repository (docs hub +
      implementation status + configuration + contribution + security
      guidance) — completed in this pass: ✓ `b86545b`, `70f20e1`,
      `7b03000`, `7d28458`, `a972d88`, `b722eb6`

## Open / deferred

- [ ] Extend the pipeline beyond the seven implemented stages (for example a
      run report that joins `metadata.json`, `figures.json` and
      `language_analysis.json` into one document record) — deferred: new
      functionality, not a documentation fix.

## Completed after the documentation pass

- [x] Add automated tests and CI: `tests/` covers the four implemented stages
      and the `main.py` wiring offline (local fixture server, stubbed HTTP and
      OCR), with a 90% coverage floor; `.github/workflows/ci.yml` runs lint and
      tests on Python 3.12-3.14 — ✓ `7caaa45`
- [x] Add `pyproject.toml` packaging metadata: dependencies and the dev extra
      live there, the Python floor is 3.12, and `requirements.txt` is removed
      with every reference updated — ✓ `7caaa45`
- [x] Implement stage 4 (`file_converter.py`): documents convert to
      `text/<name>.txt` and `pages/<name>/page-NNNN.png`, with a Tesseract
      fallback for image-only PDF pages, and `main.py` now runs stages 1-4 — ✓ `5635e09`
- [x] Implement stage 7 (`language_analyzer.py`): the converted text compiles
      to `language_analysis.json` and `SUMMARY.md` with per-document and
      corpus statistics, and `main.py` runs it after stage 4 — ✓ `d3a3e6a`
- [x] Implement stage 6 (`figure_extractor.py`): each page image yields
      `<document>-fig-NNN.png` crops with their caption candidates in
      `figures.json`, and `main.py` now runs all seven stages — ✓ `21e350c`
- [x] Run the pipeline on real documents (first live run): stages 2-7 over two
      proceedings articles from `journals.isss.org` (14 and 16 pages), 76 s wall
      clock, exit 0; recorded in `docs/implementation-status.md` and the
      workstream report — ✓ `a29747a`
- [x] Fix stage 6 on that run: a candidate whose box is covered at least 15% by
      the page's Tesseract word boxes is text, not a figure, so the two
      articles that produced 118 paragraph "figures" now produce 5 figures with
      their real captions — ✓ `58dee20`, merged as `0a8c2f9`
- [x] Fix stage 2 on that run: an extension-less document URL is saved with the
      extension its response `Content-Type` implies, so the journal galley that
      stage 4 dropped as `7584` now converts as `7584.pdf` — ✓ `ab5432e`,
      merged as `a29747a`
