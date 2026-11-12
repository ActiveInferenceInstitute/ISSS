# ISSS — Document Processing Pipeline

A Python pipeline that discovers documents on the Open ISSS site
(`https://web3.isss.org`) and the International Society for the Systems
Sciences site (`https://www.isss.org`), downloads them, archives their
metadata, and converts, illustrates and analyses them.

The pipeline is designed as seven stages, all of them implemented. See
[docs/implementation-status.md](docs/implementation-status.md) for the
artifacts and contracts of every stage.

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
| Figure Extractor — extracts figures and caption candidates from page images | `figure_extractor.py` | Implemented |
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
`python figure_extractor.py`, `python ocr_processor.py`,
`python language_analyzer.py`.

## Prerequisites

- Python 3.12 or newer (declared in `pyproject.toml`).
- `requests` and `beautifulsoup4` — web scraping (`web_scraper.py`).
- `aiohttp` — asynchronous downloads (`document_downloader.py`).
- `PyMuPDF` — PDF text extraction and page rendering, and `python-docx`,
  `python-pptx` and `openpyxl` — Word, PowerPoint and Excel text extraction
  (`file_converter.py`).
- `Pillow` and `pytesseract` plus the system Tesseract binary — OCR
  (`ocr_processor.py`), the converter's fallback for PDF pages whose text
  layer is empty, and the caption candidates of the figure extractor.
- The metadata archiver and the language analyzer use only the standard
  library.

## Tests

The suite covers all seven implemented stages and the `main.py` wiring, and it
runs offline: fixture pages come from an in-process server, the HTTP and OCR
calls are stubbed, and the document, page and figure fixtures are generated in
the test directory, so no test needs network access or Tesseract.

```bash
pip install -e '.[dev]'
./run.sh ci        # every gate arm: lint, tests, coverage, docs, GNN conformance
```

`./run.sh` is the gate entry point: `./run.sh lint`, `./run.sh test` (the whole
suite without coverage), `./run.sh test-cov` (the suite with the 90% floor),
`./run.sh docs` and `./run.sh gnn` each run one arm, and CI calls the same
arms. `pytest` and `ruff check .` remain the underlying commands. The measured
wall time of each arm is recorded in
[docs/_generated/gate-status.md](docs/_generated/gate-status.md); the suite
runs on Python 3.12, 3.13 and 3.14. See
[tests/README.md](tests/README.md) for the details.

### Required local PR check

The `main` ruleset requires `gate (local, 3.12)` on the exact
pull request head. Run the gate locally and publish a commit status from
GitVault. GitHub Actions is optional.

Set `PR_NUMBER` to the pull request number. From a standalone clone with
`origin` pointing to this repository, set `PR_CHECKOUT` to an absolute path
for a new worktree and fetch the exact head. In GitVault, use a separate worktree under
`Local/worktrees/` and acquire the repository lease for the fetch and
worktree creation.

```bash
set -euo pipefail
repo=ActiveInferenceInstitute/ISSS
context='gate (local, 3.12)'
live_pr_head() {
  gh pr view "$PR_NUMBER" --repo "$repo" --json state,baseRefName,headRefOid |
    jq -er 'select(.state == "OPEN" and .baseRefName == "main") |
      .headRefOid | select(test("^[0-9a-f]{40}$"))'
}
tested_head=$(live_pr_head)
git fetch --no-tags origin "refs/pull/$PR_NUMBER/head" </dev/null
test "$(git rev-parse FETCH_HEAD </dev/null)" = "$tested_head"
git worktree add --detach "$PR_CHECKOUT" "$tested_head" </dev/null
cd "$PR_CHECKOUT"
test "$(git rev-parse HEAD </dev/null)" = "$tested_head"
test -z "$(git status --porcelain </dev/null)"
```

Prepare a Python 3.12 environment with the editable development install
before starting the offline test launch.

```bash
python3.12 -m venv .venv
export PYTHON="$PWD/.venv/bin/python"
"$PYTHON" -m pip install -e '.[dev]'
```

Run all required arms with that environment from the clean checkout. In
GitVault, run the block as one bounded `execute --classification test`
launch following GitVault's `docs/EXECUTE.md`. Bind this repository and the
exact `tested_head` in the intent. Prepare the environment before admission
and keep the gate output with the successful `exit.json` receipt.

Save these arms in a shell file outside the checkout and set `GATE_SCRIPT`
to its absolute path.

```bash
set -e
export PYTHON="$PWD/.venv/bin/python"
./run.sh lint
./run.sh test-cov
./run.sh docs
```

Set `VAULT` to the GitVault launcher and `GATE_INTENT` to the reviewed
intent file's absolute path, then launch the check.

```bash
"$VAULT" execute --classification test --intent "$GATE_INTENT" \
  --repository "$repo" --cwd "$PR_CHECKOUT" -- /bin/bash "$GATE_SCRIPT"
```

### Publish the local PR result

An authorized maintainer uses the mapped Institute identity and enables
status publication through GitVault’s `state` write class. Set
`GATE_EXIT_RECEIPT` to the launch's `exit.json`. Review the gate output
to confirm that every required arm passed. Continue in the same shell
and verify the receipt and live PR head before planning the status.

```bash
set -euo pipefail
receipt_head=$(jq -er --arg repo "$repo" '
  .payload | select(.classification == "test" and .outcome == "SUCCEEDED"
    and .returncode == 0 and .source_unchanged == true and .binding.source == $repo
    and .descendants.sample_errors == 0 and .descendants.remaining == [])
  | .binding.revision | select(test("^[0-9a-f]{40}$"))
' "$GATE_EXIT_RECEIPT")
test "$receipt_head" = "$tested_head"
test "$(live_pr_head)" = "$tested_head"
digest=$(shasum -a 256 "$GATE_EXIT_RECEIPT")
status_parameters=$(jq -cn --arg repo "$repo" --arg head "$tested_head" \
  --arg context "$context" --arg digest "${digest%% *}" '{
    repository:$repo, expected_commit:$head, context:$context, state:"success",
    description:("Local gate passed. Receipt SHA-256 " + $digest[:16])
  }')
plan=$("$VAULT" plan github-status --parameters "$status_parameters")
plan_id=$(jq -er .github <<< "$plan")
phrase=$(jq -er .confirmation <<< "$plan")
"$VAULT" github-apply --plan "$plan_id"
```

After reviewing the plan's repository, SHA and context, recheck the
PR head and apply its confirmation phrase. If the head moved, rerun
the full gate on the new head and make a fresh plan.

```bash
test "$(live_pr_head)" = "$tested_head"
"$VAULT" github-apply --plan "$plan_id" --apply --confirm "$phrase"
gh api "repos/$repo/commits/$tested_head/status" |
  jq -e --arg head "$tested_head" --arg context "$context" '
    .sha == $head and any(.statuses[]; .context == $context and .state == "success")
  '
test "$(live_pr_head)" = "$tested_head"
gh pr checks "$PR_NUMBER" --repo "$repo" --required --json name,state,bucket |
  jq -e --arg context "$context" '
    any(.[]; .name == $context and .state == "SUCCESS" and .bucket == "pass")
  '
```

## Status and readiness

All seven pipeline stages are implemented and the offline suite passes today.
Two things still need a network or a token:

- **Discovery** depends on the live ISSS sites; `www.isss.org` has refused
  connections intermittently, and the `web3.isss.org` front end links no
  documents, so the corpus is reached through the configured seeds (see
  [docs/implementation-status.md](docs/implementation-status.md)).
- The OCR stage needs the system Tesseract binary. The tests stub it and run
  without it.
- The organization readiness checker's `github-api` criteria need an
  authenticated token; offline it reports them `unavailable` (exit 3) rather
  than a pass.

The repository is measured against the standard's `python-library` tier. As of
2026-11-11 that measurement has real, documented gaps — it does not yet adopt the
uv-based lockfile toolchain the tier expects. The list and the reason each is
deferred are in [TO-DO.md](TO-DO.md#readiness-standard-gaps-measured-2026-11-11).

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

## InstituteOS sidecar

This repository carries a committed [`.aii/`](.aii/README.md) sidecar with curated
InstituteOS metadata (`aii-sidecar/v1`): category, maturity, ecosystem relations,
key artifacts, provenance, and portable tasks. It is read by
[InstituteOS](https://github.com/ActiveInferenceInstitute/InstituteOS) tooling and
does not affect the project's build or runtime.
