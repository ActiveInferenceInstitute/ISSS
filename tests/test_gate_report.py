"""Real report rendering/checking with isolated measurement/acquisition boundaries."""

import importlib
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def report_module(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    module = importlib.import_module('gate_report')
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'docs' / '_generated').mkdir(parents=True)
    (tmp_path / '.github' / 'workflows').mkdir(parents=True)
    (tmp_path / 'run.sh').write_text(
        'case "$1" in\n' + ''.join(
            f'  {name}) : ;;\n' for name in ('lint', 'test', 'test-cov', 'docs', 'gnn', 'ci', 'timings', 'list')
        ) + 'esac\n'
    )
    module.WORKFLOW_PATH.write_text(
        'jobs:\n  gate:\n    name: gate\n    python-version: "3.12"\n'
        '    steps:\n      - run: ./run.sh docs\n      - uses: owner/action@012345\n'
    )
    module.PIN_PATH.write_text(json.dumps({
        'schema': 'gnn-importer-pin/v1',
        'repository': 'ActiveInferenceInstitute/Generalized_Notation_Notation',
        'revision': '8f293d9ba810e6eda5c09842d9c7ed9ffa5f92c1',
        'tag': 'v5.0.3', 'recorded': '2026-11-12',
    }))
    return module


def _historical(module):
    return {
        'schema': module.SCHEMA,
        'recorded': '2026-11-12',
        'host': {
            'platform': 'macOS-27.0.1-arm64-arm-64bit-Mach-O',
            'python': '3.13.18', 'cpus': '18',
        },
        'arms': [
            {'name': name, 'after_command': after, 'after_seconds': 1.56 if name == 'gnn' else 1.0}
            for name, _, after in module.ARMS
        ],
        'suite': {'tests': 81, 'passed': 81, 'coverage_percent': 100.0},
    }


def _save(module, data):
    module.DATA_PATH.write_text(json.dumps(data))
    module.DOC_PATH.write_text(module.render(data))


def _fake_measurements(module, monkeypatch, *, full=False, fail=None, bad_summary=False):
    allowed = {
        (sys.executable, '-m', 'ruff', 'check', '.'),
        (sys.executable, '-m', 'pytest'),
        ('./run.sh', 'lint'), ('./run.sh', 'test'),
        ('./run.sh', 'test-cov'),
        ('./run.sh', 'docs', '--output-dir', str(module.DATA_PATH.parent.resolve())),
    }
    if full:
        allowed.add(('./run.sh', 'gnn'))

    def timed(command):
        command = tuple(command)
        if command not in allowed:
            raise AssertionError(f'offline measurement attempted forbidden acquisition: {command}')
        if command[:2] == ('./run.sh', fail):
            raise SystemExit('observed offline arm failure')
        if command == ('./run.sh', 'test-cov'):
            return 0.25, 'missing summaries' if bad_summary else 'Total coverage: 97.50%\n83 passed\n'
        return (2.5 if command == ('./run.sh', 'gnn') else 0.25), ''

    monkeypatch.setattr(module, 'timed', timed)
    monkeypatch.setattr(module, 'collected_tests', lambda: 83)


def test_offline_capture_keeps_original_gnn_date_host_and_duration(report_module, monkeypatch):
    module = report_module
    previous = _historical(module)
    _save(module, previous)
    _fake_measurements(module, monkeypatch)
    assert module.main(['--capture', '--offline']) == 0
    current = json.loads(module.DATA_PATH.read_text())
    gnn = next(arm for arm in current['arms'] if arm['name'] == 'gnn')
    assert gnn['status'] == 'unmeasured'
    assert 'after_seconds' not in gnn
    assert current['suite'] == {'tests': 83, 'passed': 83, 'coverage_percent': 97.5}
    assert current['historical_gnn'] == [{
        'recorded': previous['recorded'], 'host': previous['host'],
        'observation': next(arm for arm in previous['arms'] if arm['name'] == 'gnn'),
    }]
    assert current['history'][0] == previous
    page = module.DOC_PATH.read_text()
    current_row = next(line for line in page.splitlines() if line.startswith('| `gnn` |'))
    assert 'unmeasured' in current_row
    assert '1.56' not in current_row
    assert '2026-11-12' in page and previous['host']['platform'] in page
    assert 'Historical GNN observations' in page
    assert module.check() == 0


def test_repeated_offline_capture_does_not_redate_nest_or_erase_gnn_history(
    report_module, monkeypatch
):
    module = report_module
    _save(module, _historical(module))
    _fake_measurements(module, monkeypatch)
    module.capture(offline=True)
    first = json.loads(module.DATA_PATH.read_text())
    module.capture(offline=True)
    second = json.loads(module.DATA_PATH.read_text())
    assert second['historical_gnn'] == first['historical_gnn']
    assert all('history' not in snapshot for snapshot in second['history'])
    assert next(arm for arm in second['arms'] if arm['name'] == 'gnn')['status'] == 'unmeasured'


def test_absent_historical_gnn_remains_unmeasured_without_invented_zero(report_module, monkeypatch):
    module = report_module
    previous = _historical(module)
    previous['arms'] = [arm for arm in previous['arms'] if arm['name'] != 'gnn']
    _save(module, previous)
    _fake_measurements(module, monkeypatch)
    module.capture(offline=True)
    current = json.loads(module.DATA_PATH.read_text())
    assert current['historical_gnn'] == []
    assert 'No historical GNN timing is recorded.' in module.DOC_PATH.read_text()
    assert module.check() == 0


def test_current_collection_mismatch_is_not_hidden_by_page_consistency(
    report_module, monkeypatch, capsys
):
    module = report_module
    _save(module, _historical(module))
    monkeypatch.setattr(module, 'collected_tests', lambda: 82)
    assert module.check() == 1
    output = capsys.readouterr().out
    assert 'pytest collects 82' in output
    assert 'records 81' in output


def test_missing_offline_arm_still_fails_but_pending_docs_bootstrap_is_allowed(
    report_module, monkeypatch, capsys
):
    module = report_module
    _save(module, _historical(module))
    _fake_measurements(module, monkeypatch)
    module.capture(offline=True)
    current = json.loads(module.DATA_PATH.read_text())
    current['arms'] = [arm for arm in current['arms'] if arm['name'] != 'docs']
    _save(module, current)
    assert module.check() == 0
    current['arms'] = [arm for arm in current['arms'] if arm['name'] != 'lint']
    _save(module, current)
    assert module.check() == 1
    assert 'no measurement' in capsys.readouterr().out


def test_arbitrary_unmeasured_offline_arm_is_not_accepted(report_module, monkeypatch):
    module = report_module
    _save(module, _historical(module))
    _fake_measurements(module, monkeypatch)
    module.capture(offline=True)
    current = json.loads(module.DATA_PATH.read_text())
    lint = next(arm for arm in current['arms'] if arm['name'] == 'lint')
    lint['status'] = 'unmeasured'
    lint.pop('after_seconds')
    module.DATA_PATH.write_text(json.dumps(current))
    with pytest.raises(SystemExit, match='offline GNN'):
        module.check()


def test_render_mismatch_and_missing_dispatch_remain_independent_failures(
    report_module, monkeypatch, capsys
):
    module = report_module
    data = _historical(module)
    _save(module, data)
    monkeypatch.setattr(module, 'collected_tests', lambda: 81)
    module.DOC_PATH.write_text('stale page')
    assert module.check() == 1
    assert 'is stale' in capsys.readouterr().out
    _save(module, data)
    runner = Path('run.sh')
    runner.write_text(runner.read_text().replace('  docs) : ;;\n', ''))
    assert module.check() == 1
    assert 'not dispatched' in capsys.readouterr().out


@pytest.mark.parametrize(('fail', 'bad_summary'), [('test', False), (None, True)])
def test_failed_measurements_do_not_replace_previous_evidence(
    report_module, monkeypatch, fail, bad_summary
):
    module = report_module
    _save(module, _historical(module))
    previous_data = module.DATA_PATH.read_bytes()
    previous_page = module.DOC_PATH.read_bytes()
    _fake_measurements(module, monkeypatch, fail=fail, bad_summary=bad_summary)
    with pytest.raises(SystemExit):
        module.capture(offline=True)
    assert module.DATA_PATH.read_bytes() == previous_data
    assert module.DOC_PATH.read_bytes() == previous_page


def test_full_capture_still_records_gnn_instead_of_silently_skipping_it(report_module, monkeypatch):
    module = report_module
    _save(module, _historical(module))
    _fake_measurements(module, monkeypatch, full=True)
    module.capture()
    current = json.loads(module.DATA_PATH.read_text())
    gnn = next(arm for arm in current['arms'] if arm['name'] == 'gnn')
    assert gnn['status'] == 'measured'
    assert gnn['after_seconds'] == 2.5
    assert current['historical_gnn'][0]['observation']['after_seconds'] == 1.56


def test_offline_flag_cannot_be_misapplied_to_check_mode(report_module):
    with pytest.raises(SystemExit) as error:
        report_module.main(['--check', '--offline'])
    assert error.value.code == 2


def test_malformed_historical_provenance_fails_before_any_new_measurement(
    report_module, monkeypatch
):
    module = report_module
    data = _historical(module)
    data['historical_gnn'] = [{
        'recorded': '2020-01-02', 'host': {},
        'observation': {'name': 'gnn', 'after_seconds': 1.56},
    }]
    module.DATA_PATH.write_text(json.dumps(data))
    before = module.DATA_PATH.read_bytes()

    def forbidden_measurement(command):
        raise AssertionError('malformed historical evidence must fail before measurement')

    monkeypatch.setattr(module, 'timed', forbidden_measurement)
    with pytest.raises(SystemExit, match='invalid timing evidence'):
        module.capture(offline=True)
    assert module.DATA_PATH.read_bytes() == before
