# Agent guide — ISSS

Document processing pipeline for the Open ISSS site.

## Layout

- `main.py` — pipeline entry point that wires the seven stages together.
- `web_scraper.py`, `document_downloader.py`, `metadata_archiver.py`,
  `file_converter.py`, `ocr_processor.py`, `figure_extractor.py`,
  `language_analyzer.py` — one module per pipeline stage; each is runnable
  standalone as a demo.
- `tests/` — offline pytest suite for the stages and the `main.py` wiring.
- `run.sh` — the gate entry point; its arms (`lint`, `test`, `test-cov`,
  `docs`, `gnn`) are the commands CI runs.
- `scripts/` — `gnn_conformance.py` (the pinned GNN check),
  `check_docs.py` (relative Markdown links) and `gate_report.py` (measures the
  arms and renders `docs/_generated/gate-status.md`).
- `docs/` — architecture, configuration and implementation-status references,
  plus the generated gate status under `docs/_generated/`.
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
- Documentation lives in [`docs/`](docs/README.md) (index, architecture,
  configuration, implementation status) and [`tests/README.md`](tests/README.md).
- Measured against the organization's `python-library` tier by the organization
  checker (`ActiveInferenceInstitute/.github`, `scripts/check_readiness.py`); the
  current gaps and their deferral reasons are recorded in
  [`TO-DO.md`](TO-DO.md#readiness-standard-gaps-measured-2026-11-11).
  Do not adopt a lockfile toolchain or change dependency pins as part of a
  documentation change.

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
