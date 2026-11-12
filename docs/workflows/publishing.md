# ISSS — Publishing contract adoption

The canonical [Publishing contract](https://github.com/ActiveInferenceInstitute/ActiveInferenceJournal/blob/d8ec888a8f3051a66bed9af047ee4b206050bdce/docs/workflows/publishing.md)
lives in ActiveInferenceJournal. This page records ISSS's adoption, not another
definition of the identity grammar.

## Member facts

- Gate: `./run.sh <arm>`; arms: `lint`, `test`, `test-cov`, `docs`, `gnn`,
  `ci`, `timings`. The commands are recorded in [the sidecar](../../.aii/config.yaml).
- Docs index: [docs/documentation-index.md](../documentation-index.md).
- Manuscript command: none.
- GNN pin: [.github/gnn-pin.json](../../.github/gnn-pin.json).

## Canonical copies and drift gate

[record-identity.schema.json](record-identity.schema.json) and
[identity.py](../../scripts/gate/identity.py) are unmodified copies from the
lead revision linked above. Identity rules remain owned by that schema; ISSS
adds no local grammar or fabricated corpus metadata.

The following digests are the canonical contract's pins:

```text
record-identity.schema.json  84f6c4df6efc3f15f0d8a9a05c8aabd0cbdc08b0f4feac5fcc8ae860a81e306b
identity.py  847328ff163fa90c869495164869caf4e83313748e8a444dbab8d4e459b11074
gnn-pin.json  eb83f7f1b73eb31e116bd05b1f457dd07e6874a2a4ba0e9e95e5bc91f094cd55
```

`./run.sh docs` loads the schema, checks all recorded digests, and invokes the
canonical checker's `--verify-copy` path for each artifact. A missing or changed
copy fails the arm. Updating a pin requires reviewing the canonical source and
copying its bytes and digest together, not blessing a local edit.

The existing link, generated-page, test, coverage and GNN checks remain the
member's gates, following the contract's instruction not to duplicate existing
proof. There is no journal corpus in this pipeline, so this gate does not claim
to validate journal records or to establish document DOI joins. ISSS has no
journal-schema prose mirror to replace.

## Local verification

Run `./run.sh docs`, `./run.sh test` and `./run.sh test-cov`. GitHub Actions is
billing-locked for this migration; local results are the gate. The `gnn`, `ci`
and `timings` arms retain their existing network-dependent behavior and are not
substitutes for these offline checks.
