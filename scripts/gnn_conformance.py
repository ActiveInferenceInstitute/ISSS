#!/usr/bin/env python3
"""Pinned GNN conformance check for ISSS.

The pin lives in ``.github/gnn-pin.json`` (schema ``gnn-importer-pin/v1``) and
names the Generalized Notation Notation parser release this repository follows.
Both the ``gnn-conformance`` CI job and the local gate run this file, so the
check exists once.

Modes:

``--check-pin``
    Validate the pin file offline and print it as JSON. No network, no import.
``--install``
    Install the pinned parser from the revision in the pin file. Needs network.
``--verify``
    Import the installed parser, confirm its version, then parse and
    type-check every ``*.gnn.md`` sketch in the repository. When the repository
    has no sketch, parse the pinned upstream immediacy exemplar instead.

``--install`` and ``--verify`` are separate because CI splits acquisition from
verification; ``./run.sh gnn`` runs both in order.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SCHEMA = "gnn-importer-pin/v1"
PIN_PATH = Path(".github/gnn-pin.json")
EXPECTED_REPOSITORY = "ActiveInferenceInstitute/Generalized_Notation_Notation"
EXEMPLAR_PATH = "input/gnn_files/basics/static_perception.md"
INSTALL_DEPENDENCIES = ("defusedxml", "psutil", "pyyaml")


def load_pin(path: Path = PIN_PATH) -> dict:
    """Read and validate the pin file; raise ``SystemExit`` with the reason."""
    try:
        pin = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"pin file {path} is missing") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"pin file {path} is not valid JSON: {error}") from None

    if not isinstance(pin, dict):
        raise SystemExit(f"pin file {path} must hold one JSON object")
    if pin.get("schema") != SCHEMA:
        raise SystemExit(f"pin schema is {pin.get('schema')!r}, expected {SCHEMA!r}")
    for field in ("repository", "revision", "tag", "recorded"):
        if not isinstance(pin.get(field), str) or not pin[field]:
            raise SystemExit(f"pin field {field!r} must be a non-empty string")
    if pin["repository"] != EXPECTED_REPOSITORY:
        raise SystemExit(
            f"pin repository is {pin['repository']!r}, expected {EXPECTED_REPOSITORY!r}"
        )
    revision = pin["revision"]
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise SystemExit(f"pin revision {revision!r} is not a 40-character commit id")
    return pin


def install(pin: dict) -> None:
    """Install the parser pinned at ``pin['revision']``."""
    pip = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check"]
    subprocess.check_call([*pip, *INSTALL_DEPENDENCIES])
    spec = (
        "generalized-notation-notation @ "
        f"git+https://github.com/{pin['repository']}.git@{pin['revision']}"
    )
    subprocess.check_call([*pip, "--no-deps", spec])


def verify(pin: dict) -> dict:
    """Parse and type-check the repository sketches, or the pinned exemplar."""
    from gnn import __version__
    from gnn.parsers.basic import parse_gnn_formal, validate_gnn_syntax
    from gnn.type_checker import GNNTypeChecker

    expected_version = pin["tag"].removeprefix("v")
    if __version__ != expected_version:
        raise SystemExit(f"installed GNN {__version__!r} does not match {pin['tag']!r}")

    def check(sketch: Path, label: str) -> None:
        parsed = parse_gnn_formal(sketch)
        if parsed is None or getattr(parsed, "parse_errors", None):
            raise SystemExit(f"{label} did not parse cleanly")
        valid, errors = validate_gnn_syntax(sketch.read_text(encoding="utf-8"))
        if not valid:
            raise SystemExit(f"{label} syntax errors: {errors!r}")

    sketches = sorted(Path(".").rglob("*.gnn.md"))
    with tempfile.TemporaryDirectory(prefix="isss-gnn-") as output_dir:
        model_dir = Path(output_dir) / "models"
        model_dir.mkdir()
        if sketches:
            for sketch in sketches:
                check(sketch, str(sketch))
                shutil.copy2(sketch, model_dir / f"{len(list(model_dir.iterdir())):03d}_{sketch.name}")
            if not GNNTypeChecker().validate_gnn_files(model_dir, Path(output_dir)):
                raise SystemExit("GNN type checker rejected the repository sketches")
            checked, source = len(sketches), "repository"
        else:
            exemplar_url = (
                f"https://raw.githubusercontent.com/{pin['repository']}/"
                f"{pin['revision']}/{EXEMPLAR_PATH}"
            )
            exemplar = model_dir / Path(EXEMPLAR_PATH).name
            urllib.request.urlretrieve(exemplar_url, exemplar)
            check(exemplar, "pinned exemplar")
            if not GNNTypeChecker().validate_gnn_files(model_dir, Path(output_dir)):
                raise SystemExit("GNN type checker rejected the pinned exemplar")
            checked, source = 1, "pinned-exemplar"

    return {
        "gnn-version": __version__,
        "pin-revision": pin["revision"],
        "models": checked,
        "source": source,
        "result": "verified",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-pin", action="store_true", help="validate the pin file offline")
    mode.add_argument("--install", action="store_true", help="install the pinned parser")
    mode.add_argument("--verify", action="store_true", help="run the conformance check")
    args = parser.parse_args(argv)

    pin = load_pin()
    if args.check_pin:
        print(json.dumps(pin, indent=2, sort_keys=True))
        return 0
    if args.install:
        install(pin)
        return 0
    print(json.dumps(verify(pin), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
