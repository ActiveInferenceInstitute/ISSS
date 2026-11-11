# InstituteOS integration — ISSS

## Identity

| Field | Value |
| --- | --- |
| Repository | `ActiveInferenceInstitute/ISSS` |
| Affiliation | `institute` |
| Category | `research-software` |
| Status | `active` |
| Maturity | `wip` |
| Steward | Active Inference Institute |
| Default branch | `main` |
| Current release | — |
| License | `MIT` |
| Citation | Active Inference Institute — ISSS. |

## Federation

| Setting | Value |
| --- | --- |
| Dashboard mode | `repos` |
| Analytics | `true` |
| Dashboard | `true` |
| Sync policy | `pull` |
| Registries | — |
| Tags | isss, document-processing, pipeline, python |

## Ecosystem relations

| Repository | Relation | Note |
| --- | --- | --- |
| `ActiveInferenceInstitute/InstituteOS` | `referenced-by` | Federated via the InstituteOS .aii manifest. |
| `ActiveInferenceInstitute/Active_Inference_Ontology` | `references` | Uses Active Inference Ontology terms. |

## Key artifacts

| Path | Kind | Description |
| --- | --- | --- |
| `README.md` | `doc` | Repository overview. |
| `LICENSE` | `doc` | License. |
| `docs/` | `doc` | Documentation hub (index, architecture, configuration, implementation status). |
| `CONTRIBUTING.md` | `doc` | Contribution guide. |
| `SECURITY.md` | `doc` | Security reporting guidance. |
| `TO-DO.md` | `doc` | Review findings and improvement roadmap. |
| `REVIEW_LOG_2026-08-02.md` | `doc` | Documentation deep-review pass log. |
| `pyproject.toml` | `code` | Package metadata, dependencies and tool configuration. |
| `main.py` | `code` | Pipeline entry point that wires the seven stages together. |
| `tests/` | `code` | Offline test suite for all seven pipeline stages and the main wiring. |
| `.github/workflows/ci.yml` | `code` | CI workflow (lint, tests, coverage gate) on Python 3.12-3.14. |
| `AGENTS.md` | `doc` | Agent guidance. |

## Portable tasks

| Task | Command | Working directory | Description |
| --- | --- | --- | --- |
| `test` | `pytest` | `.` | Run the offline test suite. |
| `lint` | `ruff check .` | `.` | Lint the pipeline sources and tests. |
| `inventory` | `git ls-files` | `.` | List tracked files. |

## Validation

```bash
python -m aii_platform.aii_sidecar.validate <repo> --completeness
python -m aii_platform.aii_sidecar docs <repo> --overwrite
python -m aii_platform.aii_sidecar.run <repo> --list
```

The sidecar is valid when `validate` prints `OK` and reports no missing artifact,
manifest, link, or declared-doc path. Completeness is a curation target, not a
runtime requirement.

## Data boundary

This sidecar carries metadata only. It does not grant execution permission, does not
replace the repository's own documentation, and must not be used to move private
content into a public repository. Task execution is limited to trusted checkouts.
