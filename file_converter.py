"""File conversion pipeline stage: documents converted to text and page images.

Stage 4 converts explicitly selected inputs into immutable generations. ``active.json``
is the only discovery contract: each successful record names its source hash,
text file and ordered page files below ``.generations/<id>/``. Legacy flat output,
retired generations and incomplete staging sets are never active by directory scan.

Artifact rules, applied uniformly so every downstream stage reads one shape:

- PDFs produce both artifacts. Office documents (``.docx``, ``.pptx``,
  ``.xlsx``) produce the text artifact only: paginating and rasterizing them
  needs an external office suite, which this stage does not depend on.
- The text artifact is written for every page, not only for image-only pages.
- OCR needs the system Tesseract binary, exactly as in stage 5.
- Re-running atomically selects complete new sets without deleting historical
  bytes. Failed documents are explicitly excluded from the active manifest.

Runnable standalone: ``python file_converter.py``.
"""

import os
from pathlib import Path

import openpyxl
import pymupdf
import pytesseract
from docx import Document as DocxDocument
from PIL import Image
from pptx import Presentation

from pipeline_artifacts import ArtifactStore, file_identity

#: Document types downloaded by stage 2 and converted here.
DOCUMENT_EXTENSIONS = ('.pdf', '.docx', '.pptx', '.xlsx')
#: Resolution of the rendered page images, in dots per inch.
PDF_DPI = 150
#: Separator written between the text of two pages.
PAGE_SEPARATOR = '\f'


class FileConverter:
    """Converts downloaded documents into text files and page images."""

    def __init__(self, download_path, converted_path):
        self.download_path = Path(download_path).absolute()
        self.converted_path = Path(converted_path)
        self.store = ArtifactStore(converted_path, 'conversion')
        self._text_names = {
            Path(record['text_file']).name: name
            for name, record in self.store.documents.items()
        }

    def convert_files(self, document_paths=None):
        """Activate only this invocation's successful, explicitly selected inputs."""
        paths = (
            list(self.download_path.iterdir()) if document_paths is None
            else [Path(path).absolute() for path in document_paths]
        )
        paths = sorted(
            (path for path in paths if path.suffix.lower() in DOCUMENT_EXTENSIONS),
            key=lambda path: path.name,
        )
        names = [path.name for path in paths]
        if len(names) != len(set(names)):
            raise ValueError('duplicate source filenames in conversion selection')
        self.store.select(names)
        self._text_names = {
            text_name: name for text_name, name in self._text_names.items() if name in names
        }
        converted = []
        for path in paths:
            record = self._convert_document(path)
            if record is not None:
                converted.append(record)
        self.store.commit()
        print(f'Converted {len(converted)} document(s) from {self.download_path}.')
        return converted

    def convert_document(self, document_path):
        """Publish one complete document or deactivate its failed replacement."""
        record = self._convert_document(Path(document_path).absolute())
        self.store.commit()
        return record

    def _convert_document(self, path):
        name = path.name
        try:
            if path.parent.resolve() != self.download_path.resolve():
                raise ValueError('source is outside the selected download directory')
            source_identity = file_identity(path)
            text_name = self._register_text_name(name)
            with self.store.stage() as (generation, staged):
                pages = staged / 'pages'
                pages.mkdir()
                if path.suffix.lower() == '.pdf':
                    text, page_count = self._convert_pdf(path, pages)
                else:
                    text, page_count = self._convert_office(str(path)), 0
                text_directory = staged / 'text'
                text_directory.mkdir()
                (text_directory / text_name).write_text(text, encoding='utf-8')
                if file_identity(path) != source_identity:
                    raise ValueError('source changed during conversion')
                prefix = f'.generations/{generation}/'
                record = self.store.publish(staged, {
                    'document_name': name,
                    'generation': generation,
                    'source': {'path': str(path), **source_identity},
                    'text_file': prefix + 'text/' + text_name,
                    'page_files': [
                        prefix + f'pages/page-{number:04d}.png'
                        for number in range(1, page_count + 1)
                    ],
                    'page_count': page_count,
                    'characters': len(text),
                })
            print(f'Converted {name} to {text_name} ({page_count} page image(s)).')
            return record
        except Exception as error:  # Per-document errors preserve successful peers.
            self.store.fail(name, error)
            print(f'Skipped {name}: {error}')
            return None

    def _register_text_name(self, name):
        prior = self.store.documents.get(name)
        if prior is not None:
            return Path(prior['text_file']).name
        base, extension = os.path.splitext(name)
        candidate = f'{base}.txt'
        fallback = f'{base}-{extension.lstrip(".").lower()}'
        number = 1
        while self._text_names.get(candidate) not in (None, name):
            candidate = f'{fallback}{"" if number == 1 else f"-{number}"}.txt'
            number += 1
        self._text_names[candidate] = name
        return candidate

    def _convert_pdf(self, document_path, pages_path):
        """Render only into a private generation until every page and OCR succeeds."""
        page_texts = []
        with pymupdf.open(document_path) as document:
            for page_number, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(dpi=PDF_DPI)
                pixmap.save(str(pages_path / f'page-{page_number:04d}.png'))
                page_text = page.get_text().strip()
                if not page_text:
                    page_text = self._ocr_page(self._page_image(pixmap))
                page_texts.append(page_text)
        return PAGE_SEPARATOR.join(page_texts), len(page_texts)

    def _convert_office(self, document_path):
        """Extracts the text of a Word, PowerPoint or Excel document.

        Args:
            document_path (str): Path of the Office document.

        Returns:
            str: The extracted text, one paragraph, slide paragraph or
            spreadsheet row per line.
        """
        extension = os.path.splitext(document_path)[1].lower()
        if extension == '.docx':
            return self._text_from_docx(document_path)
        if extension == '.pptx':
            return self._text_from_pptx(document_path)
        if extension == '.xlsx':
            return self._text_from_xlsx(document_path)
        raise ValueError(f'unsupported document type: {extension}')

    @staticmethod
    def _text_from_docx(document_path):
        """Extracts paragraphs and table rows from a Word document."""
        document = DocxDocument(document_path)
        lines = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    lines.append(' | '.join(cells))
        return '\n'.join(lines)

    @staticmethod
    def _text_from_pptx(document_path):
        """Extracts the text of every shape on every slide."""
        presentation = Presentation(document_path)
        lines = []
        for slide in presentation.slides:
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                for paragraph in shape.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        lines.append(text)
        return '\n'.join(lines)

    @staticmethod
    def _text_from_xlsx(document_path):
        """Extracts the non-empty rows of every worksheet."""
        workbook = openpyxl.load_workbook(document_path, read_only=True, data_only=True)
        lines = []
        try:
            for sheet in workbook.worksheets:
                lines.append(f'[{sheet.title}]')
                for row in sheet.iter_rows(values_only=True):
                    cells = ['' if value is None else str(value) for value in row]
                    if any(cell.strip() for cell in cells):
                        lines.append(' | '.join(cells))
        finally:
            workbook.close()
        return '\n'.join(lines)

    @staticmethod
    def _page_image(pixmap):
        """Returns the rendered page as a Pillow image."""
        return Image.frombytes('RGB', (pixmap.width, pixmap.height), pixmap.samples)

    @staticmethod
    def _ocr_page(image):
        """Reads a rendered page with Tesseract.

        Args:
            image (PIL.Image.Image): The rendered page.

        Returns:
            str: The text read from the page.
        """
        return pytesseract.image_to_string(image).strip()


if __name__ == '__main__':
    file_converter = FileConverter('downloaded_documents', 'converted_documents')
    file_converter.convert_files()
    raise SystemExit(1 if file_converter.store.failures else 0)
