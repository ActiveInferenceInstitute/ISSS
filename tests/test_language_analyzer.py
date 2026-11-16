"""Tests for ``language_analyzer.LanguageAnalyzer``.

The fixtures are small text files written in ``tmp_path``; the stage uses only
the standard library, so no stubbing is needed.
"""

import json

import pytest

from language_analyzer import LanguageAnalyzer
from pipeline_artifacts import ArtifactStore

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


def test_analyze_language_writes_the_report_and_the_summary(tmp_path, publish_conversion):
    converted, _ = publish_conversion('b.pdf', "Second document.")
    publish_conversion('a.pdf', DOCUMENT_TEXT)
    (converted / 'notes.md').write_text('not analysed')

    output = tmp_path / "language_analysis"
    report = LanguageAnalyzer(converted, output).analyze_language()

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


@pytest.mark.parametrize(
    ('text', 'words', 'sentences', 'average_length', 'average_sentence'),
    [
        ('ISSS AI.', 2, 1, 3.0, 2.0),
        ("don't DON'T.", 2, 1, 5.0, 2.0),
        ('A 2. B?', 3, 2, 1.0, 1.5),
        ('!!? \n', 0, 0, 0.0, 0.0),
    ],
)
def test_normalized_document_and_corpus_statistics_agree(
    tmp_path, publish_conversion, text, words, sentences, average_length, average_sentence
):
    converted, _ = publish_conversion('uppercase.pdf', text)
    report = LanguageAnalyzer(converted, tmp_path / 'analysis').analyze_language()
    for record in (report['documents'][0], report['totals']):
        assert record['words'] == words
        assert record['sentences'] == sentences
        assert record['average_word_length'] == average_length
        assert record['average_words_per_sentence'] == average_sentence
    summary = (tmp_path / 'analysis' / 'SUMMARY.md').read_text()
    assert f'| uppercase.txt | {len(text)} | {words} |' in summary


def test_corpus_averages_weight_tokens_not_rounded_document_averages(tmp_path, publish_conversion):
    converted, _ = publish_conversion('first.pdf', 'AA BB CC.')
    publish_conversion('second.pdf', 'LONGWORD.')
    report = LanguageAnalyzer(converted, tmp_path / 'analysis').analyze_language()
    assert report['totals']['average_word_length'] == 3.5
    assert report['totals']['average_words_per_sentence'] == 2.0
    assert [item['word'] for item in report['totals']['most_common_words']] == [
        'aa', 'bb', 'cc', 'longword'
    ]


def test_failed_or_retired_text_and_legacy_files_never_enter_corpus(tmp_path, publish_conversion):
    converted, previous = publish_conversion('old.pdf', 'Old text.')
    publish_conversion('current.pdf', 'Current words.')
    old_text = converted / previous['text_file']
    store = ArtifactStore(converted, 'conversion')
    store.fail('old.pdf', 'replacement failed')
    store.commit()
    (converted / 'text').mkdir()
    (converted / 'text' / 'unqualified.txt').write_text('Must not be counted.')
    report = LanguageAnalyzer(converted, tmp_path / 'analysis').analyze_language()
    assert [record['document_name'] for record in report['documents']] == ['current.txt']
    assert report['totals']['words'] == 2
    assert report['failures']['old.pdf'] == 'replacement failed'
    assert old_text.read_text() == 'Old text.'


def test_repeated_tokens_keep_exact_counts_and_deterministic_ties(tmp_path, publish_conversion):
    converted, _ = publish_conversion('first.pdf', ('ALPHA beta ' * 2000) + '.')
    publish_conversion('second.pdf', ('beta ALPHA ' * 2000) + 'Gamma.')
    report = LanguageAnalyzer(converted, tmp_path / 'analysis').analyze_language()
    assert report['totals']['words'] == 8001
    assert report['totals']['unique_words'] == 3
    assert report['totals']['most_common_words'] == [
        {'word': 'alpha', 'count': 4000}, {'word': 'beta', 'count': 4000},
        {'word': 'gamma', 'count': 1},
    ]


@pytest.mark.parametrize('change', ['retire', 'replace', 'remove'])
def test_reused_analyzer_reloads_current_selection(tmp_path, publish_conversion, change):
    converted, previous = publish_conversion('old.pdf', 'Old document.')
    old_text = converted / previous['text_file']
    analyzer = LanguageAnalyzer(converted, tmp_path / 'analysis')
    assert analyzer.analyze_language()['document_count'] == 1
    if change == 'replace':
        publish_conversion('new.pdf', 'Replacement document.')
    store = ArtifactStore(converted, 'conversion')
    store.select(['new.pdf'] if change == 'replace' else [])
    store.commit()
    if change == 'remove':
        (converted / 'active.json').unlink()
    report = analyzer.analyze_language()
    assert [record['document_name'] for record in report['documents']] == (
        ['new.txt'] if change == 'replace' else []
    )
    assert old_text.read_text() == 'Old document.'
