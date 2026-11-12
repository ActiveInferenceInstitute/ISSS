# ISSS Documentation

This directory holds the documentation for the ISSS document processing
pipeline. See the top-level [README](../README.md) for a quick introduction,
[TO-DO.md](../TO-DO.md) for the current findings and roadmap, and
[REVIEW_LOG_2026-08-02.md](../REVIEW_LOG_2026-08-02.md) for the audit trail
of the documentation deep-review pass. The flat list of every long-lived
document is [documentation-index.md](documentation-index.md).

## Contents

| Document | Purpose |
| --- | --- |
| [architecture.md](architecture.md) | High-level pipeline overview: stages, data flow, modules, and directory conventions. |
| [configuration.md](configuration.md) | Configuration reference: every setting, path, and default used by the pipeline. |
| [implementation-status.md](implementation-status.md) | Every pipeline stage, its artifacts and its output contract. |
| [documentation-index.md](documentation-index.md) | Flat index of every long-lived document in the repository. |
| [_generated/gate-status.md](_generated/gate-status.md) | Generated: the gate arms with their measured wall times, the CI jobs, the GNN pin and the pinned actions. |
| [README.md](../README.md) | Project landing page: quickstart, components, dependencies, license. |
| [tests/README.md](../tests/README.md) | Offline test suite: scope, how to run it, and the offline rule. |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | How to contribute to this repository. |
| [SECURITY.md](../SECURITY.md) | How to report a security issue. |

## The gate

`./run.sh` is the only gate entry point. Each arm is the command CI calls, so a
local run is the same gate as a hosted one:

| Arm | Command | What it runs |
| --- | --- | --- |
| `lint` | `./run.sh lint` | `ruff check .` under the contract in `pyproject.toml`. |
| `test` | `./run.sh test` | The whole suite without coverage instrumentation (default arm). |
| `test-cov` | `./run.sh test-cov` | The same suite with the `--cov-fail-under=90` gate. |
| `docs` | `./run.sh docs` | Relative Markdown links plus the generated-page freshness check. |
| `gnn` | `./run.sh gnn` | The pinned GNN conformance check; it installs the pinned parser, so it needs network. |
| `ci` | `./run.sh ci` | Every arm above, in that order. |
| `timings` | `./run.sh timings` | Re-measures the arms and regenerates [`_generated/`](_generated/README.md). |

There is no `types` arm: the repository configures no type checker. The suite
also declares no pytest markers, so `test` is the whole suite minus coverage
rather than a selection.

Measured wall times, the collected test count and the coverage figure are
recorded in [_generated/gate-status.md](_generated/gate-status.md), which
`scripts/gate_report.py` renders from
[_generated/arm-timings.json](_generated/arm-timings.json). Do not copy those
numbers into prose; `./run.sh docs` fails when the page and its data diverge.

`.github/workflows/ci.yml` has four jobs — `lint` (`3.12`), `test` (matrix
`3.12`/`3.13`/`3.14`, with the coverage gate on `3.12` only), `docs` (`3.12`)
and `gnn-conformance`, which displays as `gnn conformance (pinned)`.

## GNN pin

The canonical pin is `.github/gnn-pin.json`, schema `gnn-importer-pin/v1`. It
pins `ActiveInferenceInstitute/Generalized_Notation_Notation` at `v5.0.3`,
revision `8f293d9ba810e6eda5c09842d9c7ed9ffa5f92c1`, recorded 2026-11-12.
[.github/GNN.md](../.github/GNN.md) is the pointer that records what the
conformance job parses, and `scripts/gnn_conformance.py` is the check itself.

## Quick links

- [Getting started](../README.md#getting-started)
- [Pipeline architecture](architecture.md)
- [Configuration reference](configuration.md)
- [Implementation status](implementation-status.md)
- [Gate status](_generated/gate-status.md)
- [Documentation index](documentation-index.md)
