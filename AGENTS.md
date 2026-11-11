# Agent guide — ISSS

Document processing pipeline for the Open ISSS site.

## Layout

- `main.py` — pipeline entry point that wires the seven stages together.
- `web_scraper.py`, `document_downloader.py`, `metadata_archiver.py`,
  `file_converter.py`, `ocr_processor.py`, `figure_extractor.py`,
  `language_analyzer.py` — one module per pipeline stage; each is runnable
  standalone as a demo.
- `tests/` — offline pytest suite for the stages and the `main.py` wiring.
- `docs/` — architecture, configuration and implementation-status references.
- `pyproject.toml` — package metadata, dependencies and the pytest/ruff
  configuration.

## Working notes

- Repository: `ActiveInferenceInstitute/ISSS` (default branch `main`).
- InstituteOS classification: category `research-software`, maturity `wip`, status `active`.
- License: `MIT`.
- Keep private content in private repositories; never commit credentials,
  personal data, or unverified claims.
- Read [`README.md`](README.md) first, then the nearest nested `AGENTS.md`.
- Prefer small, verified changes; run the declared tasks before handing work back.

## Tasks

| Task | Command | Working directory |
| --- | --- | --- |
| `inventory` | `git ls-files` | `.` |
| `test` | `pytest` | `.` |
| `lint` | `ruff check .` | `.` |

## InstituteOS sidecar

This repository carries a committed [`.aii/`](.aii/README.md) sidecar with curated
InstituteOS metadata (`aii-sidecar/v1`): category, maturity, ecosystem relations,
key artifacts, provenance, and portable tasks. It is read by
[InstituteOS](https://github.com/ActiveInferenceInstitute/InstituteOS) tooling and
does not affect the project's build or runtime. Regenerating the sidecar docs
rewrites only `.aii/README.md`, `.aii/AGENTS.md`, `.aii/docs/README.md`,
`.aii/docs/AGENTS.md`, and `.aii/docs/INTEGRATION.md`.
