#!/usr/bin/env bash
# Single gate entry point for the ISSS repository.
#
# Every arm is the command CI runs: .github/workflows/ci.yml calls
# `./run.sh <arm>` and nothing else, so a local green run is the same gate as a
# hosted one, not a second copy of it.
#
#   ./run.sh lint      ruff check .                    (pyproject.toml lint contract)
#   ./run.sh test      pytest without coverage         (the whole suite, fast)
#   ./run.sh test-cov  pytest with the 90% coverage gate (same suite, instrumented)
#   ./run.sh docs      Markdown links, generated docs and Publishing identity digests
#   ./run.sh gnn       pinned GNN conformance (installs the pinned parser; needs network)
#   ./run.sh ci        lint, test, test-cov, docs, gnn
#   ./run.sh timings   re-measure every arm, regenerate docs/_generated/
#   ./run.sh list      list arms
#
# There is no types arm: the repository declares no type checker (no
# [tool.mypy] section in pyproject.toml and no checker in the dev extra).
#
# The suite declares no pytest markers, so `test` is the whole suite minus
# coverage instrumentation rather than a selection; see docs/README.md.
#
# Interpreter: $PYTHON if set, else ./.venv/bin/python, else python3.

set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd -- "$ROOT"

if [[ -n ${PYTHON:-} ]]; then
  PY=$PYTHON
elif [[ -x $ROOT/.venv/bin/python ]]; then
  PY=$ROOT/.venv/bin/python
else
  PY=$(command -v python3)
fi

lint() { "$PY" -m ruff check .; }
test_fast() { "$PY" -m pytest -q --no-cov; }
test_cov() { "$PY" -m pytest; }
docs() {
  "$PY" scripts/gate/identity.py
  "$PY" scripts/gate/identity.py --verify-copy docs/workflows/record-identity.schema.json
  "$PY" scripts/gate/identity.py --verify-copy scripts/gate/identity.py
  "$PY" scripts/gate/identity.py --verify-copy .github/gnn-pin.json
  "$PY" scripts/check_docs.py
  "$PY" scripts/gate_report.py --check
}
gnn() {
  "$PY" scripts/gnn_conformance.py --install
  "$PY" scripts/gnn_conformance.py --verify
}

usage() {
  sed -n '2,23p' "$ROOT/run.sh" | sed 's/^# \{0,1\}//'
}

case "${1:-help}" in
  lint) lint ;;
  test) test_fast ;;
  test-cov) test_cov ;;
  docs) docs ;;
  gnn) gnn ;;
  ci)
    lint
    test_fast
    test_cov
    docs
    gnn
    ;;
  timings) exec "$PY" scripts/gate_report.py --capture ;;
  list)
    printf '%s\n' lint test test-cov docs gnn ci timings list
    ;;
  help | -h | --help) usage ;;
  *)
    printf 'unknown arm: %s\n\n' "${1:-}" >&2
    usage >&2
    exit 2
    ;;
esac
