# Implementation Status

Current artifact contracts below describe the 2026-11-13 source and governed offline regression qualification. Dated source-availability and live-run sections remain historical, not refreshed observations.

## Source availability (checked 2026-11-01)

The pipeline's original single seed — the `web3.isss.org` front end — links no
documents:

- `https://web3.isss.org` returns HTTP 200 and its WordPress sitemaps list
  three URLs (`/`, `/sample-page/`, one hello-world post); its pages contain
  no `.pdf`/`.docx`/`.pptx`/`.xlsx` links. A crawl from that URL alone
  therefore finds nothing, which is what the 2026-08-02 live run recorded.
- The corpus is reachable on the same domain at legacy paths the front end
  does not link, for example
  `https://web3.isss.org/proceedings/2008_ISSS_Proceedings_from_CD.pdf`
  (HTTP 200, 52,882,005 bytes) and a 2006 Sonoma programme PDF under
  `/conferences/sonoma2006/`. Directory listings are not browsable
  (`/proceedings/` returns HTTP 403).
- The society site `https://www.isss.org` links those legacy paths from
  conference pages (`/annual-meetings/`, `/2023-kruger-national-park/`,
  `/2023-kruger-memories2/`, `/2025-washington-dc/`, `/2025-birmingham-uk/`)
  and also hosts documents of its own under `/editor_upload/File/`.

Discovery therefore starts from `SEED_URLS` (see
[configuration.md](configuration.md)). The seeds are link-bearing pages; a
directory path alone yields nothing.

## Implemented

| Stage | Module | Notes |
| --- | --- | --- |
| 1. Web scraping | `web_scraper.py` | `WebScraper` crawls from the configured seeds and collects document URLs. Runnable standalone: `python web_scraper.py`. |
| 2. Document download | `document_downloader.py` | `DocumentDownloader` downloads the discovered URLs concurrently. Runnable standalone: `python document_downloader.py`. See the download contract below. |
| 3. Metadata archiving | `metadata_archiver.py` | `MetadataArchiver` appends records to `metadata.json`. Runnable standalone: `python metadata_archiver.py`. |
| 4. File conversion | `file_converter.py` | Immutable text/page generations selected by `active.json`, with source/output hashes and retained `record.json`. |
| 5. OCR | `ocr_processor.py` | `OCRProcessor` extracts text from `.jpg` images. Runnable standalone: `python ocr_processor.py`. Outside `main.py`: the pipeline emits text and PNG pages, and OCR is applied inside stage 4 to PDF pages whose text layer is empty. |
| 6. Figure extraction | `figure_extractor.py` | Active conversion inputs produce immutable crop/metadata generations selected by `active.json`; legacy `figures.json` remains history. |
| 7. Language analysis | `language_analyzer.py` | Active qualified conversion text produces deterministic `language_analysis.json` and `SUMMARY.md`. |

## Live run (2026-11-02)

The pipeline ran on real documents for the first time. Discovery from the
configured society seeds did not complete — `www.isss.org` refused connections
intermittently (TCP refusals on ports 443 and 80 at `23.253.128.172`, in both
the pipeline client and `curl`, independent of User-Agent), and the reachable
front end links no documents — so stages 2-7 ran on two real proceedings
articles from the society's journal host (`journals.isss.org`), 14 and 16
pages, supplied as URLs.

| Measurement | Result |
| --- | --- |
| Wall clock, exit code | 76 s, 0 |
| Artifacts | `metadata.json`, 2 text files, 30 page images at 150 DPI, `figures.json`, `language_analysis.json`, `SUMMARY.md` |
| Text | 12,354 words, 2,692 unique, 732 sentences, 5.45 characters per word, 16.32 words per sentence |

The run exposed the two defects that the download and figure contracts record:
stage 6 reported paragraph blocks as figures (118 of 118 candidates; the
coverage test rejects them and 5 figures with real captions remain), and stage
2 saved an extension-less galley URL as `7584`, which stage 4 then skipped.

The third defect in discovery — the page budget going to front-end fragment
and utility URLs — is fixed; the rule and its before/after measurement are in
the discovery contract below.

## Discovery contract (stage 1)

`WebScraper` starts from `SEED_URLS`, follows same-domain links up to the depth
limit and records document URLs. Four rules keep the page budget on content:

| Rule | Effect |
| --- | --- |
| URL normalisation | The fragment is dropped, the scheme and host are lowercased, a default port and the session/tracking parameters (`sid`, `sessionid`, `phpsessid`, `jsessionid`, `fbclid`, `gclid`, `utm_*`) are removed and an empty query disappears. Links that differ only in those parts are one URL, so `page`, `page#content` and `page#respond` cost one fetch instead of three. |
| Utility filtering | Path segments `wp-admin`, `wp-login.php`, `wp-signup.php`, `wp-register.php`, `wp-cron.php`, `wp-json`, `xmlrpc.php`, `feed`, `comments`, `search` and the query keys `s`, `feed`, `replytocom` are site machinery. They are never queued. |
| Documents are results, not pages | A link to `.pdf`, `.docx`, `.pptx` or `.xlsx` is recorded and never fetched, so the crawl does not spend a page on a file it has already found. |
| Seed-fair budget | Seeds take turns one page at a time (round-robin). A seed whose links are exhausted drops out and the others continue. `MAX_PAGES` stays the total page budget for the run, across every seed. |

Decisions this contract fixes:

- Before these rules the first seed's depth-first walk spent the whole budget:
  on a page carrying WordPress link furniture, the same page was fetched three
  times (once for the page, once for `#content`, once for `#respond`) before
  `wp-login.php`, a feed and a search URL took the rest, and the second seed was
  never reached. The before/after measurement on one fixture site with
  `MAX_PAGES=6`: **before**, 6 of 6 pages fetched (`/seed-one/` three times,
  then `/wp-login.php`, `/annual-meetings/feed/`, `/?s=active+inference`) and
  0 documents; **after**, 4 pages (`/seed-one/`, `/seed-two/`, `/a/`, `/b/`) and
  the document the second seed links.
- The crawl is breadth-first from each seed: a seed's own pages are visited in
  the order their links appear, one page per turn.
- Seeds, discovered links, and each redirect require admitted HTTP(S) hostname/port boundaries before the next request.
- Failed/invalid seeds and budget truncation remain explicit in `CrawlResult`; successful peers do not erase incomplete status. Successful-empty discovery is distinct from failure. CLI/pipeline incomplete outcomes are nonzero.
- Dropping a fragment removes no content: a browser never sends one, so the
  server returns the same page; the change only stops the same page being
  counted twice against the budget.

## Download contract (stage 2)

Completed downloads return `DownloadReceipt` values binding source/final URLs, file bytes, and original acquisition time. Same-volume staging and no-clobber publication prevent partial or competing bytes from becoming accepted cache entries. File existence without matching receipt/content is not completion.

Content-type extension rules remain. Metadata consumes qualified receipt batches, validates the whole batch before one atomic publication, and avoids duplicate cached acquisitions. No current receipt is retrofitted onto ambiguous legacy bytes.

## Conversion contract (stage 4)

Conversion outputs live in immutable `.generations/<id>/` sets. Each retained `record.json` binds source and generated text/page bytes; `active.json` atomically selects successful qualified sets.

PDF text retains page boundaries and 150-DPI page images; image-only pages require Tesseract. Office documents retain text-only conversion. Logical names avoid same-basename collisions. A failed or shrinking replacement cannot expose stale pages/text; all consumers exclude retired, failed, stale, corrupt, or unqualified generations without deleting old history or unowned files.

## Figure contract (stage 6)

`FigureExtractor` reads only active qualified conversion sets, in deterministic document/page order. Crops and metadata are published in immutable generations with source/output hashes and retained `record.json`; `active.json` selects current figure sets. Legacy flat crops and `figures.json` remain untouched historical files, not current discovery inputs. Figure metadata retains:

| Field | Content |
| --- | --- |
| `figure` | Figure file name. |
| `page`, `page_image` | Page number and the page file the figure came from. |
| `page_size` | Page width and height in pixels, so a box can be rescaled. |
| `bbox` | The figure's source box on the page, in page pixels, right and bottom edges exclusive. |
| `caption_candidate`, `caption_bbox` | The nearest text block's text and box, or `null` when no block is close enough. |

Each document entry also reports how many regions were skipped:
`skipped_page_sized_regions` (whole-page scans) and `skipped_text_regions`
(dense text blocks).

Decisions this contract fixes:

- Detection runs on the rendered page and needs no source-document layout: the
  page is binarized (ink below a grayscale threshold) and connected components
  are built with a run-length sweep, then merged when their boxes are within a
  few pixels.
- A component becomes a candidate when both sides of its box reach a minimum
  size and its box covers between 3% and 80% of the page. That excludes text
  lines (too thin) and whole-page scans (too large); page-sized regions are
  counted in the report instead of being cropped.
- A candidate whose box is covered at least 15% by the word boxes Tesseract
  reports for the page is text, not a figure, and is counted in
  `skipped_text_regions` instead of being cropped. This test was added after
  the first live run: dense paragraph blocks pass the size and area tests, and
  on real proceedings pages they carry 0.5-0.6 of their box covered by
  recognized words while figures carry 0.06-0.18, so coverage is what
  separates the two. Before it, a 14-page and a 16-page article yielded 118
  "figures" that were all paragraphs, with the prose beside them reported as
  their captions; with it, 5 figures remain and their captions are the real
  ones (`Figure 1. From knowledge vision to organisational performance`,
  `Figure 2. A holistic knowledge scope`,
  `Figure 4. Triad of organizational manageable (based on Leonard-Barton, 1992)`).
- The caption candidate is the text block nearest to the figure box, measured
  as the vertical gap of blocks that overlap the figure horizontally, with
  blocks below the figure preferred when two are equally close.
- A figure without a candidate within the gap limit is still written, with
  `caption_candidate: null`, so an ambiguous case stays visible rather than
  being dropped.
- The caption text and the coverage test both come from Tesseract's word boxes
  for the page, so the stage needs the system Tesseract binary and inherits its
  recognition accuracy; a caption split across two detected blocks is reported
  as the block nearest the figure.

## Statistics contract (stage 7)

`LanguageAnalyzer` takes the converted root and reads only text in qualified active generations, then writes two artifacts:

| Artifact | Content |
| --- | --- |
| `language_analysis.json` | One record per document (name, characters, words, unique words, sentences, average word length, average words per sentence, the 50 most frequent words) plus the corpus totals (documents, characters, words, unique words, sentences, both averages, the 100 most frequent words). |
| `SUMMARY.md` | The same figures as two Markdown tables and the corpus word list. |

Decisions this contract fixes:

- The statistics are descriptive and use only the standard library; no
  lemmatization, part-of-speech tagging or stop-word removal is applied.
- A word is a run of letters, digits or apostrophes after lowercasing, so
  `Proceedings`, `proceedings,` and `proceedings.` all count as
  `proceedings`, and `don't` stays one word.
- A sentence ends at `.`, `!` or `?`; empty segments do not count.
- Counters and running weighted totals replace corpus-sized token/sentence lists. The existing lowercased ASCII/apostrophe rule applies consistently: `ISSS AI.` has two words. JSON and Markdown totals agree; historical live-run results above are not recalculated.
- Documents retain deterministic order; inactive and stale text cannot re-enter analysis by remaining on disk.

## Pipeline classes

| Module | Class | Constructor | Method |
| --- | --- | --- | --- |
| `file_converter.py` | `FileConverter` | `FileConverter(download_path, converted_path)` | `convert_files()` |
| `figure_extractor.py` | `FigureExtractor` | `FigureExtractor(converted_path, figure_output_path)` | `extract_figures()` |
| `language_analyzer.py` | `LanguageAnalyzer` | `LanguageAnalyzer(converted_path, output_path)` | `analyze_language()` |

Stage 6 and stage 7 consume the conversion root's active-generation contract. Standalone OCR remains separate; no flat-file compatibility scan or parallel artifact format is introduced.

To change a stage: keep its class and method names, keep the artifacts in the
contract above (or update the contract and the dependent stages together), add
offline tests under `tests/` (see [tests/README.md](../tests/README.md) for the
rules), and update this page and the
[README](../README.md#pipeline-components) component table.
