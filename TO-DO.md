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
2026-11-02; re-checked against `main` at `066b561` 2026-11-12 (PRs #17-#19
recorded, readiness re-measured, GNN pin and `pymdp` confirmed).

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
- [ ] GNN pin is one release behind the estate cutover: `.github/gnn-pin.json`
      records `v5.0.3` at `8f293d9ba810e6eda5c09842d9c7ed9ffa5f92c1`, while the
      importer repositories moved to `v5.1.0` at
      `75c834bd8519dc7b5adc4d24f16bf393cfd1ecdf` (tag list of
      `ActiveInferenceInstitute/Generalized_Notation_Notation`, checked
      2026-11-12). Bumping it is a pin change, not a documentation one: the
      digest in `docs/workflows/publishing.md` (enforced by `./run.sh docs`),
      the tag comment in `.github/workflows/ci.yml` and
      `docs/_generated/gate-status.md` (via `./run.sh timings`) all have to
      move with it. Blocked on the repository owner deciding whether ISSS, which
      carries no `.gnn.md` model, follows the cutover.
      The `inferactively-pymdp` 1.0.5 pin does not apply here: the tree
      contains no reference to `pymdp` and the pipeline has no inference
      dependency.

## Completed after the documentation pass

- [x] Add automated tests and CI: `tests/` covers the four implemented stages
      and the `main.py` wiring offline (local fixture server, stubbed HTTP and
      OCR), with a 90% coverage floor; `.github/workflows/ci.yml` runs lint and
      tests on Python 3.12-3.14, plus the pinned GNN conformance baseline
      (see `.github/GNN.md`; ISSS carries no `.gnn.md` model file, so the job
      validates the pinned upstream exemplar) — ✓ `7caaa45`
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
- [x] Fix stage 1 on the live run: URLs are normalised (fragments, session and
      tracking parameters), login, admin, feed, search and reply URLs are never
      queued, document links are recorded instead of fetched, and seeds take
      turns so one cannot spend the whole budget; `MAX_PAGES` stays the total
      across every seed. Before: 6 of 6 pages on one fixture site with 0
      documents; after: 4 pages, both seeds reached, 1 document — ✓ `ef9a686`

## Readiness standard gaps (measured 2026-11-11)

Measured with the organization checker in the
`ActiveInferenceInstitute/.github` repository
(`scripts/check_readiness.py --repo ActiveInferenceInstitute/ISSS --path .`):
the repository's declared `python-library` tier reports 19 pass, **16 fail**, 0
waived, 3 unavailable (the `CORE-INHERIT-*` `github-api` criteria, offline) and
49 not-applicable. The 2026-11-11 reading was 20 pass / 15 fail; the extra
failure is `PY-PYTEST-CI` (below), introduced by #16. None of these is a
documentation defect and none is fixed in a documentation pass; they are
recorded here as the verified remainder.

Blocking failures:

- [ ] No tracked lock file (`CORE-LOCK`, `PY-UVLOCK`): the repository installs
      with `pip install -e '.[dev]'` and ships no `uv.lock` (or other known
      lockfile), so `CORE-DEPENDABOT-ECOSYSTEM` also fails with "no tracked lock
      file matches a known ecosystem". Adopting uv and committing `uv.lock` is a
      packaging change, deliberately not made here.
- [ ] `PY-FROZEN` / `PY-UVLOCK-CHECK`: CI does not run `uv sync --frozen` or
      `uv lock --check`.
- [ ] `PY-MYPY-CONFIG`: `pyproject.toml` declares no `[tool.mypy]` section, so
      `PY-MYPY-CI` also fails.
- [ ] `PY-RUFF-CI`: the criterion requires both `ruff check` and
      `ruff format --check` in `.github/workflows/ci.yml`; the workflow names
      neither, and `./run.sh lint` runs `ruff check .` only. Adding a format
      check is a lint-contract change (it would have to reformat the tree); the
      owner decides it.
- [ ] `PY-RUFF-EXTEND`: `pyproject.toml` states its lint contract with
      `select = [...]` (line 74) rather than the standard's expected
      `extend-select`; the file's comment says this is intentional so the gate
      does not shift with a new ruff release. Changing it is an owner decision.
- [ ] `PY-COVERAGE-RUN`: the criterion requires a literal `--cov` in the
      workflow; coverage comes from `addopts` at `pyproject.toml:47`, which
      the workflow never restates.
- [ ] `PY-PYTEST-CI`: the criterion requires a literal `pytest` in the
      workflow; the steps call `./run.sh test`. This failure is new in the
      2026-11-12 measurement and was introduced by #16, not by a lost test.

Non-blocking failures: `PY-COMPLEXITY`, `PY-DEPTRY`, `PY-DURATIONS`,
`PY-PRECOMMIT` (no `.pre-commit-config.yaml`), `PY-VULTURE`.

`PY-RUFF-CI`, `PY-PYTEST-CI` and `PY-COVERAGE-RUN` all match literal commands
inside `.github/workflows/ci.yml`. Since #16 the workflow runs no command of its
own — every step is `./run.sh <arm>` — so those criteria now fail structurally,
not because the repository stopped running ruff, pytest or coverage. The owner
picks: teach the checker about gate delegation (a change in
`ActiveInferenceInstitute/.github`, so outside this repository), restate the
commands in the workflow (which undoes #16), or waive the three criteria in
`.aii/readiness.json` with the reason above.

Fixing these means adopting the standard's uv-based toolchain, which the
documentation pass is not allowed to do (no dependency-pin, lockfile or action
changes). The owner should decide whether ISSS adopts that toolchain or records
non-expiring waivers with reasons in `.aii/readiness.json`.

## Gate and CI consolidation (2026-11-12)

Hosted GitHub Actions runs are unavailable in this estate (billing lock), so a
local run of the arms is the only evidence a change is green. The gate is
therefore one script that CI also calls.

- [x] Single entry point `./run.sh` with separately runnable arms `lint`,
      `test`, `test-cov`, `docs`, `gnn`, plus `ci` (all arms in order) and
      `timings` (re-measure and regenerate the generated page). `pytest` and
      `ruff check .` remain the underlying commands, so the `.aii` sidecar's
      portable tasks stay accurate.
- [x] Duplicated CI work removed: one `gate` job on `3.12` installs once and
      runs `lint`, `test-cov` and `docs`; the `test` matrix keeps `3.13` and
      `3.14` and runs only the coverage-free arm, so no leg runs the suite
      twice and lint/docs cost no extra install. Every job step calls an arm;
      no workflow step restates a command.
- [x] The GNN conformance check left the workflow YAML: it is
      `scripts/gnn_conformance.py` with separate `--check-pin` (offline
      schema/revision validation), `--install` and `--verify` modes, and
      `./run.sh gnn` runs acquisition then verification as the old two steps
      did.
- [x] Documentation gate: the repository has no mkdocs, markdown-link-check or
      documentation script, so `scripts/check_docs.py` checks relative targets
      and anchors of every tracked Markdown file, and
      `scripts/gate_report.py --check` refuses a stale generated page.
- [x] Measured arm wall times, the collected test count and the coverage figure
      live in `docs/_generated/gate-status.md`, rendered by
      `scripts/gate_report.py` from `docs/_generated/arm-timings.json`; no
      number is hand-written.
- [ ] No `types` arm: the repository configures no type checker, so an arm
      would have to invent a contract. This is the same gap as `PY-MYPY-CONFIG`
      above and is an owner decision.

## Publishing identity contract and gate follow-ups (2026-11-12)

- [x] Adopt the pinned Publishing identity contract: `docs/workflows/publishing.md`
      records the canonical copies and their digests,
      `docs/workflows/record-identity.schema.json` is the unmodified canonical
      schema, `scripts/gate/identity.py` verifies the schema and every recorded
      digest, and `./run.sh docs` runs it before the Markdown link check. The
      member's existing link, generated-page, test, coverage and GNN checks are
      named there instead of duplicated — ✓ `a8b8d06` (PR #17).
- [x] Align the gate help with the dispatcher and validate image targets:
      `./run.sh help` prints the arms `run.sh` actually accepts,
      `scripts/check_docs.py` resolves image targets as well as links,
      `tests/test_check_docs.py` covers the new cases, and the docs index picked
      up the added entries — ✓ `a7d43da` (PR #18).
- [x] Resolve the paths declared in `.aii/config.yaml` relative to `.aii/`, and
      correct `.aii/README.md` and `.aii/docs/INTEGRATION.md` to match — ✓
      `066b561` (PR #19).

## Documentation pass 3 (2026-11-11)

- [x] Confirmed `docs/` (index, architecture, configuration, implementation
      status), `tests/README.md`, `README.md`, `AGENTS.md` and the `.aii`
      sidecar against the tree; the docs are complete and modular. Registered
      the readiness gaps above and bumped `readiness.json`'s
      `standard_version` to the current catalogue `1.1.0`.
- [ ] `.aii/docs/INTEGRATION.md` and `.aii/README.md` are presented as rendered
      from `.aii/config.yaml` by `aii_platform.aii_sidecar docs --overwrite`.
      The private environment is reachable now, but its `aii-platform` 0.3.2
      exposes only `validate`, `scan`, `run`, `init`, `rollout`, `curate`,
      `doctor` and `schema` — there is no `docs` subcommand — so the two files
      stay hand-maintained. `python -m aii_platform.aii_sidecar validate <tree>`
      passes on `main` at `066b561`; the renderer itself is owned by
      InstituteOS, not by this repository.
