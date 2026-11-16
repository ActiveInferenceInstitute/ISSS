"""Language analysis pipeline stage: descriptive statistics over document text.

Stage 7 reads only source/content-qualified text selected by stage 4's
``active.json`` manifest, never obsolete or failed-generation directory entries.
It writes two artifacts under ``output_path``:

- ``language_analysis.json`` — one record per document plus the corpus totals.
- ``SUMMARY.md`` — the same figures as a human-readable summary.

The statistics are descriptive and use only the standard library: character
and word counts, vocabulary size, sentence count, average word length, average
words per sentence, and the most frequent words. The rules are fixed here so
two runs over the same text agree:

- A word is a run of letters, digits or apostrophes after lowercasing, so
  ``Proceedings``, ``proceedings,`` and ``proceedings.`` all count as
  ``proceedings`` and ``don't`` stays one word.
- A sentence ends at ``.``, ``!`` or ``?``; empty segments do not count.
- Word frequencies are raw counts with no stop-word removal, and no
  lemmatization or part-of-speech tagging is applied.
- ``SUMMARY.md`` lists the most frequent words per document (top 50) and for
  the corpus (top 100); the JSON records keep the same lists.
- Documents are read in sorted name order and the artifacts overwrite earlier
  runs, so the output is deterministic.

Runnable standalone: ``python language_analyzer.py``.
"""

import os
import re
from collections import Counter

from pipeline_artifacts import ArtifactStore, atomic_json

#: A word: letters, digits and apostrophes after lowercasing.
WORD_PATTERN = re.compile(r"[a-z0-9']+")
#: Nonempty segments between the existing sentence delimiters.
SENTENCE_PATTERN = re.compile(r'[^.!?]+')
#: File names of the two artifacts this stage writes.
REPORT_NAME = 'language_analysis.json'
SUMMARY_NAME = 'SUMMARY.md'
#: How many frequent words each artifact keeps.
TOP_WORDS_PER_DOCUMENT = 50
TOP_WORDS_CORPUS = 100


class LanguageAnalyzer:
    """Compiles descriptive statistics over the converted document text."""

    def __init__(self, converted_path, output_path):
        self.store = ArtifactStore(converted_path, 'conversion')
        self.output_path = output_path
        os.makedirs(output_path, exist_ok=True)

    def analyze_language(self):
        """Aggregate qualified current text without retaining corpus token lists."""
        self.store = ArtifactStore(self.store.root, 'conversion')
        records = []
        corpus_counts = Counter()
        for converted in self.store.active_documents():
            path = self.store.resolve(converted, converted['text_file'])
            record, counts = self._document_statistics(
                path.name, path.read_text(encoding='utf-8')
            )
            records.append(record)
            corpus_counts.update(counts)
        records.sort(key=lambda record: record['document_name'])
        report = {
            'document_count': len(records),
            'documents': records,
            'totals': self._totals(records, corpus_counts),
            'failures': dict(self.store.failures),
        }
        self._write_report(report)
        print(
            f'Analysed {report["document_count"]} document(s) '
            f'({report["totals"]["words"]} words) into {self.output_path}.'
        )
        return report

    def analyze_document(self, document_path):
        """Compiles the statistics of one text file.

        Args:
            document_path (str): Path of the text file to analyse.

        Returns:
            dict: The document's counts, averages and most frequent words.
        """
        with open(document_path, encoding='utf-8') as document_file:
            text = document_file.read()
        record, _ = self._document_statistics(os.path.basename(document_path), text)
        return record

    @staticmethod
    def _document_statistics(name, text):
        """Return one record and vocabulary counter, using one normalized token rule."""
        counts = Counter(match.group() for match in WORD_PATTERN.finditer(text.lower()))
        words = sum(counts.values())
        letters = sum(len(word) * count for word, count in counts.items())
        sentences = sum(1 for match in SENTENCE_PATTERN.finditer(text) if match.group().strip())
        record = {
            'document_name': name,
            'characters': len(text),
            'words': words,
            'unique_words': len(counts),
            'sentences': sentences,
            'average_word_length': _average(letters, words),
            'average_words_per_sentence': _average(words, sentences),
            'most_common_words': _frequent_words(counts, TOP_WORDS_PER_DOCUMENT),
        }
        return record, counts

    @staticmethod
    def _totals(documents, counts):
        words = sum(counts.values())
        sentences = sum(document['sentences'] for document in documents)
        return {
            'documents': len(documents),
            'characters': sum(document['characters'] for document in documents),
            'words': words,
            'unique_words': len(counts),
            'sentences': sentences,
            'average_word_length': _average(
                sum(len(word) * count for word, count in counts.items()), words
            ),
            'average_words_per_sentence': _average(words, sentences),
            'most_common_words': _frequent_words(counts, TOP_WORDS_CORPUS),
        }

    def _write_report(self, report):
        """Writes the JSON report and the Markdown summary."""
        atomic_json(os.path.join(self.output_path, REPORT_NAME), report)
        with open(os.path.join(self.output_path, SUMMARY_NAME), 'w', encoding='utf-8') as summary:
            summary.write(self._summary_markdown(report))

    @staticmethod
    def _summary_markdown(report):
        """Renders the report as a Markdown summary."""
        lines = [
            '# Language analysis',
            '',
            f'Documents analysed: {report["document_count"]}',
            '',
            '## Documents',
            '',
            '| Document | Characters | Words | Unique words | Sentences |'
            ' Average word length | Average words/sentence |',
            '| --- | --- | --- | --- | --- | --- | --- |',
        ]
        for document in report['documents']:
            lines.append(
                '| {document_name} | {characters} | {words} | {unique_words} | {sentences} | '
                '{average_word_length} | {average_words_per_sentence} |'.format(**document)
            )
        totals = report['totals']
        lines += [
            '',
            '## Corpus',
            '',
            '| Documents | Characters | Words | Unique words | Sentences |'
            ' Average word length | Average words/sentence |',
            '| --- | --- | --- | --- | --- | --- | --- |',
            '| {documents} | {characters} | {words} | {unique_words} | {sentences} | '
            '{average_word_length} | {average_words_per_sentence} |'.format(**totals),
            '',
            f'Most frequent words (top {TOP_WORDS_CORPUS}):',
            '',
            ', '.join(f'{entry["word"]} ({entry["count"]})' for entry in totals['most_common_words']),
            '',
        ]
        return '\n'.join(lines)


def _average(total, count):
    """Round only the final quotient; preserve zero-denominator behavior."""
    return round(total / count, 2) if count else 0.0


def _frequent_words(counts, limit):
    """Return the existing deterministic count-descending, word-ascending order."""
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{'word': word, 'count': count} for word, count in ordered[:limit]]


if __name__ == '__main__':
    language_analyzer = LanguageAnalyzer('converted_documents', 'language_analysis')
    report = language_analyzer.analyze_language()
    raise SystemExit(1 if report['failures'] else 0)
