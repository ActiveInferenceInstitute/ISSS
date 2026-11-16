"""Consumer-visible atomicity, provenance and no-legacy-discovery regressions."""

import json

import pytest

from pipeline_artifacts import ArtifactStore, atomic_json


def test_changed_source_excludes_previous_complete_set_without_deleting_it(publish_conversion):
    root, record = publish_conversion('paper.pdf', 'original text')
    artifact = root / record['text_file']
    source = record['source']['path']
    before = artifact.read_bytes()
    with open(source, 'wb') as handle:
        handle.write(b'different source bytes')
    store = ArtifactStore(root, 'conversion')
    assert store.active_documents() == []
    assert 'source content changed' in store.failures['paper.pdf']
    assert artifact.read_bytes() == before


def test_tampered_artifact_is_not_admitted_even_if_source_is_unchanged(publish_conversion):
    root, record = publish_conversion('paper.pdf', 'complete text')
    artifact = root / record['text_file']
    artifact.write_text('tampered text')
    store = ArtifactStore(root, 'conversion')
    assert store.active_documents() == []
    assert 'artifact content changed' in store.failures['paper.pdf']
    assert artifact.read_text() == 'tampered text'


def test_legacy_files_are_preserved_but_not_discovered(tmp_path):
    (tmp_path / 'text').mkdir()
    (tmp_path / 'text' / 'legacy.txt').write_text('legacy evidence')
    store = ArtifactStore(tmp_path, 'conversion')
    assert store.active_documents() == []
    store.commit()
    assert json.loads((tmp_path / 'active.json').read_text())['documents'] == []
    assert (tmp_path / 'text' / 'legacy.txt').read_text() == 'legacy evidence'


def test_failed_staging_cleans_only_owned_unpublished_directory(tmp_path):
    root = tmp_path / 'converted'
    root.mkdir()
    sentinel = root / 'unowned.bin'
    sentinel.write_bytes(b'preserved')
    store = ArtifactStore(root, 'conversion')
    with pytest.raises(RuntimeError, match='conversion failed'):
        with store.stage() as (_generation, staged):
            (staged / 'partial.png').write_bytes(b'partial')
            raise RuntimeError('conversion failed')
    assert sentinel.read_bytes() == b'preserved'
    assert not list((root / '.generations').glob('.staging-*'))
    assert not (root / 'active.json').exists()


def test_symlink_artifact_is_rejected_without_touching_target(tmp_path, publish_conversion):
    root, record = publish_conversion('paper.pdf', 'qualified')
    target = tmp_path / 'valuable.txt'
    target.write_text('unowned bytes')
    artifact = root / record['text_file']
    artifact.unlink()
    artifact.symlink_to(target)
    store = ArtifactStore(root, 'conversion')
    assert store.active_documents() == []
    assert target.read_text() == 'unowned bytes'


def test_malformed_selection_does_not_fall_back_to_old_directory_scan(publish_conversion):
    root, record = publish_conversion('paper.pdf', 'historical')
    (root / 'active.json').write_text('{"schema":"unknown","documents":[]}')
    with pytest.raises(ValueError, match='manifest'):
        ArtifactStore(root, 'conversion')
    assert (root / record['text_file']).read_text() == 'historical'


def test_serialization_failure_preserves_previous_complete_json(tmp_path):
    destination = tmp_path / 'metadata.json'
    destination.write_bytes(b'[{"historical":true}]\n')
    before = destination.read_bytes()
    with pytest.raises(TypeError):
        atomic_json(destination, [{'unserializable': {1, 2}}])
    assert destination.read_bytes() == before
    assert not list(tmp_path.glob('.metadata.json-*'))


@pytest.mark.parametrize('mutation', ['kind', 'documents-shape', 'duplicate-document'])
def test_malformed_manifest_refuses_admission_without_rewriting_evidence(
    publish_conversion, mutation
):
    root, record = publish_conversion('paper.pdf', 'historical')
    manifest = root / 'active.json'
    data = json.loads(manifest.read_text())
    if mutation == 'kind':
        data['kind'] = 'another-producer'
    elif mutation == 'documents-shape':
        data['documents'] = None
    else:
        data['documents'].append(dict(data['documents'][0]))
    manifest.write_text(json.dumps(data))
    before = manifest.read_bytes()
    with pytest.raises(ValueError):
        ArtifactStore(root, 'conversion')
    assert manifest.read_bytes() == before
    assert (root / record['text_file']).read_text() == 'historical'


@pytest.mark.parametrize('relative', ['../outside.txt', '/outside.txt', '.generations/wrong/file.txt'])
def test_declared_artifact_cannot_escape_its_generation(publish_conversion, relative):
    root, record = publish_conversion('paper.pdf', 'qualified')
    altered = dict(record)
    altered['files'] = {relative: {'sha256': '0' * 64, 'size': 0}}
    with pytest.raises(ValueError, match='outside'):
        ArtifactStore(root, 'conversion').resolve(altered, relative)
    assert (root / record['text_file']).read_text() == 'qualified'


def test_json_output_symlink_cannot_overwrite_valuable_target(tmp_path):
    target = tmp_path / 'valuable.json'
    target.write_text('[\"historical\"]')
    output = tmp_path / 'metadata.json'
    output.symlink_to(target)
    with pytest.raises(ValueError, match='symlink'):
        atomic_json(output, [])
    assert target.read_text() == '[\"historical\"]'
