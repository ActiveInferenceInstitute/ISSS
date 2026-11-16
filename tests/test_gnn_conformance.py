"""The pinned GNN check must fail closed and label what it actually checked."""

import json
import sys
import types
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from scripts import gnn_conformance

gate = gnn_conformance

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
            if outcome is True:
                files = sorted(model_dir.iterdir())
                (output_dir / "type_check_results.json").write_text(json.dumps({
                    "processed_files": len(files), "success": True, "errors": [],
                    "validation_results": [{"file_path": str(path), "valid": True,
                                            "errors": [], "warnings": []} for path in files],
                }))
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
    with pytest.raises(SystemExit, match=r"type checker (failed|evidence rejected)"):
        gnn_conformance.verify(PIN)


@pytest.mark.parametrize("outcome", [2, False, None, 0])
def test_non_true_type_checker_result_fails_on_exemplar(monkeypatch, tmp_path, outcome):
    _install_stub(monkeypatch, outcome)
    monkeypatch.chdir(tmp_path)

    def fake_urlretrieve(url, target):
        target.write_text("## GNNSection\nX\n", encoding="utf-8")

    monkeypatch.setattr(gnn_conformance.urllib.request, "urlretrieve", fake_urlretrieve)
    with pytest.raises(SystemExit, match=r"type checker (failed|evidence rejected)"):
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


@pytest.fixture(params=['repository', 'exemplar'])
def upstream_fixture(tmp_path, monkeypatch, request):
    monkeypatch.chdir(tmp_path)
    if request.param == 'repository':
        for directory in ('a', 'b'):
            path = tmp_path / directory / 'shared.gnn.md'
            path.parent.mkdir()
            path.write_text('offline parser input')
    packages = {name: ModuleType(name) for name in (
        'gnn', 'gnn.parsers', 'gnn.parsers.basic', 'gnn.type_checker'
    )}
    packages['gnn'].__path__ = []
    packages['gnn.parsers'].__path__ = []
    packages['gnn'].__version__ = '5.0.3'
    packages['gnn.parsers.basic'].parse_gnn_formal = lambda path: SimpleNamespace(parse_errors=[])
    packages['gnn.parsers.basic'].validate_gnn_syntax = lambda text, is_content=False: (True, [])
    for name, module in packages.items():
        monkeypatch.setitem(sys.modules, name, module)
    state = {'status': True, 'mutation': None, 'downloads': []}

    class Checker:
        def validate_gnn_files(self, model_dir, output_dir):
            files = sorted(Path(model_dir).iterdir())
            rows = [{
                'file_path': str(path), 'file_name': path.name, 'valid': True,
                'errors': [], 'warnings': [], 'type_issues': [],
            } for path in files]
            report = {
                'processed_files': len(files), 'success': True, 'errors': [],
                'validation_results': rows, 'type_analysis': [],
            }
            mutation = state['mutation']
            if mutation == 'invalid':
                rows[0]['valid'] = False
                rows[0]['errors'] = ['type mismatch']
                report['success'] = False
            elif mutation == 'empty':
                report.update(processed_files=0, success=False, errors=['No GNN files found'],
                              validation_results=[])
            elif mutation == 'warning':
                rows[0]['warnings'] = ['advisory']
            elif mutation == 'count-mismatch':
                report['processed_files'] += 1
            elif mutation == 'missing-row':
                rows.pop()
            elif mutation == 'extra-row':
                rows.append(dict(rows[0]))
            elif mutation == 'substituted-path':
                rows[0]['file_path'] = str(tmp_path / 'not-a-staged-model.md')
            elif mutation == 'duplicate-path':
                if len(rows) == 1:
                    rows.append(dict(rows[0]))
                    report['processed_files'] = 2
                else:
                    rows[1]['file_path'] = rows[0]['file_path']
            elif mutation == 'missing-valid':
                rows[0].pop('valid')
            elif mutation == 'alias-valid':
                rows[0].pop('valid')
                rows[0]['is_valid'] = True
            elif mutation == 'integer-valid':
                rows[0]['valid'] = 1
            elif mutation == 'string-valid':
                rows[0]['valid'] = 'false'
            elif mutation == 'boolean-count':
                report['processed_files'] = True
            elif mutation == 'float-count':
                report['processed_files'] = float(len(files))
            elif mutation == 'string-count':
                report['processed_files'] = str(len(files))
            elif mutation == 'top-errors':
                report['errors'] = ['processing failed after discovery']
            elif mutation == 'row-errors':
                rows[0]['errors'] = ['contradictory error']
            elif mutation == 'bad-errors':
                rows[0]['errors'] = ''
            elif mutation == 'bad-warnings':
                rows[0]['warnings'] = 'not a warning list'
            elif mutation == 'contradictory-success':
                report['success'] = False
            elif mutation == 'bad-rows':
                report['validation_results'] = None
            elif mutation == 'bad-row':
                rows[0] = None
            elif mutation == 'root-null':
                report = None
            elif mutation == 'root-list':
                report = []
            if mutation != 'missing-report':
                destination = Path(output_dir) / 'type_check_results.json'
                destination.write_text('{broken' if mutation == 'invalid-json' else json.dumps(report))
            return state['status']

    packages['gnn.type_checker'].GNNTypeChecker = Checker

    def exemplar(url, destination):
        state['downloads'].append(url)
        Path(destination).write_text('offline pinned exemplar')

    monkeypatch.setattr(gate.urllib.request, 'urlretrieve', exemplar)
    state['branch'] = request.param
    return state


@pytest.mark.parametrize(('status', 'mutation'), [(True, None), (True, 'warning'), (2, 'warning')])
def test_complete_valid_files_are_admitted_in_both_branches(upstream_fixture, status, mutation):
    # Integer-2 warning-only validity is a documented-sentinel compatibility
    # fixture, not an assertion that the inspected producer naturally returns it.
    upstream_fixture.update(status=status, mutation=mutation)
    result = gate.verify(PIN)
    repository = upstream_fixture['branch'] == 'repository'
    assert result['result'] == ('repository-content-passed' if repository
                                else 'pinned-exemplar-baseline-passed')
    assert result['models'] == (2 if repository else 1)
    assert result['source'] == ('repository' if repository else 'pinned-exemplar')
    assert result['gnn-version'] == '5.0.3'
    assert result['pin-revision'] == PIN['revision']
    expected_url = (
        f"https://raw.githubusercontent.com/{PIN['repository']}/"
        f"{PIN['revision']}/{gate.EXEMPLAR_PATH}"
    )
    assert upstream_fixture['downloads'] == ([] if repository else [expected_url])


@pytest.mark.parametrize('mutation', [
    'invalid', 'empty', 'count-mismatch', 'missing-row', 'extra-row', 'substituted-path',
    'duplicate-path', 'missing-valid', 'alias-valid', 'integer-valid', 'string-valid',
    'boolean-count', 'float-count', 'string-count', 'top-errors', 'row-errors',
    'bad-errors', 'bad-warnings', 'contradictory-success', 'bad-rows', 'bad-row',
    'root-null', 'root-list', 'missing-report', 'invalid-json',
])
@pytest.mark.parametrize('status', [True, 2])
def test_invalid_empty_incomplete_or_malformed_evidence_never_verifies(
    upstream_fixture, status, mutation
):
    upstream_fixture.update(status=status, mutation=mutation)
    with pytest.raises(SystemExit, match='evidence rejected'):
        gate.verify(PIN)


@pytest.mark.parametrize('status', [False, None, 0, 1, '2', 2.0])
def test_aggregate_failure_or_unsupported_sentinel_overrides_good_looking_report(
    upstream_fixture, status
):
    upstream_fixture['status'] = status
    with pytest.raises(SystemExit, match='type checker failed'):
        gate.verify(PIN)
