"""Batch archival of qualified acquisition receipts; historical records stay intact."""

import json
from pathlib import Path

from document_downloader import DownloadReceipt
from pipeline_artifacts import atomic_json


class MetadataArchiver:
    def __init__(self, archive_path):
        self.metadata_file = Path(archive_path) / 'metadata.json'
        if not self.metadata_file.exists():
            atomic_json(self.metadata_file, [])

    def archive_receipts(self, receipts):
        """Validate the entire batch before one atomic archive publication."""
        receipts = list(receipts)
        for receipt in receipts:
            if not isinstance(receipt, DownloadReceipt):
                raise ValueError('metadata requires a DownloadReceipt')
            receipt.validate()
        existing = json.loads(self.metadata_file.read_text(encoding='utf-8'))
        if not isinstance(existing, list) or any(not isinstance(row, dict) for row in existing):
            raise ValueError('metadata archive must be an array of records')
        identity_fields = ('source_url', 'sha256', 'size', 'download_date', 'document_name')
        identities = {
            tuple(row.get(field) for field in identity_fields)
            for row in existing
            if all(field in row for field in identity_fields)
        }
        added = []
        for receipt in receipts:
            row = {
                'document_name': receipt.document_name,
                'document_path': receipt.document_path,
                'source_url': receipt.source_url,
                'document_type': Path(receipt.document_name).suffix.lstrip('.').lower(),
                'download_date': receipt.download_date,
                'sha256': receipt.sha256,
                'size': receipt.size,
                'final_url': receipt.final_url,
            }
            identity = tuple(row[field] for field in identity_fields)
            if identity not in identities:
                added.append(row)
                identities.add(identity)
        if added:
            atomic_json(self.metadata_file, existing + added)
        return added


if __name__ == '__main__':
    receipts = []
    for path in sorted(Path('downloaded_documents/.receipts').glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.pop('schema', None) != 'isss-download/v1':
            raise ValueError(f'invalid receipt: {path}')
        receipts.append(DownloadReceipt(**data))
    MetadataArchiver('archived_documents').archive_receipts(receipts)
