import os
   
# URLs document for website therape Sc:1  Step #

_output_analysis_language = '_path_output_analysis_language'
_outputfigure = '_path_output_figure'
_outputocr = '_path_output_ocr'
_documentsconverted = '_path_converted'
_documentsivedarch = '_path_archive'
from web_scraper import WebScraper
from document_downloader import DocumentDownloader
from metadata_archiver import MetadataArchiver
from file_converter import FileConverter
from ocr_processor import OCRProcessor
from figure_extractor import FigureExtractor
from language_analyzer import LanguageAnalyzer

def main():
    scraper = WebScraper(base_url)
    scraper.start_crawling()
    document_urls = scraper.get_document_urls()

    # Step 2: Download all documents discovered
    downloader = DocumentDownloader(base_url, download_path)
    for url in document_urls:
        downloader.save_document(url)

    # Step 3: Archive documents with metadata
    archiver = MetadataArchiver(archive_path)
    for url in document_urls:
        document_name = url.split('/')[-1]
        document_path = os.path.join(download_path, document_name)
        archiver.archive_metadata(document_path, url, document_name.split('.')[-1])

    # Step 4: Convert files into clean and scannable versions
    converter = FileConverter(download_path, converted_path)
    converter.convert_files()

    # Step 5: Deploy OCR to extract all text
    ocr_processor = OCRProcessor(converted_path, ocr_output_path)
    ocr_processor.process_documents()

    # Step 6: Extract figures with captions
    figure_extractor = FigureExtractor(converted_path, figure_output_path)
    figure_extractor.extract_figures()

    # Step 7: Provide descriptive statistics on all language analysis
    language_analyzer = LanguageAnalyzer(ocr_output_path, language_analysis_output_path)
    language_analyzer.analyze_language()

if __name__ == '__main__':
    main()

    base_url = 'http://example.com'
    download_path