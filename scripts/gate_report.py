#!/usr/bin/env python3
"""Measure the gate arms and render the generated gate-status page.

``docs/_generated/arm-timings.json`` holds the measurements and
``docs/_generated/gate-status.md`` is rendered from it. Neither file is edited
by hand: ``./run.sh timings`` refreshes both, and ``--check`` (part of the
``docs`` arm) refuses a page that no longer matches the measurements or the
live repository facts it cites.

    python scripts/gate_report.py --capture           # full measurement, including GNN
    python scripts/gate_report.py --capture --offline # no GNN acquisition or verification
    python scripts/gate_report.py --check             # consistency, count and dispatch
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from gnn_conformance import EXEMPLAR_PATH, PIN_PATH, load_pin

SCHEMA = "isss-gate-timings/v1"
DEFAULT_OUTPUT_DIR = Path("docs/_generated")
DATA_PATH = DEFAULT_OUTPUT_DIR / "arm-timings.json"
DOC_PATH = DEFAULT_OUTPUT_DIR / "gate-status.md"
WORKFLOW_PATH = Path(".github/workflows/ci.yml")
NOT_USED_COMPOSITE = (
    "ActiveInferenceInstitute/.github/.github/actions/"
    "setup-python-uv@7159e67315330aac8e414aebae0ad1e999a41448"
)

# arm -> the pre-gate CI step it replaces (None: the arm is new)
ARMS: tuple[tuple[str, list[str] | None, str], ...] = (
    ("lint", [sys.executable, "-m", "ruff", "check", "."], "./run.sh lint"),
    ("test", None, "./run.sh test"),
    ("test-cov", [sys.executable, "-m", "pytest"], "./run.sh test-cov"),
    ("docs", None, "./run.sh docs"),
    ("gnn", None, "./run.sh gnn"),
)


def timed(command: list[str]) -> tuple[float, str]:
    """Run one command, return its wall time and combined output."""
    started = time.perf_counter()
    completed = subprocess.run(
        command, capture_output=True, text=True,
        env={**os.environ, "PYTHON": sys.executable},
    )
    seconds = time.perf_counter() - started
    output = completed.stdout + completed.stderr
    if completed.returncode != 0:
        sys.stderr.write(output)
        raise SystemExit(f"{' '.join(command)} failed with exit {completed.returncode}")
    return seconds, output


def collected_tests() -> int:
    """Number of tests pytest collects in this checkout."""
    _, output = timed([sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-cov"])
    match = re.search(r"(\d+) tests? collected", output)
    if not match:
        raise SystemExit("could not read the collected test count from pytest")
    return int(match.group(1))


def dispatched_arms() -> list[str]:
    """Arms ``run.sh`` dispatches, in file order."""
    text = Path("run.sh").read_text(encoding="utf-8")
    block = text.split("case ", 1)[1]
    return re.findall(r"^  ([a-z][a-z-]*)\)", block, flags=re.MULTILINE)


def workflow_facts() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Jobs (key, display name, arms) and pinned actions, read from the workflow."""
    lines = WORKFLOW_PATH.read_text(encoding="utf-8").splitlines()
    jobs: list[dict[str, str]] = []
    try:
        start = lines.index("jobs:")
    except ValueError:
        raise SystemExit(f"{WORKFLOW_PATH} declares no jobs: section") from None
    current: dict[str, str] | None = None
    body: list[str] = []
    for line in lines[start + 1 :]:
        key = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if key:
            if current is not None:
                current["arms"] = ", ".join(dict.fromkeys(re.findall(r"run\.sh ([a-z][a-z-]*)", "\n".join(body))))
                jobs.append(current)
            current = {"key": key.group(1), "name": "", "python": ""}
            body = []
            continue
        if current is None:
            continue
        body.append(line)
        name = re.match(r"^    name:\s*(.+?)\s*$", line)
        if name and not current["name"]:
            current["name"] = name.group(1)
        versions = re.match(r"^\s+python-version:\s*(.+?)\s*$", line)
        if versions and not current["python"]:
            current["python"] = versions.group(1)
    if current is not None:
        current["arms"] = ", ".join(dict.fromkeys(re.findall(r"run\.sh ([a-z][a-z-]*)", "\n".join(body))))
        jobs.append(current)

    actions: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines:
        match = re.match(r"^\s*(?:-\s+)?uses:\s*(\S+)(?:\s+#\s*(.+?))?\s*$", line)
        if not match or match.group(1) in seen:
            continue
        seen.add(match.group(1))
        actions.append({"reference": match.group(1), "version": match.group(2) or ""})
    return jobs, actions


def _validate_data(data: dict) -> None:
    """Accept legacy measurements and explicit offline states, never invented numbers."""
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise SystemExit(f"invalid timing schema; expected {SCHEMA}")
    try:
        date.fromisoformat(data["recorded"])
        if not all(isinstance(data["host"][key], str) and data["host"][key]
                   for key in ("platform", "python", "cpus")):
            raise ValueError("invalid host identity")
        mode = data.get("capture_mode", "full")
        if mode not in {"full", "offline"} or not isinstance(data["arms"], list):
            raise ValueError("invalid capture mode or arms")
        names = set()
        for arm in data["arms"]:
            name = arm["name"]
            if name in names or name not in {item[0] for item in ARMS}:
                raise ValueError("duplicate or unknown arm")
            names.add(name)
            status = arm.get("status", "measured")
            if status == "unmeasured":
                if (mode != "offline" or name != "gnn" or "after_seconds" in arm
                        or "before_seconds" in arm):
                    raise ValueError("unmeasured is allowed only for offline GNN")
            elif status == "measured":
                seconds = arm["after_seconds"]
                if (type(seconds) not in (int, float) or not math.isfinite(seconds)
                        or seconds < 0 or (mode == "offline" and name == "gnn")):
                    raise ValueError("invalid measured duration/state")
            else:
                raise ValueError("invalid observation state")
            if "before_seconds" in arm:
                before = arm["before_seconds"]
                if type(before) not in (int, float) or not math.isfinite(before) or before < 0:
                    raise ValueError("invalid baseline duration")
        if not isinstance(data.get("history", []), list):
            raise ValueError("invalid historical snapshot list")
        if not all(isinstance(snapshot, dict) for snapshot in data.get("history", [])):
            raise ValueError("invalid historical snapshot")
        historical = data.get("historical_gnn", [])
        if not isinstance(historical, list):
            raise ValueError("invalid historical GNN list")
        for observation in historical:
            date.fromisoformat(observation["recorded"])
            if not all(isinstance(observation["host"][key], str) and observation["host"][key]
                       for key in ("platform", "python", "cpus")):
                raise ValueError("invalid historical host")
            arm = observation["observation"]
            seconds = arm["after_seconds"]
            if (arm["name"] != "gnn" or type(seconds) not in (int, float)
                    or not math.isfinite(seconds) or seconds < 0):
                raise ValueError("invalid historical GNN observation")
        suite = data["suite"]
        if (type(suite["tests"]) is not int or type(suite["passed"]) is not int
                or not 0 <= suite["passed"] <= suite["tests"]
                or type(suite["coverage_percent"]) not in (int, float)
                or not 0 <= suite["coverage_percent"] <= 100):
            raise ValueError("invalid observed suite totals")
    except (KeyError, TypeError, ValueError) as error:
        raise SystemExit(f"invalid timing evidence: {error}") from None


def _historical_gnn(previous: dict | None) -> list[dict]:
    """Carry original date/host/bytes, without nesting or inventing a pin binding."""
    if previous is None:
        return []
    history = list(previous.get("historical_gnn", []))
    for arm in previous["arms"]:
        if arm["name"] == "gnn" and arm.get("status", "measured") == "measured":
            observation = {
                "recorded": previous["recorded"],
                "host": dict(previous["host"]),
                "observation": dict(arm),
            }
            if observation not in history:
                history.append(observation)
    return history


def capture(offline: bool = False) -> int:
    """Measure admitted arms; offline mode explicitly leaves current GNN unmeasured."""
    previous = None
    if DATA_PATH.exists():
        previous = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        _validate_data(previous)
    history = [] if previous is None else list(previous.get("history", []))
    if previous is not None:
        history.append({key: value for key, value in previous.items() if key != "history"})
    data = {
        "schema": SCHEMA,
        "recorded": date.today().isoformat(),
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpus": str(os.cpu_count()),
        },
        "capture_mode": "offline" if offline else "full",
        "historical_gnn": _historical_gnn(previous),
        "history": history,
        "arms": [],
        "suite": {},
    }

    docs_command = ["./run.sh", "docs", "--output-dir", str(DATA_PATH.parent.resolve())]

    def write() -> None:
        _validate_data(data)
        DATA_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        DOC_PATH.write_text(render(data), encoding="utf-8")

    def measure(name: str, before: list[str] | None, after: str) -> None:
        record = {"name": name, "after_command": after, "status": "measured"}
        if before is not None:
            record["before_command"] = "python " + " ".join(before[1:])
            record["before_seconds"] = round(timed(before)[0], 2)
        seconds, output = timed(docs_command if name == "docs" else ["./run.sh", name])
        record["after_seconds"] = round(seconds, 2)
        print(f"{name:9s} {seconds:7.2f}s", file=sys.stderr)
        if name == "test-cov":
            coverage = re.search(r"Total coverage:\s*([\d.]+)%", output)
            passed = re.search(r"(\d+) passed", output)
            if not coverage or not passed:
                raise SystemExit("could not read coverage or the passed count from pytest")
            data["suite"] = {
                "tests": collected_tests(),
                "passed": int(passed.group(1)),
                "coverage_percent": float(coverage.group(1)),
            }
        data["arms"].append(record)

    for name, before, after in ARMS:
        if name == "docs":
            continue
        if offline and name == "gnn":
            data["arms"].append({
                "name": "gnn", "after_command": after, "status": "unmeasured",
                "reason": "offline refresh: GNN acquisition and verification were not executed",
            })
        else:
            measure(name, before, after)
    # Bootstrap: docs checks this first complete non-docs record before its own
    # duration can exist. A failed docs run is never appended as a measurement.
    write()
    measure("docs", None, "./run.sh docs")
    write()
    timed(docs_command)
    print(f"wrote {DATA_PATH} and {DOC_PATH}", file=sys.stderr)
    return 0


def render(data: dict) -> str:
    """The gate-status page for one measurements record."""
    _validate_data(data)
    pin = load_pin(PIN_PATH)
    jobs, actions = workflow_facts()
    suite = data["suite"]

    lines = [
        "<!-- Generated by scripts/gate_report.py from docs/_generated/arm-timings.json.",
        "     Do not edit by hand: run ./run.sh timings to re-measure, then",
        "     ./run.sh docs to verify the page matches. -->",
        "",
        "# Gate status",
        "",
        "The gate has one entry point, `./run.sh`; CI calls the same arms.",
        "Measured rows in this record were observed on",
        f"{data['host']['platform']}, CPython {data['host']['python']},",
        f"{data['host']['cpus']} CPUs on {data['recorded']}.",
        "An offline refresh does not execute or qualify the GNN arm.",
        "",
        "## Arms",
        "",
        "| Arm | Command | Before (s) | After (s) | Observation |",
        "| --- | --- | --- | --- | --- |",
    ]
    by_name = {arm["name"]: arm for arm in data["arms"]}
    for name in (arm[0] for arm in ARMS):
        arm = by_name.get(name)
        if arm is None:
            continue
        if arm.get("status", "measured") == "unmeasured":
            before, after, status = "—", "unmeasured", "offline; not executed"
        else:
            before = f"{arm['before_seconds']:.2f}" if "before_seconds" in arm else "— (new)"
            after, status = f"{arm['after_seconds']:.2f}", "measured"
        lines.append(
            f"| `{arm['name']}` | `{arm['after_command']}` | {before} | {after} | {status} |"
        )
    lines += [
        "",
        "The old CI step is measured with the same interpreter that runs the arm",
        "(`python -m ruff check .`, `python -m pytest`). Each arm adds one `bash`",
        "start, which is the whole difference in the `lint` row — the command",
        "itself is unchanged. \"Before\" is what the earlier workflow ran: `ruff",
        "check .` and `pytest` with coverage inside all three Python legs. The",
        "gate now lints once, gates coverage once, and runs the coverage-free arm",
        "on the two other versions, in the same job and install as lint and docs.",
        "`test`, `docs` and `gnn` had no separate step.",
        "",
        "Measured values are observations, not speedup claims. Explicit historical",
        "GNN values below retain their own original dates and hosts; they are not",
        "fresh success, not a current After value, and not bound retroactively to",
        "the current pin. Historical source snapshots remain in the JSON record.",
        "",
        "## Historical GNN observations",
        "",
        *(
            [
                "| Recorded | Host | Python | Historical seconds |",
                "| --- | --- | --- | --- |",
                *[
                    f"| {item['recorded']} | {item['host']['platform']} | "
                    f"{item['host']['python']} | {item['observation']['after_seconds']:.2f} |"
                    for item in data.get("historical_gnn", [])
                ],
            ] if data.get("historical_gnn") else ["No historical GNN timing is recorded."]
        ),
        "",
        "## Suite",
        "",
        "| Measurement | Value |",
        "| --- | --- |",
        f"| Tests collected | {suite['tests']} |",
        f"| Tests passed by the `test-cov` arm | {suite['passed']} |",
        f"| Coverage (gate: 90%) | {suite['coverage_percent']:.2f}% |",
        "",
        "The suite declares no pytest markers, so the default `test` arm runs all",
        "of it and only drops coverage instrumentation; `test-cov` adds the",
        "`--cov-fail-under=90` gate from `pyproject.toml`.",
        "",
        "## CI jobs",
        "",
        "| Job key | Display name | Python | Arms |",
        "| --- | --- | --- | --- |",
    ]
    for job in jobs:
        lines.append(
            f"| `{job['key']}` | {job['name'] or '(key)'} | "
            f"{job['python'].strip() or '—'} | {job['arms'] or '—'} |"
        )
    lines += [
        "",
        "## Pinned GNN conformance",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Pin file | `{PIN_PATH}` |",
        f"| Schema | `{pin['schema']}` |",
        f"| Repository | `{pin['repository']}` |",
        f"| Tag | `{pin['tag']}` |",
        f"| Revision | `{pin['revision']}` |",
        f"| Recorded | {pin['recorded']} |",
        "",
        f"`{PIN_PATH}` is the canonical pin; `.github/GNN.md` is the pointer that",
        "records what the job parses. The job installs the parser at the pinned",
        "revision, checks the installed version against the tag, then parses and",
        "type-checks every `*.gnn.md` sketch in the repository; ISSS carries none,",
        f"so it parses the pinned upstream `{EXEMPLAR_PATH}` exemplar as a",
        "pipeline and pin baseline. `scripts/gnn_conformance.py` is that check,",
        "and `./run.sh gnn` runs its offline pin validation, acquisition and",
        "verification in that order.",
        "",
        "## Actions",
        "",
        "| Action | Version |",
        "| --- | --- |",
    ]
    for action in actions:
        lines.append(f"| `{action['reference']}` | {action['version'] or '—'} |")
    lines += [
        "",
        "Each reference above is immutable (a commit id, not a tag). The workflow",
        "does not use the organization composite action",
        f"`{NOT_USED_COMPOSITE}`:",
        "the repository installs with pip and ships no lock file, so nothing here",
        "can call a uv-based setup action without also changing the install",
        "method (see [TO-DO.md](../../TO-DO.md#readiness-standard-gaps-measured-2026-11-11)).",
        "",
        "## Reproducing",
        "",
        "```bash",
        "./run.sh ci        # every arm, in CI order",
        "./run.sh timings           # full measurement, including network-dependent GNN",
        "./run.sh timings --offline # offline arms; GNN unmeasured, history retained",
        "./run.sh docs              # check links and report consistency/count/dispatch",
        "```",
        "",
    ]
    return "\n".join(lines)


def check() -> int:
    """Refuse a page that no longer matches its data or the live repository."""
    problems: list[str] = []
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    _validate_data(data)

    recorded = [arm["name"] for arm in data["arms"]]
    unmeasured = [name for name, _, _ in ARMS if name != "docs" and name not in recorded]
    if unmeasured:
        problems.append(f"{DATA_PATH} has no measurement for {unmeasured}; run ./run.sh timings")
    dispatched = dispatched_arms()
    missing = [arm for arm in recorded if arm not in dispatched]
    helpers = [arm for arm in ("ci", "timings", "list") if arm not in dispatched]
    if missing or helpers:
        problems.append(
            f"run.sh dispatches {dispatched} but {DATA_PATH} records {recorded}"
            + (f"; not dispatched: {missing}" if missing else "")
            + (f"; missing helpers: {helpers}" if helpers else "")
            + "; run ./run.sh timings"
        )

    live_tests = collected_tests()
    if live_tests != data["suite"]["tests"]:
        problems.append(
            f"pytest collects {live_tests} tests but {DATA_PATH} records "
            f"{data['suite']['tests']}; run ./run.sh timings"
        )

    expected = render(data)
    actual = DOC_PATH.read_text(encoding="utf-8")
    if expected != actual:
        diff = "".join(
            difflib.unified_diff(
                actual.splitlines(keepends=True),
                expected.splitlines(keepends=True),
                fromfile=str(DOC_PATH),
                tofile=f"{DOC_PATH} (regenerated)",
            )
        )
        problems.append(f"{DOC_PATH} is stale:\n{diff}")

    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(
        f"gate report consistent: {len(recorded)} arms, {live_tests} tests; "
        f"GNN {'unmeasured (offline)' if data.get('capture_mode') == 'offline' else 'recorded'}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    global DATA_PATH, DOC_PATH
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture", action="store_true", help="measure the arms and regenerate")
    mode.add_argument("--check", action="store_true", help="verify the committed page")
    parser.add_argument("--offline", action="store_true", help="capture without GNN/network acquisition")
    parser.add_argument(
        "--output-dir", type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="measurement/page directory; forwarded explicitly to child docs checks",
    )
    args = parser.parse_args(argv)
    if args.offline and not args.capture:
        parser.error("--offline requires --capture")
    previous_paths = DATA_PATH, DOC_PATH
    DATA_PATH = args.output_dir / "arm-timings.json"
    DOC_PATH = args.output_dir / "gate-status.md"
    try:
        if args.capture:
            args.output_dir.mkdir(parents=True, exist_ok=True)
        return check() if args.check else capture(offline=args.offline)
    finally:
        DATA_PATH, DOC_PATH = previous_paths


if __name__ == "__main__":
    raise SystemExit(main())
