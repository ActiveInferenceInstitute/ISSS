# .aii — InstituteOS sidecar

This folder is the committed [InstituteOS](https://github.com/ActiveInferenceInstitute/InstituteOS)
sidecar for **`ActiveInferenceInstitute/ISSS`**. It records curated institutional metadata that the GitHub
API cannot provide — identity, category, maturity, ecosystem relations, key artifacts,
provenance, and portable tasks — so InstituteOS can federate a unified view across
Institute repositories without touching this project's own content. The schema is
`aii-sidecar/v1`.

## Contents

| File | Purpose |
| --- | --- |
| [`config.yaml`](config.yaml) | Machine-readable metadata; the single source of truth. |
| [`readiness.json`](readiness.json) | Declared tier, baseline commit, and waivers for the AII readiness standard. |
| [`docs/`](docs/README.md) | Sidecar documents: the [`README.md`](docs/README.md) · [`AGENTS.md`](docs/AGENTS.md) folder guides, and [`INTEGRATION.md`](docs/INTEGRATION.md) — how this repository is federated, validated, and operated through InstituteOS. |
| [`README.md`](README.md) · [`AGENTS.md`](AGENTS.md) | Human and agent guidance for this folder. |

## Repository profile

| Field | Value |
| --- | --- |
| Repository | `ActiveInferenceInstitute/ISSS` |
| Category | `research-software` |
| Status | `active` |
| Maturity | `wip` |
| License | `MIT` |
| Default branch | `main` |
| Homepage | — |
| Tags | `isss`, `document-processing`, `pipeline`, `python` |

## Capabilities

- documentation
- tested
- python-package
- ci

## Portable tasks

| Task | Command | Working directory | Description |
| --- | --- | --- | --- |
| `lint` | `./run.sh lint` | `.` | Lint the pipeline sources and tests. |
| `test` | `./run.sh test` | `.` | Run the offline test suite without coverage. |
| `test-cov` | `./run.sh test-cov` | `.` | Run the offline test suite with the coverage gate. |
| `docs` | `./run.sh docs` | `.` | Check docs/documentation-index.md and Markdown links, generated docs, and the pinned Publishing identity artifacts. No manuscript command. |
| `gnn` | `./run.sh gnn` | `.` | Run GNN conformance using .github/gnn-pin.json; requires network. |
| `ci` | `./run.sh ci` | `.` | Run lint, test, test-cov, docs and gnn. |
| `timings` | `./run.sh timings` | `.` | Measure gate arms and regenerate docs/_generated/. |

## Links

- **github:** https://github.com/ActiveInferenceInstitute/ISSS
- **website:** https://www.activeinference.org

## Validate

The authoritative validator ships in the private `aii-platform` kernel:

```bash
python -m aii_platform.aii_sidecar.validate <repo> --completeness
python -m aii_platform.aii_sidecar docs <repo> --overwrite
python -m aii_platform.aii_sidecar.run <repo> --list
```

If the private environment is unavailable, review `config.yaml` as plain YAML and
check that every declared path exists in the repository.
