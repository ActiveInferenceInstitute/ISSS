"""Tests for ``metadata_archiver.MetadataArchiver`` — schema and append behaviour."""

import json
from dataclasses import replace

import pytest

import pipeline_artifacts
from metadata_archiver import MetadataArchiver


def test_constructor_creates_the_archive_and_an_empty_metadata_file(tmp_path):
    archive = tmp_path / "archived_documents"

    MetadataArchiver(str(archive))

    assert archive.is_dir()
    assert json.loads((archive / "metadata.json").read_text()) == []


def test_constructor_keeps_existing_metadata(tmp_path):
    archive = tmp_path / "archived_documents"
    archive.mkdir()
    (archive / "metadata.json").write_text(json.dumps([{"document_name": "kept.pdf"}]))

    MetadataArchiver(str(archive))

    assert json.loads((archive / "metadata.json").read_text()) == [{"document_name": "kept.pdf"}]


def test_archive_records_actual_receipt_identity_and_acquisition_time(tmp_path, receipt_factory):
    receipt = receipt_factory('proceedings.pdf', b'qualified bytes')
    archive = tmp_path / 'archived'
    MetadataArchiver(archive).archive_receipts([receipt])
    rows = json.loads((archive / 'metadata.json').read_text())
    assert rows == [{
        'document_name': 'proceedings.pdf',
        'document_path': receipt.document_path,
        'source_url': 'https://web3.isss.org/proceedings.pdf',
        'final_url': 'https://web3.isss.org/proceedings.pdf',
        'document_type': 'pdf',
        'download_date': '2020-01-02T03:04:05+00:00',
        'sha256': receipt.sha256,
        'size': len(b'qualified bytes'),
    }]


def test_batch_preserves_history_order_and_deduplicates_cached_receipts(tmp_path, receipt_factory):
    first = receipt_factory('a.pdf', b'first')
    second = receipt_factory('b.docx', b'second')
    archive = tmp_path / 'archived'
    archiver = MetadataArchiver(archive)
    historical = {'document_name': 'legacy.pdf', 'download_date': 'historical', 'custom': [1, 2]}
    (archive / 'metadata.json').write_text(json.dumps([historical]))
    archiver.archive_receipts([first, second])
    before = (archive / 'metadata.json').read_bytes()
    assert archiver.archive_receipts([replace(first, cached=True), replace(second, cached=True)]) == []
    assert (archive / 'metadata.json').read_bytes() == before
    rows = json.loads(before)
    assert rows[0] == historical
    assert [row['document_name'] for row in rows] == ['legacy.pdf', 'a.pdf', 'b.docx']
    assert rows[1]['download_date'] == first.download_date


def test_invalid_receipt_aborts_entire_batch_without_partial_metadata(tmp_path, receipt_factory):
    good = receipt_factory('good.pdf', b'good')
    bad = receipt_factory('bad.pdf', b'original')
    archive = tmp_path / 'archived'
    archiver = MetadataArchiver(archive)
    before = (archive / 'metadata.json').read_bytes()
    (tmp_path / 'downloaded_documents' / 'bad.pdf').write_bytes(b'corrupted')
    with pytest.raises(RuntimeError, match='content'):
        archiver.archive_receipts([good, bad])
    assert (archive / 'metadata.json').read_bytes() == before


def test_atomic_archive_failure_preserves_previous_complete_bytes(
    tmp_path, receipt_factory, monkeypatch
):
    archiver = MetadataArchiver(tmp_path / 'archived')
    archiver.archive_receipts([receipt_factory('first.pdf')])
    before = archiver.metadata_file.read_bytes()
    second = receipt_factory('second.pdf')

    def refuse_replace(source, destination):
        raise OSError('publication refused')

    monkeypatch.setattr(pipeline_artifacts.os, 'replace', refuse_replace)
    with pytest.raises(OSError, match='publication refused'):
        archiver.archive_receipts([second])
    assert archiver.metadata_file.read_bytes() == before
    assert not list(archiver.metadata_file.parent.glob('.metadata.json-*'))


def test_raw_path_cannot_be_archived_as_a_successful_download(tmp_path):
    archiver = MetadataArchiver(tmp_path / 'archive')
    with pytest.raises(ValueError, match='DownloadReceipt'):
        archiver.archive_receipts(['unqualified.pdf'])
    assert json.loads(archiver.metadata_file.read_text()) == []
