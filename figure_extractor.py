"""Figure extraction pipeline stage: figures and caption candidates from pages.

Stage 6 reads only stage 4's qualified active generation manifest. Crops are
published as immutable document sets and selected by the figure directory's own
``active.json``. Legacy crops and ``figures.json`` remain historical, never inputs.

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

Documents and declared pages retain deterministic reading order. Figure numbers
start at ``fig-001`` per document. Failed or retired sets are excluded atomically;
historical generations and unowned files are never overwritten or removed.

Runnable standalone: ``python figure_extractor.py``.
"""

import os
from collections import defaultdict
from pathlib import Path

import pytesseract
from PIL import Image

from pipeline_artifacts import ArtifactStore, file_identity

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
#: The same active-generation contract as stage 4; legacy reports remain untouched.
REPORT_NAME = 'active.json'


class FigureExtractor:
    """Extracts the figures and caption candidates of converted page images."""

    def __init__(self, converted_path, figure_output_path):
        self.converted_path = Path(converted_path)
        self.figure_output_path = Path(figure_output_path)
        self.store = ArtifactStore(figure_output_path, 'figures')
        self.figure_output_path.mkdir(parents=True, exist_ok=True)

    def extract_figures(self):
        """Atomically select only successful figures of current conversion sets."""
        producer = ArtifactStore(self.converted_path, 'conversion')
        documents = [record for record in producer.active_documents() if record['page_files']]
        self.store.select(record['document_name'] for record in documents)
        self.store.failures.update(producer.failures)
        for document in documents:
            self._extract_document(document, producer)
        report = self.store.commit()
        print(
            f'Extracted {report["figure_count"]} figure(s) from '
            f'{report["document_count"]} document(s) into {self.figure_output_path}.'
        )
        return report

    def extract_document(self, document_name):
        """Replace one selected source document; names include their source extension."""
        producer = ArtifactStore(self.converted_path, 'conversion')
        records = {record['document_name']: record for record in producer.active_documents()}
        if document_name not in records:
            raise ValueError(f'no qualified conversion for {document_name}')
        result = self._extract_document(records[document_name], producer)
        self.store.commit()
        return result

    def _extract_document(self, document, producer):
        name = document['document_name']
        try:
            figures = []
            skipped_page_sized = skipped_text = 0
            artifact_name = Path(document['text_file']).stem
            with self.store.stage() as (generation, staged):
                for relative in document['page_files']:
                    page = producer.resolve(document, relative)
                    page_figures, skipped = self.extract_page(
                        page, artifact_name, _page_number(page.name), len(figures) + 1,
                        output_path=staged,
                    )
                    figures.extend(page_figures)
                    skipped_page_sized += skipped['page_sized_regions']
                    skipped_text += skipped['text_regions']
                source = document['source']
                if file_identity(source['path']) != {
                    'sha256': source['sha256'], 'size': source['size']
                }:
                    raise ValueError('source changed during figure extraction')
                current = ArtifactStore(self.converted_path, 'conversion')
                if current.documents.get(name, {}).get('generation') != document['generation']:
                    raise ValueError('conversion changed during figure extraction')
                for figure in figures:
                    figure['figure'] = f'.generations/{generation}/' + figure['figure']
                return self.store.publish(staged, {
                    'document_name': name,
                    'generation': generation,
                    'source': dict(source),
                    'upstream': {
                        'manifest': str(producer.manifest_path.absolute()),
                        'generation': document['generation'],
                    },
                    'figures': figures,
                    'skipped_page_sized_regions': skipped_page_sized,
                    'skipped_text_regions': skipped_text,
                })
        except Exception as error:
            self.store.fail(name, error)
            print(f'Skipped figures for {name}: {error}')
            return None

    def extract_page(
        self, page_path, document_name, page_number, first_figure_number=1, *, output_path
    ):
        """Write candidate crops only into the caller's explicit private staging path."""
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
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
            page.crop(box).convert('RGB').save(output_path / figure_name)
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
    """Prune distant pairs while preserving the original first-pair restart order."""
    ordered = sorted(boxes, key=lambda box: (box[1], box[0]))
    active = {index: list(box) for index, box in enumerate(ordered)}
    cells = defaultdict(set)
    memberships = {}
    large = set()
    cell_size = max(1, 2 * MERGE_DISTANCE + 1)

    def keys(box, grow=0):
        left, top, right, bottom = box
        x1, x2 = (left - grow) // cell_size, (right + grow) // cell_size
        y1, y2 = (top - grow) // cell_size, (bottom + grow) // cell_size
        # Large boxes use a side set: never allocate a grid proportional to
        # arbitrary coordinate magnitudes. This changes candidates, not science.
        if (x2 - x1 + 1) * (y2 - y1 + 1) > max(1, len(ordered)):
            return None
        return [(x, y) for x in range(x1, x2 + 1) for y in range(y1, y2 + 1)]

    def add(index):
        membership = keys(active[index])
        memberships[index] = membership
        if membership is None:
            large.add(index)
        else:
            for key in membership:
                cells[key].add(index)

    def remove(index):
        membership = memberships.pop(index)
        if membership is None:
            large.remove(index)
        else:
            for key in membership:
                cells[key].remove(index)
                if not cells[key]:
                    del cells[key]

    for index in active:
        add(index)
    while True:
        changed = False
        for index, box in active.items():
            nearby = keys(box, MERGE_DISTANCE)
            candidates = set(active) if nearby is None else set(large)
            if nearby is not None:
                for key in nearby:
                    candidates.update(cells.get(key, ()))
            for other_index in sorted(candidate for candidate in candidates if candidate > index):
                other = active[other_index]
                if not _boxes_are_near(box, other):
                    continue
                remove(index)
                remove(other_index)
                box[:] = [
                    min(box[0], other[0]), min(box[1], other[1]),
                    max(box[2], other[2]), max(box[3], other[3]),
                ]
                del active[other_index]
                add(index)
                changed = True
                break
            if changed:
                break
        if not changed:
            return [tuple(box) for box in active.values()]


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
    report = figure_extractor.extract_figures()
    raise SystemExit(1 if report['failures'] else 0)
