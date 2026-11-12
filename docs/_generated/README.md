# Generated documentation

Every file here is produced by a script and must not be edited by hand. A
change to a number or a table on these pages is a change to the script that
produces it.

| File | Producer | Refreshed by |
| --- | --- | --- |
| [arm-timings.json](arm-timings.json) | `scripts/gate_report.py --capture` | `./run.sh timings` |
| [gate-status.md](gate-status.md) | `scripts/gate_report.py` from `arm-timings.json` | `./run.sh timings`, verified by `./run.sh docs` |

`./run.sh docs` refuses a page that no longer matches its measurement record or
the live repository facts it cites (the arms `run.sh` dispatches, the collected
test count, the GNN pin and the workflow jobs).
