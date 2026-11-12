"""The pinned GNN check must fail closed and label what it actually checked."""

import json
import sys
import types

import pytest

from scripts import gnn_conformance

PIN = {"tag": "v5.0.3", "revision": "0" * 40, "repository": gnn_conformance.EXPECTED_REPOSITORY}


class _Parsed:
    parse_errors: list = []


def _install_stub(monkeypatch, outcome):
    """Install a stub ``gnn`` package whose type checker returns ``outcome``."""
    calls = {"is_content": []}

    def validate_gnn_syntax(text, is_content=False):
        calls["is_content"].append(is_content)
        return True, []

    class Checker:
        def validate_gnn_files(self, model_dir, output_dir):
            return outcome

    root = types.ModuleType("gnn")
    root.__version__ = "5.0.3"
    basic = types.ModuleType("gnn.parsers.basic")
    basic.parse_gnn_formal = lambda path: _Parsed()
    basic.validate_gnn_syntax = validate_gnn_syntax
    checking = types.ModuleType("gnn.type_checker")
    checking.GNNTypeChecker = Checker
    for name, module in {
        "gnn": root,
        "gnn.parsers": types.ModuleType("gnn.parsers"),
        "gnn.parsers.basic": basic,
        "gnn.type_checker": checking,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    return calls


@pytest.fixture
def sketch(tmp_path, monkeypatch):
    (tmp_path / "m.gnn.md").write_text("## GNNSection\nX\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)


@pytest.mark.parametrize("outcome", [2, False, None, 0])
def test_non_true_type_checker_result_fails(monkeypatch, sketch, outcome):
    _install_stub(monkeypatch, outcome)
    with pytest.raises(SystemExit, match=r"did not pass .*expected True"):
        gnn_conformance.verify(PIN)


def test_repository_sketches_get_content_label_and_is_content(monkeypatch, sketch):
    calls = _install_stub(monkeypatch, True)
    receipt = gnn_conformance.verify(PIN)
    assert receipt["result"] == "repository-content-passed"
    assert receipt["source"] == "repository"
    assert calls["is_content"] == [True]
    json.dumps(receipt)


def test_exemplar_only_run_gets_baseline_label(monkeypatch, tmp_path):
    calls = _install_stub(monkeypatch, True)
    monkeypatch.chdir(tmp_path)

    def fake_urlretrieve(url, target):
        target.write_text("## GNNSection\nX\n", encoding="utf-8")

    monkeypatch.setattr(gnn_conformance.urllib.request, "urlretrieve", fake_urlretrieve)
    receipt = gnn_conformance.verify(PIN)
    assert receipt["result"] == "pinned-exemplar-baseline-passed"
    assert receipt["source"] == "pinned-exemplar"
    assert calls["is_content"] == [True]
