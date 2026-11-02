"""File conversion pipeline stage: documents converted to text and page images.

Stage 4 of the pipeline. ``FileConverter`` reads every supported document in
``download_path`` (the stage-2 download directory) and writes two uniform
artifacts per document under ``converted_path``:

- ``text/<name>.txt`` — the document's text. For PDFs this is the embedded
  text layer, page by page in page order, with a form feed (``\\f``) between
  pages; a page whose text layer is empty (an image-only scan) is rendered and
  read with Tesseract instead, so the text artifact is complete for scanned
  documents too.
- ``pages/<name>/page-NNNN.png`` — one PNG per PDF page, rendered at 150 DPI,
  numbered from 1 and zero-padded to four digits, so later stages address
  pages deterministically.

Artifact rules, applied uniformly so every downstream stage reads one shape:

- PDFs produce both artifacts. Office documents (``.docx``, ``.pptx``,
  ``.xlsx``) produce the text artifact only: paginating and rasterizing them
  needs an external office suite, which this stage does not depend on.
- The text artifact is written for every page, not only for image-only pages.
- OCR needs the system Tesseract binary, exactly as in stage 5.
- Re-running overwrites the artifacts, and a document that cannot be read is
  reported and skipped without stopping the run.

Runnable standalone: ``python file_converter.py``.
"""

import os

import openpyxl
import pymupdf
import pytesseract
from docx import Document as DocxDocument
from PIL import Image
from pptx import Presentation

#: Document types downloaded by stage 2 and converted here.
DOCUMENT_EXTENSIONS = ('.pdf', '.docx', '.pptx', '.xlsx')
#: Resolution of the rendered page images, in dots per inch.
PDF_DPI = 150
#: Separator written between the text of two pages.
PAGE_SEPARATOR = '\f'


class FileConverter:
    """Converts downloaded documents into text files and page images."""

    def __init__(self, download_path, converted_path):
        """Initializes the FileConverter with input and output paths.

        Args:
            download_path (str): Directory holding the downloaded documents.
            converted_path (str): Directory where the converted artifacts are
                written, as ``text/`` and ``pages/`` subdirectories.
        """
        self.download_path = download_path
        self.converted_path = converted_path
        self.text_path = os.path.join(converted_path, 'text')
        self.pages_path = os.path.join(converted_path, 'pages')
        os.makedirs(self.text_path, exist_ok=True)
        os.makedirs(self.pages_path, exist_ok=True)
        self._text_names = {}

    def convert_files(self):
        """Converts every supported document in the download directory.

        Returns:
            list[dict]: One record per converted document, with the document
            name, its page-image count and the length of the extracted text.
            Documents that could not be read are left out.
        """
        converted = []
        for filename in sorted(os.listdir(self.download_path)):
            if not filename.lower().endswith(DOCUMENT_EXTENSIONS):
                continue
            document_path = os.path.join(self.download_path, filename)
            record = self.convert_document(document_path)
            if record is not None:
                converted.append(record)
        print(f'Converted {len(converted)} document(s) from {self.download_path}.')
        return converted

    def convert_document(self, document_path):
        """Converts one document and writes its text file and page images.

        Args:
            document_path (str): Path of the document to convert.

        Returns:
            dict | None: The conversion record for the document, or ``None``
            when it could not be read; the failure is reported and the
            remaining documents are still converted.
        """
        name = os.path.basename(document_path)
        try:
            if name.lower().endswith('.pdf'):
                text, page_count = self._convert_pdf(document_path)
            else:
                text, page_count = self._convert_office(document_path), 0
        except Exception as error:  # one unreadable document must not stop the run
            print(f'Skipped {name}: {error}')
            return None
        text_name = self._register_text_name(name)
        with open(os.path.join(self.text_path, text_name), 'w', encoding='utf-8') as text_file:
            text_file.write(text)
        print(f'Converted {name} to {text_name} ({page_count} page image(s)).')
        return {'document_name': name, 'page_count': page_count, 'characters': len(text)}

    def _register_text_name(self, name):
        """Returns the text file name for a document, disambiguating collisions.

        Two documents can share a base name with different extensions
        (``programme.pdf`` and ``programme.docx``). The first in the sorted
        conversion order keeps ``<base>.txt``; a later one is written as
        ``<base>-<extension>.txt`` instead of overwriting it.

        Args:
            name (str): File name of the converted document.

        Returns:
            str: File name of its text artifact.
        """
        base, extension = os.path.splitext(name)
        text_name = f'{base}.txt'
        if self._text_names.get(text_name) not in (None, name):
            text_name = f'{base}-{extension.lstrip(".").lower()}.txt'
        self._text_names[text_name] = name
        return text_name

    def _convert_pdf(self, document_path):
        """Extracts the text of every page and renders one PNG per page.

        Args:
            document_path (str): Path of the PDF document.

        Returns:
            tuple[str, int]: The document text and its page-image count.
        """
        base = os.path.splitext(os.path.basename(document_path))[0]
        pages_path = os.path.join(self.pages_path, base)
        os.makedirs(pages_path, exist_ok=True)
        page_texts = []
        with pymupdf.open(document_path) as document:
            for page_number, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(dpi=PDF_DPI)
                pixmap.save(os.path.join(pages_path, f'page-{page_number:04d}.png'))
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
