"""Language analysis pipeline stage: descriptive statistics over document text.

Stage 7 of the pipeline. ``LanguageAnalyzer`` reads every ``.txt`` file in
``text_path`` — the ``text/`` directory written by stage 4 — and writes two
artifacts under ``output_path``:

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

import json
import os
import re
from collections import Counter

#: A word: letters, digits and apostrophes after lowercasing.
WORD_PATTERN = re.compile(r"[a-z0-9']+")
#: Characters that end a sentence.
SENTENCE_PATTERN = re.compile(r'[.!?]+')
#: File names of the two artifacts this stage writes.
REPORT_NAME = 'language_analysis.json'
SUMMARY_NAME = 'SUMMARY.md'
#: How many frequent words each artifact keeps.
TOP_WORDS_PER_DOCUMENT = 50
TOP_WORDS_CORPUS = 100


class LanguageAnalyzer:
    """Compiles descriptive statistics over the converted document text."""

    def __init__(self, text_path, output_path):
        """Initializes the LanguageAnalyzer with input and output paths.

        Args:
            text_path (str): Directory holding the ``.txt`` document text.
            output_path (str): Directory where the report and the summary are
                written.
        """
        self.text_path = text_path
        self.output_path = output_path
        os.makedirs(output_path, exist_ok=True)

    def analyze_language(self):
        """Analyses every text file in the input directory.

        Returns:
            dict: The report that was written: one record per document plus
            the corpus totals.
        """
        records = []
        corpus_words = []
        corpus_words_per_sentence = []
        for filename in sorted(os.listdir(self.text_path)):
            if not filename.lower().endswith('.txt'):
                continue
            with open(os.path.join(self.text_path, filename), encoding='utf-8') as document_file:
                text = document_file.read()
            record, words, words_per_sentence = self._document_statistics(filename, text)
            records.append(record)
            corpus_words.extend(words)
            corpus_words_per_sentence.extend(words_per_sentence)

        report = {
            'document_count': len(records),
            'documents': records,
            'totals': self._totals(records, corpus_words, corpus_words_per_sentence),
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
        record, _, _ = self._document_statistics(os.path.basename(document_path), text)
        return record

    @staticmethod
    def _document_statistics(name, text):
        """Returns the statistics of one document and its raw word lists.

        Args:
            name (str): Name of the document file.
            text (str): The document text.

        Returns:
            tuple[dict, list[str], list[int]]: The document record, its words
            in reading order, and the word count of each sentence.
        """
        words = WORD_PATTERN.findall(text.lower())
        sentences = [segment for segment in SENTENCE_PATTERN.split(text) if segment.strip()]
        words_per_sentence = [len(WORD_PATTERN.findall(segment)) for segment in sentences]
        record = {
            'document_name': name,
            'characters': len(text),
            'words': len(words),
            'unique_words': len(set(words)),
            'sentences': len(sentences),
            'average_word_length': _rounded(_mean([len(word) for word in words])),
            'average_words_per_sentence': _rounded(_mean(words_per_sentence)),
            'most_common_words': _frequent_words(words, TOP_WORDS_PER_DOCUMENT),
        }
        return record, words, words_per_sentence

    @staticmethod
    def _totals(documents, words, words_per_sentence):
        """Aggregates the corpus totals over the analysed documents."""
        return {
            'documents': len(documents),
            'characters': sum(document['characters'] for document in documents),
            'words': len(words),
            'unique_words': len(set(words)),
            'sentences': sum(document['sentences'] for document in documents),
            'average_word_length': _rounded(_mean([len(word) for word in words])),
            'average_words_per_sentence': _rounded(_mean(words_per_sentence)),
            'most_common_words': _frequent_words(words, TOP_WORDS_CORPUS),
        }

    def _write_report(self, report):
        """Writes the JSON report and the Markdown summary."""
        with open(os.path.join(self.output_path, REPORT_NAME), 'w', encoding='utf-8') as report_file:
            json.dump(report, report_file, indent=2, ensure_ascii=False)
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


def _mean(values):
    """Returns the arithmetic mean, or 0.0 for an empty sequence."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _rounded(value):
    """Rounds a statistic so the report is stable."""
    return round(value, 2)


def _frequent_words(words, limit):
    """Returns the most frequent words as records, most frequent first."""
    counts = Counter(words)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{'word': word, 'count': count} for word, count in ordered[:limit]]


if __name__ == '__main__':
    language_analyzer = LanguageAnalyzer('converted_documents/text', 'language_analysis')
    language_analyzer.analyze_language()
