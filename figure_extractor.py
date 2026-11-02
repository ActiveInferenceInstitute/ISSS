"""Figure extraction pipeline stage: figures and caption candidates from pages.

Stage 6 of the pipeline. ``FigureExtractor`` reads the page images written by
stage 4 (``pages/<document>/page-NNNN.png``) and, for every page, writes each
detected figure as a PNG named ``<document>-fig-NNN.png`` into the figure
output directory, together with a ``figures.json`` metadata file.

Detection runs on the rendered page, so it needs no source-document layout:

- The page is binarized (a pixel is ink when its grayscale value is below
  ``INK_THRESHOLD``) and connected components of ink are built with a
  run-length sweep, then merged when their boxes are within ``MERGE_DISTANCE``
  pixels of each other.
- A component becomes a candidate when both sides of its bounding box are at
  least ``MIN_FIGURE_SIDE`` pixels, its box covers at least
  ``MIN_FIGURE_AREA_RATIO`` of the page, and it covers no more than
  ``MAX_FIGURE_AREA_RATIO``: text lines are too thin and a page-sized region is
  a scan of the whole page rather than a figure. Page-sized regions are counted
  in the report, not cropped.
- A candidate whose box is covered by at least ``TEXT_COVERAGE_LIMIT`` of the
  word boxes Tesseract reports for the page is text, not a figure, and is
  counted in the report instead of being cropped. Dense paragraph blocks pass
  the size and area tests, and on real proceedings pages they carry 0.5-0.6 of
  their box covered by recognized words, while figures carry 0.06-0.18, so the
  coverage test is what separates the two.

Each figure keeps its caption candidate:

- The word boxes are grouped into blocks by the block, paragraph and line
  numbers Tesseract reports, reusing the same page read as the coverage test.
- The caption candidate is the text block nearest to the figure box, measured
  as the vertical gap for blocks that overlap the figure horizontally, with
  blocks below the figure preferred over blocks above it.
- A candidate is only accepted within ``CAPTION_MAX_GAP`` pixels; when nothing
  is close enough the figure is still written and its metadata records
  ``caption_candidate: null``, so an ambiguous case stays visible instead of
  being dropped.

Naming, ordering and re-runs are deterministic: documents and pages are
processed in sorted name and page order, figure numbers are three digits
starting at ``fig-001`` and continue across the pages of one document, and
artifacts overwrite earlier runs.

Runnable standalone: ``python figure_extractor.py``.
"""

import json
import os

import pytesseract
from PIL import Image

#: A pixel counts as ink when its grayscale value is below this threshold.
INK_THRESHOLD = 200
#: Component boxes closer than this many pixels are merged into one figure.
MERGE_DISTANCE = 8
#: Smallest side of an accepted figure box, in pixels.
MIN_FIGURE_SIDE = 48
#: Smallest and largest page-area ratio of an accepted figure box.
MIN_FIGURE_AREA_RATIO = 0.03
MAX_FIGURE_AREA_RATIO = 0.80
#: A candidate whose box is covered this much by Tesseract word boxes is text.
TEXT_COVERAGE_LIMIT = 0.15
#: Largest distance between a figure box and its caption candidate, in pixels.
CAPTION_MAX_GAP = 120
#: Metadata file name and the page-image directory name written by stage 4.
REPORT_NAME = 'figures.json'
PAGES_DIRECTORY = 'pages'


class FigureExtractor:
    """Extracts the figures and caption candidates of converted page images."""

    def __init__(self, converted_path, figure_output_path):
        """Initializes the FigureExtractor with input and output paths.

        Args:
            converted_path (str): Directory written by stage 4, holding
                ``pages/<document>/page-NNNN.png``.
            figure_output_path (str): Directory where the figure images and
                ``figures.json`` are written.
        """
        self.converted_path = converted_path
        self.figure_output_path = figure_output_path
        self.pages_path = os.path.join(converted_path, PAGES_DIRECTORY)
        os.makedirs(figure_output_path, exist_ok=True)

    def extract_figures(self):
        """Extracts the figures of every converted document's page images.

        Returns:
            dict: The report that was written: one entry per document with its
            figures and the count of page-sized regions that were skipped.
        """
        documents = [self.extract_document(name) for name in sorted(self._document_names())]
        report = {
            'document_count': len(documents),
            'figure_count': sum(len(document['figures']) for document in documents),
            'documents': documents,
        }
        self._write_report(report)
        print(
            f'Extracted {report["figure_count"]} figure(s) from '
            f'{report["document_count"]} document(s) into {self.figure_output_path}.'
        )
        return report

    def extract_document(self, document_name):
        """Extracts the figures of one document's page images.

        Args:
            document_name (str): Name of the document as stage 4 writes it, that
                is the file name without its extension (``proceedings`` for
                ``proceedings.pdf``).

        Returns:
            dict: The document entry, with one record per extracted figure.
        """
        pages_directory = os.path.join(self.pages_path, document_name)
        figures = []
        skipped_page_sized = 0
        skipped_text = 0
        for page_name in sorted(os.listdir(pages_directory)):
            if not page_name.lower().endswith('.png'):
                continue
            page_figures, skipped = self.extract_page(
                os.path.join(pages_directory, page_name),
                document_name,
                _page_number(page_name),
                len(figures) + 1,
            )
            figures.extend(page_figures)
            skipped_page_sized += skipped['page_sized_regions']
            skipped_text += skipped['text_regions']
        return {
            'document_name': document_name,
            'figures': figures,
            'skipped_page_sized_regions': skipped_page_sized,
            'skipped_text_regions': skipped_text,
        }

    def extract_page(self, page_path, document_name, page_number, first_figure_number=1):
        """Extracts the figures of one page image.

        Args:
            page_path (str): Path of the page PNG.
            document_name (str): Name of the document the page belongs to.
            page_number (int): Page number, taken from the file name.
            first_figure_number (int): Figure number of the first figure found
                on this page, so numbering continues across a document.

        Returns:
            tuple[list[dict], dict]: The figure records with their file names,
            and the number of page-sized and text regions that were skipped.
        """
        with Image.open(page_path) as page_image:
            page = page_image.convert('L')
            boxes = _merge_nearby_boxes(_component_boxes(page.tobytes(), *page.size))
            page_size = page.size
        candidates, skipped_page_sized = _classify_components(boxes, page_size)
        figure_boxes = []
        skipped_text = 0
        caption_blocks = []
        if candidates:
            word_data = _ocr_page(page)
            word_boxes = _word_boxes(word_data)
            caption_blocks = _text_blocks(word_data)
            for box in candidates:
                if _text_coverage(box, word_boxes) >= TEXT_COVERAGE_LIMIT:
                    skipped_text += 1
                else:
                    figure_boxes.append(box)
        records = []
        for index, box in enumerate(figure_boxes):
            figure_name = f'{document_name}-fig-{first_figure_number + index:03d}.png'
            page.convert('RGB').crop(box).save(
                os.path.join(self.figure_output_path, figure_name)
            )
            caption = self._caption_candidate(box, caption_blocks)
            records.append(
                {
                    'figure': figure_name,
                    'page': page_number,
                    'page_image': os.path.basename(page_path),
                    'page_size': {'width': page_size[0], 'height': page_size[1]},
                    'bbox': _box_record(box),
                    'caption_candidate': caption['text'] if caption else None,
                    'caption_bbox': _box_record(caption['box']) if caption else None,
                }
            )
        return records, {'page_sized_regions': skipped_page_sized, 'text_regions': skipped_text}

    def _document_names(self):
        """Returns the document directories written by stage 4."""
        if not os.path.isdir(self.pages_path):
            return []
        return [
            name
            for name in os.listdir(self.pages_path)
            if os.path.isdir(os.path.join(self.pages_path, name))
        ]

    @staticmethod
    def _caption_candidate(figure_box, caption_blocks):
        """Returns the text block nearest to a figure box, within the gap limit.

        Blocks below the figure are preferred over blocks above it when both are
        equally close, and blocks that do not overlap the figure horizontally
        are ignored.

        Args:
            figure_box (tuple[int, int, int, int]): The figure's page box.
            caption_blocks (list[dict]): The page's text blocks.

        Returns:
            dict | None: The caption candidate with its text and box, or
            ``None`` when no block is close enough.
        """
        best = None
        for block in caption_blocks:
            if not _overlaps_horizontally(figure_box, block['box']):
                continue
            below = block['box'][1] - figure_box[3]
            above = figure_box[1] - block['box'][3]
            if below >= 0:
                distance, rank = below, 0
            elif above >= 0:
                distance, rank = above, 1
            else:
                continue
            if distance > CAPTION_MAX_GAP:
                continue
            candidate = (distance, rank, block)
            if best is None or candidate[:2] < best[:2]:
                best = candidate
        return best[2] if best else None

    def _write_report(self, report):
        """Writes the figure metadata file."""
        report_path = os.path.join(self.figure_output_path, REPORT_NAME)
        with open(report_path, 'w', encoding='utf-8') as report_file:
            json.dump(report, report_file, indent=2, ensure_ascii=False)


def _ocr_page(page):
    """Returns Tesseract's word data for one page.

    The stage needs the system Tesseract binary; one read of the page serves
    both the text-coverage test and the caption blocks.

    Args:
        page (PIL.Image.Image): The grayscale page image.

    Returns:
        dict: Tesseract's ``image_to_data`` dictionary.
    """
    return pytesseract.image_to_data(page, output_type=pytesseract.Output.DICT)


def _word_boxes(word_data):
    """Returns the box of every recognized word.

    Args:
        word_data (dict): Tesseract's ``image_to_data`` dictionary.

    Returns:
        list[tuple[int, int, int, int]]: Word boxes, right and bottom exclusive.
    """
    boxes = []
    for index, word in enumerate(word_data.get('text', [])):
        if not word.strip():
            continue
        left = word_data['left'][index]
        top = word_data['top'][index]
        boxes.append(
            (left, top, left + word_data['width'][index], top + word_data['height'][index])
        )
    return boxes


def _text_blocks(word_data):
    """Groups the recognized words into blocks, by Tesseract's own numbering.

    Args:
        word_data (dict): Tesseract's ``image_to_data`` dictionary.

    Returns:
        list[dict]: One entry per block, with its text and its box.
    """
    blocks = {}
    for index, word in enumerate(word_data.get('text', [])):
        if not word.strip():
            continue
        key = (word_data['block_num'][index], word_data['par_num'][index], word_data['line_num'][index])
        left = word_data['left'][index]
        top = word_data['top'][index]
        right = left + word_data['width'][index]
        bottom = top + word_data['height'][index]
        block = blocks.setdefault(key, {'words': [], 'box': [left, top, right, bottom]})
        block['words'].append(word)
        block['box'] = [
            min(block['box'][0], left),
            min(block['box'][1], top),
            max(block['box'][2], right),
            max(block['box'][3], bottom),
        ]
    return [
        {'text': ' '.join(block['words']), 'box': tuple(block['box'])}
        for _, block in sorted(blocks.items())
    ]


def _text_coverage(box, word_boxes):
    """Returns the fraction of a component box covered by recognized words.

    Args:
        box (tuple[int, int, int, int]): The component box.
        word_boxes (list[tuple[int, int, int, int]]): The page's word boxes.

    Returns:
        float: Covered area divided by the component area, capped at 1.0.
    """
    area = max(1, (box[2] - box[0]) * (box[3] - box[1]))
    covered = 0
    for other in word_boxes:
        overlap_x = max(0, min(box[2], other[2]) - max(box[0], other[0]))
        overlap_y = max(0, min(box[3], other[3]) - max(box[1], other[1]))
        covered += overlap_x * overlap_y
    return min(1.0, covered / area)


def _classify_components(boxes, page_size):
    """Splits component boxes into figures and page-sized regions.

    Args:
        boxes (list[tuple[int, int, int, int]]): Merged component boxes.
        page_size (tuple[int, int]): Page width and height in pixels.

    Returns:
        tuple[list[tuple[int, int, int, int]], int]: The figure boxes in
        reading order, and the number of page-sized regions.
    """
    page_area = page_size[0] * page_size[1]
    figures = []
    page_sized = 0
    for box in boxes:
        box_width = box[2] - box[0]
        box_height = box[3] - box[1]
        ratio = (box_width * box_height) / page_area
        if ratio > MAX_FIGURE_AREA_RATIO:
            page_sized += 1
            continue
        if min(box_width, box_height) < MIN_FIGURE_SIDE:
            continue
        if ratio < MIN_FIGURE_AREA_RATIO:
            continue
        figures.append(box)
    return sorted(figures, key=lambda box: (box[1], box[0])), page_sized


def _component_boxes(pixels, width, height):
    """Builds connected components of ink pixels with a run-length sweep.

    Args:
        pixels (bytes): The grayscale page pixels, row by row.
        width (int): Page width in pixels.
        height (int): Page height in pixels.

    Returns:
        list[tuple[int, int, int, int]]: One box per component, with the right
        and bottom edges exclusive.
    """
    parents = {}

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first, second):
        first_root, second_root = find(first), find(second)
        if first_root != second_root:
            parents[second_root] = first_root

    components = {}
    previous_runs = []
    run_index = 0
    for y in range(height):
        row_start = y * width
        runs = []
        x = 0
        while x < width:
            if pixels[row_start + x] < INK_THRESHOLD:
                start = x
                while x < width and pixels[row_start + x] < INK_THRESHOLD:
                    x += 1
                parents[run_index] = run_index
                # Boxes are pixel-exclusive on the right and bottom edges, the
                # convention ``PIL.Image.crop`` uses, so a box crops exactly as
                # the metadata reports it.
                components[run_index] = [start, y, x, y + 1]
                for previous_index, previous_start, previous_end in previous_runs:
                    if previous_start <= x - 1 and start <= previous_end:
                        union(find(previous_index), run_index)
                runs.append((run_index, start, x - 1))
                run_index += 1
            else:
                x += 1
        previous_runs = runs

    merged = {}
    for index, box in components.items():
        root = find(index)
        current = merged.get(root)
        if current is None:
            merged[root] = list(box)
            continue
        current[0] = min(current[0], box[0])
        current[1] = min(current[1], box[1])
        current[2] = max(current[2], box[2])
        current[3] = max(current[3], box[3])
    return [tuple(box) for box in merged.values()]


def _merge_nearby_boxes(boxes):
    """Merges component boxes whose edges are within the merge distance."""
    merged = [list(box) for box in sorted(boxes, key=lambda box: (box[1], box[0]))]
    changed = True
    while changed:
        changed = False
        for index, box in enumerate(merged):
            for other_index in range(index + 1, len(merged)):
                other = merged[other_index]
                if _boxes_are_near(box, other):
                    box[0] = min(box[0], other[0])
                    box[1] = min(box[1], other[1])
                    box[2] = max(box[2], other[2])
                    box[3] = max(box[3], other[3])
                    del merged[other_index]
                    changed = True
                    break
            if changed:
                break
    return [tuple(box) for box in merged]


def _boxes_are_near(first, second):
    """Returns whether two boxes overlap when grown by the merge distance."""
    return (
        first[0] - MERGE_DISTANCE <= second[2]
        and second[0] - MERGE_DISTANCE <= first[2]
        and first[1] - MERGE_DISTANCE <= second[3]
        and second[1] - MERGE_DISTANCE <= first[3]
    )


def _overlaps_horizontally(first, second):
    """Returns whether two boxes overlap horizontally."""
    return first[0] <= second[2] and second[0] <= first[2]


def _box_record(box):
    """Returns a box as a JSON-friendly record."""
    return {'left': box[0], 'top': box[1], 'right': box[2], 'bottom': box[3]}


def _page_number(page_name):
    """Returns the page number encoded in a ``page-NNNN.png`` file name."""
    digits = ''.join(character for character in os.path.splitext(page_name)[0] if character.isdigit())
    return int(digits) if digits else 0


if __name__ == '__main__':
    figure_extractor = FigureExtractor('converted_documents', 'extracted_figures')
    figure_extractor.extract_figures()
