"""Tests for ``figure_extractor.FigureExtractor``.

Pages are synthetic grayscale images (a white page with black rectangles) and
``pytesseract.image_to_data`` is stubbed, so figure detection and caption
association are deterministic and the suite needs no Tesseract binary.
"""

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import figure_extractor
from figure_extractor import FigureExtractor
from pipeline_artifacts import ArtifactStore

PAGE_SIZE = (600, 800)
#: A 300x200 rectangle: 12.5% of the page, both sides above the minimum.
FIGURE_BOX = (100, 100, 400, 300)


def _write_page(path, rectangles, size=PAGE_SIZE):
    """Writes a white page with the given black rectangles.

    Rectangle coordinates are pixel-exclusive on the right and bottom edges,
    matching the boxes the extractor reports and crops.
    """
    image = Image.new("L", size, 255)
    draw = ImageDraw.Draw(image)
    for box in rectangles:
        left, top, right, bottom = box
        draw.rectangle((left, top, right - 1, bottom - 1), fill=0)
    image.save(path)


def _word_data(entries):
    """Builds a Tesseract-like data dict from ``(text, box, block, line)`` entries."""
    data = {
        "text": [],
        "left": [],
        "top": [],
        "width": [],
        "height": [],
        "block_num": [],
        "par_num": [],
        "line_num": [],
    }
    for text, box, block_num, line_num in entries:
        left, top, right, bottom = box
        data["text"].append(text)
        data["left"].append(left)
        data["top"].append(top)
        data["width"].append(right - left)
        data["height"].append(bottom - top)
        data["block_num"].append(block_num)
        data["par_num"].append(1)
        data["line_num"].append(line_num)
    return data


def _stub_ocr(monkeypatch, entries):
    """Stubs the Tesseract word boxes with the given entries."""
    monkeypatch.setattr(
        figure_extractor.pytesseract,
        "image_to_data",
        lambda image, output_type=None: _word_data(entries),
    )


def _extractor(tmp_path):
    return FigureExtractor(
        str(tmp_path / "converted_documents"), str(tmp_path / "extracted_figures")
    )


def _pages_directory(tmp_path, document_name):
    pages = tmp_path / "converted_documents" / "pages" / document_name
    pages.mkdir(parents=True, exist_ok=True)
    return pages


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------




def test_extract_page_writes_the_figure_crop_and_its_caption(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [FIGURE_BOX])
    _stub_ocr(
        monkeypatch,
        [("Figure", (100, 320, 160, 340), 0, 0), ("1", (165, 320, 180, 340), 0, 0)],
    )

    records, skipped = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert skipped == {'page_sized_regions': 0, 'text_regions': 0}
    assert records == [
        {
            "figure": "proceedings-fig-001.png",
            "page": 1,
            "page_image": "page-0001.png",
            "page_size": {"width": 600, "height": 800},
            "bbox": {"left": 100, "top": 100, "right": 400, "bottom": 300},
            "caption_candidate": "Figure 1",
            "caption_bbox": {"left": 100, "top": 320, "right": 180, "bottom": 340},
        }
    ]
    with Image.open(tmp_path / "extracted_figures" / "proceedings-fig-001.png") as figure:
        assert figure.size == (300, 200)
        assert figure.getpixel((150, 150)) == (0, 0, 0)


def test_small_marks_and_text_lines_are_not_figures(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [(10, 10, 30, 30), (0, 500, 600, 505)])
    _stub_ocr(monkeypatch, [])

    records, skipped = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records == []
    assert skipped == {'page_sized_regions': 0, 'text_regions': 0}
    assert list((tmp_path / "extracted_figures").iterdir()) == []


def test_page_sized_region_is_counted_and_not_cropped(tmp_path):
    pages = _pages_directory(tmp_path, "scan")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [(10, 10, 590, 790)])

    records, skipped = _extractor(tmp_path).extract_page(
        page_path, "scan", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records == []
    assert skipped == {'page_sized_regions': 1, 'text_regions': 0}
    assert list((tmp_path / "extracted_figures").iterdir()) == []


def test_figures_are_numbered_in_reading_order_across_pages(
    tmp_path, monkeypatch, publish_conversion
):
    pages = _pages_directory(tmp_path, "proceedings")
    _write_page(pages / "page-0001.png", [(100, 500, 300, 620), (350, 100, 500, 300)])
    _write_page(pages / "page-0002.png", [(100, 100, 300, 250)])
    _stub_ocr(monkeypatch, [])

    publish_conversion('proceedings.pdf', pages=sorted(pages.glob('*.png')))
    document = _extractor(tmp_path).extract_document("proceedings.pdf")

    assert [Path(figure["figure"]).name for figure in document["figures"]] == [
        "proceedings-fig-001.png",
        "proceedings-fig-002.png",
        "proceedings-fig-003.png",
    ]
    assert [figure["page"] for figure in document["figures"]] == [1, 1, 2]
    assert document["figures"][0]["bbox"] == {"left": 350, "top": 100, "right": 500, "bottom": 300}
    assert document["skipped_page_sized_regions"] == 0
    assert document["skipped_text_regions"] == 0
    with Image.open(tmp_path / "extracted_figures" / document['figures'][1]['figure']) as figure:
        assert figure.size == (200, 120)


# ---------------------------------------------------------------------------
# Caption candidates
# ---------------------------------------------------------------------------


def test_caption_below_wins_a_tie_with_one_above(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [(100, 300, 400, 500)])
    _stub_ocr(
        monkeypatch,
        [
            # Both blocks are 40 pixels away from the figure box.
            ("above", (100, 240, 180, 260), 0, 0),
            ("below", (100, 540, 180, 560), 1, 0),
        ],
    )

    records, _ = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records[0]["caption_candidate"] == "below"
    assert records[0]["caption_bbox"] == {"left": 100, "top": 540, "right": 180, "bottom": 560}


def test_nearest_block_wins_even_when_it_is_above(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [(100, 300, 400, 500)])
    _stub_ocr(
        monkeypatch,
        [
            ("above", (100, 240, 180, 260), 0, 0),
            ("below", (100, 570, 180, 590), 1, 0),
        ],
    )

    records, _ = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records[0]["caption_candidate"] == "above"


def test_caption_above_is_used_when_it_is_the_nearest(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [(100, 300, 400, 500)])
    _stub_ocr(monkeypatch, [("above", (100, 240, 180, 260), 0, 0)])

    records, _ = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records[0]["caption_candidate"] == "above"
    assert records[0]["caption_bbox"] == {"left": 100, "top": 240, "right": 180, "bottom": 260}


def test_distant_blocks_leave_the_figure_without_a_caption(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [FIGURE_BOX])
    _stub_ocr(monkeypatch, [("far below", (100, 700, 220, 720), 0, 0)])

    records, _ = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records[0]["caption_candidate"] is None
    assert records[0]["caption_bbox"] is None
    assert (tmp_path / "extracted_figures" / "proceedings-fig-001.png").exists()


def test_blocks_without_horizontal_overlap_are_ignored(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [FIGURE_BOX])
    _stub_ocr(monkeypatch, [("side note", (450, 320, 560, 340), 0, 0)])

    records, _ = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records[0]["caption_candidate"] is None


def test_no_caption_lookup_happens_without_candidates(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [(10, 10, 30, 30)])

    def fail_if_called(image, output_type=None):
        raise AssertionError("Tesseract must not run on a page without figure candidates")

    monkeypatch.setattr(figure_extractor.pytesseract, "image_to_data", fail_if_called)

    records, _ = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records == []


# ---------------------------------------------------------------------------
# Text coverage: dense paragraph blocks are text, not figures
# ---------------------------------------------------------------------------


def test_component_covered_by_text_is_not_a_figure(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [FIGURE_BOX])
    # A word box over the whole component: this is a text block, as on real pages.
    _stub_ocr(monkeypatch, [("paragraph", (100, 100, 400, 300), 0, 0)])

    records, skipped = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records == []
    assert skipped == {"page_sized_regions": 0, "text_regions": 1}
    assert list((tmp_path / "extracted_figures").iterdir()) == []


def test_text_coverage_at_the_limit_is_rejected(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [FIGURE_BOX])
    # 150x60 of the 300x200 component: exactly the 15% coverage limit.
    _stub_ocr(monkeypatch, [("words", (100, 100, 250, 160), 0, 0)])

    records, skipped = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records == []
    assert skipped == {"page_sized_regions": 0, "text_regions": 1}


def test_large_figure_with_a_small_annotation_inside_is_kept(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [FIGURE_BOX])
    # 60x20 of the 300x200 component: 2% coverage, an annotation inside a figure.
    _stub_ocr(monkeypatch, [("axis label", (120, 120, 180, 140), 0, 0)])

    records, skipped = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert skipped == {"page_sized_regions": 0, "text_regions": 0}
    assert len(records) == 1
    # The only block sits inside the figure box, so it is not a caption.
    assert records[0]["caption_candidate"] is None
    assert (tmp_path / "extracted_figures" / "proceedings-fig-001.png").exists()


def test_blank_ocr_words_are_ignored(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [FIGURE_BOX])
    _stub_ocr(
        monkeypatch,
        [("", (100, 320, 180, 340), 0, 0), ("Figure 1", (100, 320, 180, 340), 0, 0)],
    )

    records, _ = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records[0]["caption_candidate"] == "Figure 1"


def test_block_inside_the_figure_box_is_not_a_caption(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    _write_page(page_path, [FIGURE_BOX])
    _stub_ocr(monkeypatch, [("inside", (150, 150, 250, 170), 0, 0)])

    records, _ = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records[0]["caption_candidate"] is None


def test_component_below_the_area_ratio_is_ignored(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    # 60x60 pixels: both sides are above the minimum, the area is not.
    _write_page(page_path, [(100, 100, 160, 160)])
    _stub_ocr(monkeypatch, [])

    records, skipped = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert records == []
    assert skipped == {'page_sized_regions': 0, 'text_regions': 0}


def test_nearby_components_merge_into_one_figure(tmp_path, monkeypatch):
    pages = _pages_directory(tmp_path, "proceedings")
    page_path = pages / "page-0001.png"
    # Two 100x100 squares with a four-pixel gap merge into one figure.
    _write_page(page_path, [(100, 100, 200, 200), (204, 100, 304, 200)])
    _stub_ocr(monkeypatch, [])

    records, _ = _extractor(tmp_path).extract_page(
        page_path, "proceedings", 1, output_path=tmp_path / "extracted_figures"
    )

    assert len(records) == 1
    assert records[0]["bbox"] == {"left": 100, "top": 100, "right": 304, "bottom": 200}
    with Image.open(tmp_path / "extracted_figures" / "proceedings-fig-001.png") as figure:
        assert figure.size == (204, 100)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def test_extract_figures_writes_the_metadata_report(tmp_path, monkeypatch, publish_conversion):
    _write_page(_pages_directory(tmp_path, "proceedings") / "page-0001.png", [FIGURE_BOX])
    _write_page(_pages_directory(tmp_path, "minutes") / "page-0001.png", [(50, 50, 200, 200)])
    (tmp_path / "converted_documents" / "pages" / "minutes" / "notes.txt").write_text("ignored")
    _stub_ocr(monkeypatch, [])
    for name in ('proceedings', 'minutes'):
        publish_conversion(
            name + '.pdf',
            pages=sorted((tmp_path / 'converted_documents' / 'pages' / name).glob('*.png')),
        )

    report = _extractor(tmp_path).extract_figures()

    assert report["document_count"] == 2
    assert report["figure_count"] == 2
    assert [document["document_name"] for document in report["documents"]] == [
        "minutes.pdf",
        "proceedings.pdf",
    ]
    assert json.loads((tmp_path / "extracted_figures" / "active.json").read_text()) == report


def test_missing_pages_directory_produces_an_empty_report(tmp_path):
    report = _extractor(tmp_path).extract_figures()

    assert report['documents'] == []
    assert report['figure_count'] == 0
    assert json.loads((tmp_path / "extracted_figures" / "active.json").read_text()) == report


def test_figure_rerun_retires_obsolete_crops_without_deleting_history(
    tmp_path, monkeypatch, publish_conversion
):
    pages = _pages_directory(tmp_path, 'paper')
    page = pages / 'page-0001.png'
    _write_page(page, [(100, 100, 300, 300), (350, 500, 550, 700)])
    publish_conversion('paper.pdf', pages=[page])
    _stub_ocr(monkeypatch, [])
    extractor = _extractor(tmp_path)
    first = extractor.extract_figures()['documents'][0]
    output = tmp_path / 'extracted_figures'
    history = {row['figure']: (output / row['figure']).read_bytes() for row in first['figures']}
    (output / 'paper-fig-099.png').write_bytes(b'unowned')
    (output / 'figures.json').write_bytes(b'historical legacy report')
    _write_page(page, [FIGURE_BOX])
    publish_conversion('paper.pdf', pages=[page])
    report = extractor.extract_figures()
    assert report['figure_count'] == 1
    assert all((output / name).read_bytes() == content for name, content in history.items())
    assert (output / 'paper-fig-099.png').read_bytes() == b'unowned'
    assert (output / 'figures.json').read_bytes() == b'historical legacy report'
    selected = ArtifactStore(output, 'figures').active_documents()
    assert selected[0]['generation'] != first['generation']
    assert len(selected[0]['figures']) == 1


def test_retired_conversion_invalidates_old_figures_before_another_extraction(
    tmp_path, monkeypatch, publish_conversion
):
    page = _pages_directory(tmp_path, 'paper') / 'page-0001.png'
    _write_page(page, [FIGURE_BOX])
    converted, _ = publish_conversion('paper.pdf', pages=[page])
    _stub_ocr(monkeypatch, [])
    first = _extractor(tmp_path).extract_figures()['documents'][0]
    output = tmp_path / 'extracted_figures'
    previous_crop = output / first['figures'][0]['figure']
    before = previous_crop.read_bytes()
    producer = ArtifactStore(converted, 'conversion')
    producer.fail('paper.pdf', 'replacement conversion failed')
    producer.commit()
    assert ArtifactStore(output, 'figures').active_documents() == []
    report = _extractor(tmp_path).extract_figures()
    assert report['documents'] == []
    assert report['failures']['paper.pdf'] == 'replacement conversion failed'
    assert previous_crop.read_bytes() == before


def test_later_page_failure_publishes_no_partial_figure_set(
    tmp_path, monkeypatch, publish_conversion
):
    pages = _pages_directory(tmp_path, 'paper')
    first_page, second_page = pages / 'page-0001.png', pages / 'page-0002.png'
    _write_page(first_page, [FIGURE_BOX])
    _write_page(second_page, [FIGURE_BOX])
    publish_conversion('paper.pdf', pages=[first_page, second_page])
    _stub_ocr(monkeypatch, [])
    extractor = _extractor(tmp_path)
    original = extractor.extract_figures()['documents'][0]
    output = tmp_path / 'extracted_figures'
    before = {row['figure']: (output / row['figure']).read_bytes() for row in original['figures']}
    publish_conversion('paper.pdf', text='new generation', pages=[first_page, second_page])
    calls = []

    def fail_on_second_page(image):
        calls.append(image.size)
        if len(calls) == 2:
            raise RuntimeError('later figure OCR failed')
        return _word_data([])

    monkeypatch.setattr(figure_extractor, '_ocr_page', fail_on_second_page)
    report = extractor.extract_figures()
    assert report['documents'] == []
    assert 'later figure OCR failed' in report['failures']['paper.pdf']
    assert all((output / name).read_bytes() == content for name, content in before.items())
    assert not list((output / '.generations').glob('.staging-*'))


def test_multiple_crops_preserve_rgb_pixels_and_coordinates(tmp_path, monkeypatch):
    page = _pages_directory(tmp_path, 'paper') / 'page-0001.png'
    _write_page(page, [(100, 100, 300, 300), (350, 500, 550, 700)])
    _stub_ocr(monkeypatch, [])
    output = tmp_path / 'crops'
    records, _ = _extractor(tmp_path).extract_page(page, 'paper', 1, output_path=output)
    assert len(records) == 2
    with Image.open(page) as original:
        for row in records:
            box = row['bbox']
            expected = original.convert('L').crop(
                (box['left'], box['top'], box['right'], box['bottom'])
            ).convert('RGB')
            with Image.open(output / row['figure']) as actual:
                assert actual.mode == 'RGB'
                assert actual.size == expected.size
                assert actual.tobytes() == expected.tobytes()


@pytest.mark.parametrize(
    ('boxes', 'expected'),
    [
        ([(0, 0, 10, 10), (17, 0, 27, 10), (34, 0, 44, 10)], [(0, 0, 44, 10)]),
        ([(0, 0, 10, 40), (18, 0, 40, 10), (30, 30, 40, 40)], [(0, 0, 40, 40)]),
        ([(0, 0, 10, 10), (19, 0, 29, 10)], [(0, 0, 10, 10), (19, 0, 29, 10)]),
        ([(0, 0, 10**9, 10**9), (100, 100, 200, 200)], [(0, 0, 10**9, 10**9)]),
    ],
)
def test_spatial_candidates_preserve_merge_boundaries_and_late_bridges(boxes, expected):
    assert figure_extractor._merge_nearby_boxes(boxes) == expected
    assert figure_extractor._merge_nearby_boxes(list(reversed(boxes))) == expected


def test_separated_grid_keeps_all_components_in_reading_order():
    boxes = [
        (x * 100, y * 100, x * 100 + 10, y * 100 + 10)
        for y in range(10) for x in range(10)
    ]
    assert figure_extractor._merge_nearby_boxes(list(reversed(boxes))) == boxes
