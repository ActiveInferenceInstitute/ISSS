#!/usr/bin/env python3
"""Measure the gate arms and render the generated gate-status page.

``docs/_generated/arm-timings.json`` holds the measurements and
``docs/_generated/gate-status.md`` is rendered from it. Neither file is edited
by hand: ``./run.sh timings`` refreshes both, and ``--check`` (part of the
``docs`` arm) refuses a page that no longer matches the measurements or the
live repository facts it cites.

    python scripts/gate_report.py capture   # run every arm once, timed
    python scripts/gate_report.py --check   # verify the committed page
"""

from __future__ import annotations

import argparse
import difflib
import json
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
DATA_PATH = Path("docs/_generated/arm-timings.json")
DOC_PATH = Path("docs/_generated/gate-status.md")
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
    completed = subprocess.run(command, capture_output=True, text=True)
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


def capture() -> int:
    """Run every arm once, timed, and write the data file and the page."""
    data: dict[str, object] = {
        "schema": SCHEMA,
        "recorded": date.today().isoformat(),
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpus": str(os.cpu_count()),
        },
        "arms": [],
        "suite": {},
    }

    def entry(name: str) -> dict:
        return next(arm for arm in data["arms"] if arm["name"] == name)

    def write() -> None:
        DATA_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        DOC_PATH.write_text(render(data), encoding="utf-8")

    def measure(name: str, before: list[str] | None, after: str) -> None:
        record: dict[str, object] = {"name": name, "after_command": after}
        if before is not None:
            record["before_command"] = "python " + " ".join(before[1:])
            record["before_seconds"] = round(timed(before)[0], 2)
        seconds, output = timed(["./run.sh", name])
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

    # The docs arm verifies the rendered page, so it cannot be timed against a
    # page that already claims its own duration: the other arms are measured
    # and written first, the docs arm runs against that page, and the final
    # page is then verified by one more docs run.
    for name, before, after in ARMS:
        if name != "docs":
            measure(name, before, after)
    write()
    measure("docs", None, "./run.sh docs")
    write()
    timed(["./run.sh", "docs"])
    print(f"wrote {DATA_PATH} and {DOC_PATH}", file=sys.stderr)
    return 0


def render(data: dict) -> str:
    """The gate-status page for one measurements record."""
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
        "The gate has one entry point, `./run.sh`, and every arm of it is the exact",
        "command `.github/workflows/ci.yml` runs. This page records what each arm",
        f"costs on the host that measured it ({data['host']['platform']},",
        f"CPython {data['host']['python']}, {data['host']['cpus']} CPUs) on",
        f"{data['recorded']}.",
        "",
        "## Arms",
        "",
        "| Arm | Command | Before (s) | After (s) |",
        "| --- | --- | --- | --- |",
    ]
    by_name = {arm["name"]: arm for arm in data["arms"]}
    for name in (arm[0] for arm in ARMS):
        arm = by_name.get(name)
        if arm is None:
            continue
        before = (
            f"{arm['before_seconds']:.2f}"
            if "before_seconds" in arm
            else "— (new)"
        )
        lines.append(
            f"| `{arm['name']}` | `{arm['after_command']}` | {before} | {arm['after_seconds']:.2f} |"
        )
    lines += [
        "",
        "The old CI step is measured with the same interpreter that runs the arm",
        "(`python -m ruff check .`, `python -m pytest`). Each arm adds one `bash`",
        "start, which is the whole difference in the `lint` row — the command",
        "itself is unchanged. \"Before\" is the earlier workflow's step: every job",
        "ran `ruff check .` and `pytest` (with coverage) in each of its three",
        "Python legs, so the gate now does that work once instead of three times.",
        "`test`, `docs` and `gnn` had no separate step.",
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
        "./run.sh timings   # re-measure the arms and regenerate this page",
        "./run.sh docs      # verify links and that this page matches its data",
        "```",
        "",
    ]
    return "\n".join(lines)


def check() -> int:
    """Refuse a page that no longer matches its data or the live repository."""
    problems: list[str] = []
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise SystemExit(f"{DATA_PATH} schema is {data.get('schema')!r}, expected {SCHEMA!r}")

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
    print(f"gate status current: {len(recorded)} arms, {live_tests} tests")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture", action="store_true", help="measure the arms and regenerate")
    mode.add_argument("--check", action="store_true", help="verify the committed page")
    args = parser.parse_args(argv)
    return check() if args.check else capture()


if __name__ == "__main__":
    raise SystemExit(main())
