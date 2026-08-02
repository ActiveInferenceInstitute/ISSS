# TO-DO — ISSS

Repository-wide findings and improvement scope from the documentation
deep-review pass (2026-08-02). Items are grouped by severity:

- **Minor** — typos, broken references, formatting, small docstring fixes.
- **Medium** — stale-section rewrites, doc restructures, missing guides added.
- **Major** — large documentation system changes, cross-cutting refactors.

Status markers: `[x]` completed (with commit reference), `[ ]` open/deferred.

Last reviewed: 2026-08-02 (documentation deep-review pass).

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

## Major

- [x] Establish a documentation system for the repository (docs hub +
      implementation status + configuration + contribution + security
      guidance) — completed in this pass: ✓ `b86545b`, `70f20e1`,
      `7b03000`, `7d28458`, `a972d88`, `b722eb6`

## Open / deferred

- [ ] Implement the three placeholder pipeline stages (`file_converter.py`,
      `figure_extractor.py`, `language_analyzer.py`) — deferred: this is new
      functionality beyond a documentation pass; the intended class
      signatures are documented in `docs/implementation-status.md`
- [ ] Add automated tests and CI — deferred: no test infrastructure exists;
      introducing it is a new toolchain beyond a documentation pass (see
      `REVIEW_LOG_2026-08-02.md`)
- [ ] Add `pyproject.toml` packaging metadata — deferred: packaging
      infrastructure beyond documentation scope
