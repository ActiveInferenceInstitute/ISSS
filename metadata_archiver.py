import os
import json
from datetime import datetime

class MetadataArchiver:
    def __init__(self, archive_path):
        """Initializes the MetadataArchiver with a specified archive path.
        
        Args:
            archive_path (str): The path where the archive and metadata file will be stored.
        """
        self.archive_path = archive_path
        # Ensure the archive directory exists
        os.makedirs(archive_path, exist_ok=True)
        self.metadata_file = os.path.join(archive_path, 'metadata.json')
        # Initialize an empty metadata file if it does not exist
        if not os.path.isfile(self.metadata_file):
            with open(self.metadata_file, 'w') as file:
                json.dump([], file)

    def archive_metadata(self, document_path, url, document_type):
        """Archives metadata for a given document.
        
        Args:
            document_path (str): The path to the document being archived.
            url (str): The source URL of the document.
            document_type (str): The type of the document (e.g., pdf, docx).
        """
        metadata = {
            'document_name': os.path.basename(document_path),
            'document_path': document_path,
            'source_url': url,
            'document_type': document_type,
            'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        # Safely read and update existing metadata
        with open(self.metadata_file, 'r+') as file:
            existing_metadata = json.load(file)
            existing_metadata.append(metadata)
            file.seek(0)  # Rewind to the start of the file
            json.dump(existing_metadata, file, indent=4)
            file.truncate()  # Remove any remaining parts of the old data

if __name__ == '__main__':
    # Demonstration of usage
    archiver = MetadataArchiver('archived_documents')
    document_path = 'downloaded_documents/example_document.pdf'
    url = 'http://example.com/example_document.pdf'
    document_type = 'pdf'
    archiver.archive_metadata(document_path, url, document_type)
