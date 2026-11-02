"""Tests for ``metadata_archiver.MetadataArchiver`` — schema and append behaviour."""

import json
import re

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


def test_archive_metadata_appends_a_record_with_the_documented_schema(tmp_path):
    archiver = MetadataArchiver(str(tmp_path / "archived"))

    archiver.archive_metadata(
        "downloaded_documents/proceedings.pdf",
        "https://web3.isss.org/proceedings/proceedings.pdf",
        "pdf",
    )

    records = json.loads((tmp_path / "archived" / "metadata.json").read_text())
    assert len(records) == 1
    record = records[0]
    assert record["document_name"] == "proceedings.pdf"
    assert record["document_path"] == "downloaded_documents/proceedings.pdf"
    assert record["source_url"] == "https://web3.isss.org/proceedings/proceedings.pdf"
    assert record["document_type"] == "pdf"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", record["download_date"])


def test_archive_metadata_appends_without_losing_earlier_records(tmp_path):
    archiver = MetadataArchiver(str(tmp_path / "archived"))

    archiver.archive_metadata("downloaded_documents/a.pdf", "https://web3.isss.org/a.pdf", "pdf")
    archiver.archive_metadata("downloaded_documents/b.docx", "https://web3.isss.org/b.docx", "docx")

    records = json.loads((tmp_path / "archived" / "metadata.json").read_text())
    assert [record["document_name"] for record in records] == ["a.pdf", "b.docx"]
