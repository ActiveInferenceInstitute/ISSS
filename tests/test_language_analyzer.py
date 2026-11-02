"""Tests for ``language_analyzer.LanguageAnalyzer``.

The fixtures are small text files written in ``tmp_path``; the stage uses only
the standard library, so no stubbing is needed.
"""

import json

from language_analyzer import LanguageAnalyzer

DOCUMENT_TEXT = "Active inference works. Active inference!\n"


def test_constructor_creates_the_output_directory(tmp_path):
    output = tmp_path / "language_analysis"

    LanguageAnalyzer(str(tmp_path / "text"), str(output))

    assert output.is_dir()


def test_analyze_document_returns_counts_and_averages(tmp_path):
    text_path = tmp_path / "text"
    text_path.mkdir()
    document = text_path / "a.txt"
    document.write_text(DOCUMENT_TEXT)

    analyzer = LanguageAnalyzer(str(text_path), str(tmp_path / "language_analysis"))

    assert analyzer.analyze_document(str(document)) == {
        "document_name": "a.txt",
        "characters": len(DOCUMENT_TEXT),
        "words": 5,
        "unique_words": 3,
        "sentences": 2,
        "average_word_length": 7.0,
        "average_words_per_sentence": 2.5,
        "most_common_words": [
            {"word": "active", "count": 2},
            {"word": "inference", "count": 2},
            {"word": "works", "count": 1},
        ],
    }


def test_analyze_language_writes_the_report_and_the_summary(tmp_path):
    text_path = tmp_path / "text"
    text_path.mkdir()
    (text_path / "b.txt").write_text("Second document.")
    (text_path / "a.txt").write_text(DOCUMENT_TEXT)
    (text_path / "notes.md").write_text("not analysed")

    output = tmp_path / "language_analysis"
    report = LanguageAnalyzer(str(text_path), str(output)).analyze_language()

    assert [document["document_name"] for document in report["documents"]] == ["a.txt", "b.txt"]
    assert report["document_count"] == 2
    assert report["totals"] == {
        "documents": 2,
        "characters": len(DOCUMENT_TEXT) + len("Second document."),
        "words": 7,
        "unique_words": 5,
        "sentences": 3,
        "average_word_length": round((6 + 9 + 5 + 6 + 9 + 6 + 8) / 7, 2),
        "average_words_per_sentence": round(7 / 3, 2),
        "most_common_words": [
            {"word": "active", "count": 2},
            {"word": "inference", "count": 2},
            {"word": "document", "count": 1},
            {"word": "second", "count": 1},
            {"word": "works", "count": 1},
        ],
    }

    assert json.loads((output / "language_analysis.json").read_text()) == report

    summary = (output / "SUMMARY.md").read_text()
    assert "Documents analysed: 2" in summary
    assert "| a.txt |" in summary
    assert "| 2 |" in summary
    assert "active (2)" in summary
    assert "notes.md" not in summary


def test_empty_document_statistics_are_zero(tmp_path):
    text_path = tmp_path / "text"
    text_path.mkdir()
    document = text_path / "empty.txt"
    document.write_text("")

    analyzer = LanguageAnalyzer(str(text_path), str(tmp_path / "language_analysis"))
    record = analyzer.analyze_document(str(document))

    assert record["characters"] == 0
    assert record["words"] == 0
    assert record["unique_words"] == 0
    assert record["sentences"] == 0
    assert record["average_word_length"] == 0.0
    assert record["average_words_per_sentence"] == 0.0
    assert record["most_common_words"] == []


def test_empty_input_directory_produces_empty_totals(tmp_path):
    text_path = tmp_path / "text"
    text_path.mkdir()

    report = LanguageAnalyzer(str(text_path), str(tmp_path / "language_analysis")).analyze_language()

    assert report["document_count"] == 0
    assert report["documents"] == []
    assert report["totals"]["words"] == 0
    assert report["totals"]["unique_words"] == 0
    assert report["totals"]["average_word_length"] == 0.0
