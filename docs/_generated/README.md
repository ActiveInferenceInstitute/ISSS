# Generated documentation

The measurement JSON and generated page are script-owned, not hand-edited.
This README documents their contract; new numbers require actual execution.

| File | Producer | Refreshed by |
| --- | --- | --- |
| [arm-timings.json](arm-timings.json) | `scripts/gate_report.py --capture` | `./run.sh timings` |
| [gate-status.md](gate-status.md) | `scripts/gate_report.py` from `arm-timings.json` | `./run.sh timings`, verified by `./run.sh docs` |

`./run.sh docs` refuses a page that no longer matches its measurement record or
the live repository facts it cites (the arms `run.sh` dispatches, the collected
test count, the GNN pin and the workflow jobs).

`scripts/gate_report.py --capture --offline` (or `./run.sh timings --offline`) measures only offline arms. Current GNN is explicitly unmeasured; its original date/host/duration and complete prior snapshot remain historical without invented pin bindings. Repeated refresh must not re-date that observation. New values require real source-bound execution after source/docs settle; do not hand-edit generated JSON/page values.

For source-immutable governed qualification, use `scripts/gate_report.py --capture --offline --output-dir PATH` with a task-owned external directory. Seed that directory's `arm-timings.json` with the retained prior record when carrying history. Child documentation checks receive that exact selection through `run.sh docs --output-dir PATH`; there is no ambient environment selector. The CLI restores its module paths after returning, so nested regression captures cannot overwrite the outer producer's evidence. `--check --output-dir PATH` is read-only. Apply only exact canonical producer bytes under a separate repository lease.
